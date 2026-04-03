"""Unit tests for pure business logic — no DB, no HTTP."""

import pytest

from app.domain import validate_in_progress_fields, validate_status_transition
from app.models import TransferStatus


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
        error = validate_status_transition(TransferStatus.IN_PROGRESS, TransferStatus.CANCELLED)
        assert "CANCELLED" not in error or "only allowed" in error.lower()

    @pytest.mark.unit
    def test_cancel_completed_message(self):
        error = validate_status_transition(TransferStatus.COMPLETED, TransferStatus.CANCELLED)
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
