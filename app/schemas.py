from datetime import datetime

from pydantic import BaseModel, Field

from app.models import TransferStatus, VehicleStatus, VehicleType


# --- Vehicle ---

class VehicleCreate(BaseModel):
    type: VehicleType
    capacity: int = Field(gt=0)
    plate_number: str = Field(min_length=1, max_length=20)
    status: VehicleStatus = VehicleStatus.AVAILABLE


class VehicleOut(BaseModel):
    id: int
    type: VehicleType
    capacity: int
    plate_number: str
    status: VehicleStatus

    model_config = {"from_attributes": True}


# --- Transfer ---

class TransferCreate(BaseModel):
    vehicle_id: int
    passenger_name: str = Field(min_length=1, max_length=200)
    flight_number: str = Field(min_length=1, max_length=20)
    pickup_time: datetime
    pickup_location: str = Field(min_length=1, max_length=300)
    dropoff_location: str = Field(min_length=1, max_length=300)
    pax_count: int = Field(gt=0)


class StatusHistoryOut(BaseModel):
    id: int
    old_status: str | None
    new_status: str
    changed_at: datetime

    model_config = {"from_attributes": True}


class TransferOut(BaseModel):
    id: int
    vehicle_id: int
    passenger_name: str
    flight_number: str
    pickup_time: datetime
    pickup_location: str
    dropoff_location: str
    pax_count: int
    status: TransferStatus
    driver_name: str | None = None
    estimated_duration_minutes: int | None = None
    notes: str | None = None

    model_config = {"from_attributes": True}


class TransferDetailOut(TransferOut):
    status_history: list[StatusHistoryOut] = []


class StatusUpdate(BaseModel):
    status: TransferStatus
    driver_name: str | None = Field(default=None, max_length=100)
    estimated_duration_minutes: int | None = Field(default=None, gt=0)
    notes: str | None = None
