"""Transfer endpoints — booking lifecycle."""

from datetime import date

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.enums import TransferStatus
from app.schemas import StatusUpdate, TransferCreate, TransferDetailOut, TransferOut
from app.services import notification_service, transfer_service

router = APIRouter(prefix="/transfers", tags=["Transfers"])


@router.post("", response_model=TransferOut, status_code=201)
def create_transfer(
    payload: TransferCreate,
    db: Session = Depends(get_db),
):
    return transfer_service.create_transfer(db, payload)


@router.get("/{transfer_id}", response_model=TransferDetailOut)
def get_transfer(transfer_id: int, db: Session = Depends(get_db)):
    return transfer_service.get_transfer(db, transfer_id)


@router.patch("/{transfer_id}/status", response_model=TransferOut)
def update_transfer_status(
    transfer_id: int,
    payload: StatusUpdate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    transfer = transfer_service.update_status(db, transfer_id, payload)

    if payload.status == TransferStatus.CONFIRMED:
        background_tasks.add_task(notification_service.send_confirmation, transfer.id)

    return transfer


@router.get("", response_model=list[TransferOut])
def list_transfers(
    date_: date = Query(..., alias="date"),
    db: Session = Depends(get_db),
):
    return transfer_service.list_transfers_by_date(db, date_)
