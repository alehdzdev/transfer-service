"""Unit tests for service layer — uses DB session but no HTTP.

These verify that services raise the correct domain exceptions
rather than HTTPException, which is key to the layered architecture.
"""

import pytest
from datetime import datetime

from app.enums import TransferStatus
from app.exceptions import ConflictError, NotFoundError, ValidationError
from app.schemas import StatusUpdate, TransferCreate, VehicleCreate
from app.services import transfer_service, vehicle_service


@pytest.mark.integration
class TestVehicleService:
    def test_check_vehicle_bookable_not_found(self, db_session):
        with pytest.raises(NotFoundError, match="Vehicle not found"):
            vehicle_service.check_vehicle_bookable(db_session, 9999, 2)

    def test_check_vehicle_bookable_maintenance(self, db_session):
        v = vehicle_service.create_vehicle(
            db_session, VehicleCreate(type="SEDAN", capacity=4, plate_number="SVC-1", status="MAINTENANCE")
        )
        with pytest.raises(ConflictError, match="MAINTENANCE"):
            vehicle_service.check_vehicle_bookable(db_session, v.id, 2)

    def test_check_vehicle_bookable_capacity(self, db_session):
        v = vehicle_service.create_vehicle(
            db_session, VehicleCreate(type="SEDAN", capacity=2, plate_number="SVC-2")
        )
        with pytest.raises(ConflictError, match="capacity"):
            vehicle_service.check_vehicle_bookable(db_session, v.id, 5)


@pytest.mark.integration
class TestTransferService:
    def _make_vehicle_and_transfer(self, db_session):
        v = vehicle_service.create_vehicle(
            db_session, VehicleCreate(type="VAN", capacity=8, plate_number="SVC-3")
        )
        t = transfer_service.create_transfer(db_session, TransferCreate(
            vehicle_id=v.id,
            passenger_name="Test",
            flight_number="XX1",
            pickup_time=datetime(2026, 9, 1, 10, 0),
            pickup_location="Airport",
            dropoff_location="Hotel",
            pax_count=3,
        ))
        return t

    def test_create_transfer_returns_pending(self, db_session):
        t = self._make_vehicle_and_transfer(db_session)
        assert t.status == TransferStatus.PENDING

    def test_update_status_not_found(self, db_session):
        with pytest.raises(NotFoundError):
            transfer_service.update_status(
                db_session, 9999, StatusUpdate(status=TransferStatus.CONFIRMED)
            )

    def test_update_status_invalid_transition(self, db_session):
        t = self._make_vehicle_and_transfer(db_session)
        with pytest.raises(ConflictError):
            transfer_service.update_status(
                db_session, t.id, StatusUpdate(status=TransferStatus.COMPLETED)
            )

    def test_in_progress_without_driver_raises_validation(self, db_session):
        t = self._make_vehicle_and_transfer(db_session)
        transfer_service.update_status(
            db_session, t.id, StatusUpdate(status=TransferStatus.CONFIRMED)
        )
        with pytest.raises(ValidationError, match="driver_name"):
            transfer_service.update_status(
                db_session, t.id, StatusUpdate(status=TransferStatus.IN_PROGRESS)
            )

    def test_get_transfer_not_found(self, db_session):
        with pytest.raises(NotFoundError):
            transfer_service.get_transfer(db_session, 9999)
