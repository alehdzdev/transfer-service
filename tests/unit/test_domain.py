"""Unit tests for pure business logic — no DB, no HTTP."""

from unittest.mock import MagicMock

import pytest
from sqlalchemy.exc import IntegrityError

from app.domain import validate_in_progress_fields, validate_status_transition
from app.enums import TransferStatus, VehicleType
from app.exceptions import ConflictError
from app.schemas import VehicleCreate
from app.services.vehicle_service import create_vehicle


class TestStatusTransitions:
    """Cancellation constraint:
    A transfer may only be CANCELLED from PENDING or CONFIRMED.
    IN_PROGRESS and COMPLETED transfers cannot be cancelled.
    """

    @pytest.mark.unit
    @pytest.mark.parametrize(
        "current,new",
        [
            (TransferStatus.PENDING, TransferStatus.CONFIRMED),
            (TransferStatus.PENDING, TransferStatus.CANCELLED),
            (TransferStatus.CONFIRMED, TransferStatus.IN_PROGRESS),
            (TransferStatus.CONFIRMED, TransferStatus.CANCELLED),
            (TransferStatus.IN_PROGRESS, TransferStatus.COMPLETED),
        ],
    )
    def test_valid_transitions(self, current, new):
        assert validate_status_transition(current, new) is None

    @pytest.mark.unit
    @pytest.mark.parametrize(
        "current,new",
        [
            (TransferStatus.IN_PROGRESS, TransferStatus.CANCELLED),
            (TransferStatus.COMPLETED, TransferStatus.CANCELLED),
            (TransferStatus.COMPLETED, TransferStatus.PENDING),
            (TransferStatus.CANCELLED, TransferStatus.PENDING),
            (TransferStatus.PENDING, TransferStatus.IN_PROGRESS),
            (TransferStatus.PENDING, TransferStatus.COMPLETED),
        ],
    )
    def test_invalid_transitions(self, current, new):
        error = validate_status_transition(current, new)
        assert error is not None

    @pytest.mark.unit
    def test_cancel_in_progress_message(self):
        error = validate_status_transition(
            TransferStatus.IN_PROGRESS, TransferStatus.CANCELLED
        )
        assert "CANCELLED" not in error or "only allowed" in error.lower()

    @pytest.mark.unit
    def test_cancel_completed_message(self):
        error = validate_status_transition(
            TransferStatus.COMPLETED, TransferStatus.CANCELLED
        )
        assert error is not None


class TestInProgressValidation:
    @pytest.mark.unit
    def test_driver_name_required(self):
        assert validate_in_progress_fields(None) is not None
        assert validate_in_progress_fields("") is not None
        assert validate_in_progress_fields("  ") is not None

    @pytest.mark.unit
    def test_driver_name_provided(self):
        assert validate_in_progress_fields("John Doe") is None


class TestCreateVehicle:
    """Unit tests for create_vehicle — DB session is fully mocked."""

    PAYLOAD = VehicleCreate(
        type=VehicleType.SEDAN,
        capacity=4,
        plate_number="ABC-123",
    )

    @pytest.mark.unit
    def test_create_vehicle_success(self):
        db = MagicMock()
        vehicle = create_vehicle(db, self.PAYLOAD)

        db.add.assert_called_once()
        db.commit.assert_called_once()
        db.refresh.assert_called_once_with(vehicle)

    @pytest.mark.unit
    def test_create_vehicle_duplicate_plate_raises_conflict(self):
        db = MagicMock()
        db.commit.side_effect = IntegrityError("dup", params=None, orig=Exception())

        with pytest.raises(ConflictError, match="plate number.*ABC-123"):
            create_vehicle(db, self.PAYLOAD)

        db.rollback.assert_called_once()
