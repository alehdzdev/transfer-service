import logging
from datetime import date, datetime, timedelta

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.domain import validate_in_progress_fields, validate_status_transition
from app.models import (
    Notification,
    Transfer,
    TransferStatus,
    TransferStatusHistory,
    Vehicle,
)
from app.schemas import (
    StatusUpdate,
    TransferCreate,
    TransferDetailOut,
    TransferOut,
    VehicleCreate,
    VehicleOut,
)

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Vehicles
# ---------------------------------------------------------------------------

@router.post("/vehicles", response_model=VehicleOut, status_code=201)
def create_vehicle(payload: VehicleCreate, db: Session = Depends(get_db)):
    vehicle = Vehicle(**payload.model_dump())
    db.add(vehicle)
    db.commit()
    db.refresh(vehicle)
    return vehicle


# ---------------------------------------------------------------------------
# Availability
# ---------------------------------------------------------------------------

@router.get("/availability", response_model=list[VehicleOut])
def check_availability(
    date_: date = Query(..., alias="date"),
    pax_count: int = Query(..., gt=0),
    pickup_time: datetime | None = Query(default=None),
    db: Session = Depends(get_db),
):
    """Return vehicles available for the given date and passenger count.

    Uses raw SQL (SQLAlchemy text()) for the overlap check as required.

    A vehicle is available when:
    1. Its status is AVAILABLE
    2. Its capacity >= pax_count
    3. It has no CONFIRMED or IN_PROGRESS transfer whose pickup_time falls
       within a 2-hour window around the requested pickup_time.

    If pickup_time is not supplied, it defaults to noon on the requested date
    and the window spans the full day (00:00 – 23:59:59).
    """
    if pickup_time is not None:
        window_start = pickup_time - timedelta(hours=2)
        window_end = pickup_time + timedelta(hours=2)
    else:
        window_start = datetime.combine(date_, datetime.min.time())
        window_end = datetime.combine(date_, datetime.max.time())

    # Raw SQL: find vehicle IDs that have a conflicting transfer.
    sql = text("""
        SELECT DISTINCT t.vehicle_id
        FROM transfers t
        WHERE t.status IN ('CONFIRMED', 'IN_PROGRESS')
          AND t.pickup_time >= :window_start
          AND t.pickup_time <= :window_end
    """)

    busy_rows = db.execute(sql, {"window_start": window_start, "window_end": window_end})
    busy_ids = {row[0] for row in busy_rows}

    # Now filter vehicles in Python (could also be a second raw query, but the
    # vehicle table is small — this keeps the code readable).
    query = db.query(Vehicle).filter(
        Vehicle.status == "AVAILABLE",
        Vehicle.capacity >= pax_count,
    )
    if busy_ids:
        query = query.filter(Vehicle.id.notin_(busy_ids))

    return query.all()


# ---------------------------------------------------------------------------
# Transfers
# ---------------------------------------------------------------------------

def _send_confirmation(transfer_id: int, db_url: str):
    """Background task: log a confirmation notification."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session as RawSession

    eng = create_engine(db_url)
    with RawSession(eng) as session:
        notification = Notification(
            transfer_id=transfer_id,
            message=f"Transfer {transfer_id} has been confirmed. Notification sent.",
        )
        session.add(notification)
        session.commit()
    eng.dispose()
    logger.info("Confirmation notification sent for transfer %s", transfer_id)


@router.post("/transfers", response_model=TransferOut, status_code=201)
def create_transfer(
    payload: TransferCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    # Validate vehicle exists and is available
    vehicle = db.get(Vehicle, payload.vehicle_id)
    if not vehicle:
        raise HTTPException(404, "Vehicle not found.")
    if vehicle.status != "AVAILABLE":
        raise HTTPException(409, f"Vehicle is currently {vehicle.status.value}.")
    if vehicle.capacity < payload.pax_count:
        raise HTTPException(
            422, f"Vehicle capacity ({vehicle.capacity}) < requested pax ({payload.pax_count})."
        )

    # Check for time overlap (reuse availability logic via raw SQL)
    window_start = payload.pickup_time - timedelta(hours=2)
    window_end = payload.pickup_time + timedelta(hours=2)
    conflict = db.execute(
        text("""
            SELECT 1 FROM transfers
            WHERE vehicle_id = :vid
              AND status IN ('CONFIRMED', 'IN_PROGRESS')
              AND pickup_time >= :ws
              AND pickup_time <= :we
            LIMIT 1
        """),
        {"vid": payload.vehicle_id, "ws": window_start, "we": window_end},
    ).fetchone()
    if conflict:
        raise HTTPException(409, "Vehicle is not available at the requested time.")

    transfer = Transfer(**payload.model_dump())
    db.add(transfer)
    db.flush()

    # Log initial status
    db.add(TransferStatusHistory(
        transfer_id=transfer.id,
        old_status=None,
        new_status=TransferStatus.PENDING.value,
    ))
    db.commit()
    db.refresh(transfer)
    return transfer


@router.get("/transfers/{transfer_id}", response_model=TransferDetailOut)
def get_transfer(transfer_id: int, db: Session = Depends(get_db)):
    transfer = (
        db.query(Transfer)
        .options(joinedload(Transfer.status_history))
        .filter(Transfer.id == transfer_id)
        .first()
    )
    if not transfer:
        raise HTTPException(404, "Transfer not found.")
    return transfer


@router.patch("/transfers/{transfer_id}/status", response_model=TransferOut)
def update_transfer_status(
    transfer_id: int,
    payload: StatusUpdate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    transfer = db.get(Transfer, transfer_id)
    if not transfer:
        raise HTTPException(404, "Transfer not found.")

    # Validate transition using domain logic
    error = validate_status_transition(transfer.status, payload.status)
    if error:
        raise HTTPException(409, error)

    # Extra validation for IN_PROGRESS
    if payload.status == TransferStatus.IN_PROGRESS:
        error = validate_in_progress_fields(payload.driver_name)
        if error:
            raise HTTPException(422, error)

    old_status = transfer.status.value
    transfer.status = payload.status

    # Apply optional fields
    if payload.driver_name is not None:
        transfer.driver_name = payload.driver_name
    if payload.estimated_duration_minutes is not None:
        transfer.estimated_duration_minutes = payload.estimated_duration_minutes
    if payload.notes is not None:
        transfer.notes = payload.notes

    db.add(TransferStatusHistory(
        transfer_id=transfer.id,
        old_status=old_status,
        new_status=payload.status.value,
    ))

    db.commit()
    db.refresh(transfer)

    # Fire background notification on CONFIRMED
    if payload.status == TransferStatus.CONFIRMED:
        from app.config import settings
        background_tasks.add_task(_send_confirmation, transfer.id, settings.database_url)

    return transfer


@router.get("/transfers", response_model=list[TransferOut])
def list_transfers(
    date_: date = Query(..., alias="date"),
    db: Session = Depends(get_db),
):
    start = datetime.combine(date_, datetime.min.time())
    end = datetime.combine(date_, datetime.max.time())
    return (
        db.query(Transfer)
        .filter(Transfer.pickup_time >= start, Transfer.pickup_time <= end)
        .order_by(Transfer.pickup_time)
        .all()
    )
