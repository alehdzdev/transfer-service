"""Transfer service — booking lifecycle and status management."""

import logging
from datetime import date, datetime

from sqlalchemy.orm import Session, joinedload

from app.domain import validate_in_progress_fields, validate_status_transition
from app.enums import TransferStatus
from app.exceptions import ConflictError, NotFoundError, ValidationError
from app.models import Transfer, TransferStatusHistory
from app.schemas import StatusUpdate, TransferCreate
from app.services import vehicle_service

logger = logging.getLogger(__name__)


def create_transfer(db: Session, payload: TransferCreate) -> Transfer:
    """Create a new transfer booking after validating vehicle availability."""
    vehicle_service.check_vehicle_bookable(db, payload.vehicle_id, payload.pax_count)
    vehicle_service.check_time_conflict(db, payload.vehicle_id, payload.pickup_time)

    transfer = Transfer(**payload.model_dump())
    db.add(transfer)
    db.flush()

    db.add(TransferStatusHistory(
        transfer_id=transfer.id,
        old_status=None,
        new_status=TransferStatus.PENDING.value,
    ))
    db.commit()
    db.refresh(transfer)
    return transfer


def get_transfer(db: Session, transfer_id: int) -> Transfer:
    """Fetch a single transfer with its status history. Raises NotFoundError."""
    transfer = (
        db.query(Transfer)
        .options(joinedload(Transfer.status_history))
        .filter(Transfer.id == transfer_id)
        .first()
    )
    if not transfer:
        raise NotFoundError("Transfer not found.")
    return transfer


def list_transfers_by_date(db: Session, date_: date) -> list[Transfer]:
    start = datetime.combine(date_, datetime.min.time())
    end = datetime.combine(date_, datetime.max.time())
    return (
        db.query(Transfer)
        .filter(Transfer.pickup_time >= start, Transfer.pickup_time <= end)
        .order_by(Transfer.pickup_time)
        .all()
    )


def update_status(db: Session, transfer_id: int, payload: StatusUpdate) -> Transfer:
    """Advance transfer status. Returns the updated transfer.

    Business rules:
    - Only PENDING/CONFIRMED can be CANCELLED.
    - IN_PROGRESS requires driver_name.
    - Every transition is logged in transfer_status_history.
    """
    transfer = db.get(Transfer, transfer_id)
    if not transfer:
        raise NotFoundError("Transfer not found.")

    error = validate_status_transition(transfer.status, payload.status)
    if error:
        raise ConflictError(error)

    if payload.status == TransferStatus.IN_PROGRESS:
        error = validate_in_progress_fields(payload.driver_name)
        if error:
            raise ValidationError(error)

    old_status = transfer.status.value
    transfer.status = payload.status

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
    return transfer
