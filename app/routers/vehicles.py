"""Vehicle endpoints — registration and availability checks."""

from datetime import date, datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import VehicleCreate, VehicleOut
from app.services import vehicle_service

router = APIRouter(prefix="/vehicles", tags=["Vehicles"])


@router.post("", response_model=VehicleOut, status_code=201)
def create_vehicle(payload: VehicleCreate, db: Session = Depends(get_db)):
    return vehicle_service.create_vehicle(db, payload)


# Availability lives here because the result type is a list of vehicles.
availability_router = APIRouter(tags=["Availability"])


@availability_router.get("/availability", response_model=list[VehicleOut])
def check_availability(
    date_: date = Query(..., alias="date"),
    pax_count: int = Query(..., gt=0),
    pickup_time: datetime | None = Query(default=None),
    db: Session = Depends(get_db),
):
    return vehicle_service.find_available(db, date_, pax_count, pickup_time)
