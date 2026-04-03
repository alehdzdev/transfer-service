"""Vehicle service — all DB interaction for the vehicle domain."""

from datetime import date, datetime, timedelta

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.enums import VehicleStatus
from app.exceptions import ConflictError
from app.models import Vehicle
from app.schemas import VehicleCreate


def create_vehicle(db: Session, payload: VehicleCreate) -> Vehicle:
    vehicle = Vehicle(**payload.model_dump())
    db.add(vehicle)
    db.commit()
    db.refresh(vehicle)
    return vehicle


def find_available(
    db: Session,
    date_: date,
    pax_count: int,
    pickup_time: datetime | None = None,
) -> list[Vehicle]:
    """Return vehicles available for the given date and passenger count.

    Uses raw SQL (SQLAlchemy text()) for the overlap check.

    A vehicle is available when:
    1. Its status is AVAILABLE
    2. Its capacity >= pax_count
    3. It has no CONFIRMED or IN_PROGRESS transfer whose pickup_time falls
       within a 2-hour window around the requested pickup_time.

    If pickup_time is not supplied, the window spans the full day.
    """
    if pickup_time is not None:
        window_start = pickup_time - timedelta(hours=2)
        window_end = pickup_time + timedelta(hours=2)
    else:
        window_start = datetime.combine(date_, datetime.min.time())
        window_end = datetime.combine(date_, datetime.max.time())

    sql = text("""
        SELECT DISTINCT t.vehicle_id
        FROM transfers t
        WHERE t.status IN ('CONFIRMED', 'IN_PROGRESS')
          AND t.pickup_time >= :window_start
          AND t.pickup_time <= :window_end
    """)

    busy_rows = db.execute(sql, {"window_start": window_start, "window_end": window_end})
    busy_ids = {row[0] for row in busy_rows}

    query = db.query(Vehicle).filter(
        Vehicle.status == VehicleStatus.AVAILABLE,
        Vehicle.capacity >= pax_count,
    )
    if busy_ids:
        query = query.filter(Vehicle.id.notin_(busy_ids))

    return query.all()


def check_vehicle_bookable(db: Session, vehicle_id: int, pax_count: int) -> Vehicle:
    """Validate a vehicle exists, is AVAILABLE, and has sufficient capacity.

    Raises NotFoundError or ConflictError on failure.
    """
    from app.exceptions import NotFoundError

    vehicle = db.get(Vehicle, vehicle_id)
    if not vehicle:
        raise NotFoundError("Vehicle not found.")
    if vehicle.status != VehicleStatus.AVAILABLE:
        raise ConflictError(f"Vehicle is currently {vehicle.status.value}.")
    if vehicle.capacity < pax_count:
        raise ConflictError(
            f"Vehicle capacity ({vehicle.capacity}) < requested pax ({pax_count})."
        )
    return vehicle


def check_time_conflict(db: Session, vehicle_id: int, pickup_time: datetime) -> None:
    """Raise ConflictError if the vehicle has a conflicting booking."""
    window_start = pickup_time - timedelta(hours=2)
    window_end = pickup_time + timedelta(hours=2)
    conflict = db.execute(
        text("""
            SELECT 1 FROM transfers
            WHERE vehicle_id = :vid
              AND status IN ('CONFIRMED', 'IN_PROGRESS')
              AND pickup_time >= :ws
              AND pickup_time <= :we
            LIMIT 1
        """),
        {"vid": vehicle_id, "ws": window_start, "we": window_end},
    ).fetchone()
    if conflict:
        raise ConflictError("Vehicle is not available at the requested time.")
