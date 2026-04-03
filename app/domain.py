"""Pure business rules — no DB, no HTTP. Testable in isolation."""

from app.enums import TransferStatus

# Valid status transitions: current_status -> set of allowed next statuses.
VALID_TRANSITIONS: dict[TransferStatus, set[TransferStatus]] = {
    TransferStatus.PENDING: {TransferStatus.CONFIRMED, TransferStatus.CANCELLED},
    TransferStatus.CONFIRMED: {TransferStatus.IN_PROGRESS, TransferStatus.CANCELLED},
    TransferStatus.IN_PROGRESS: {TransferStatus.COMPLETED},
    TransferStatus.COMPLETED: set(),
    TransferStatus.CANCELLED: set(),
}


def validate_status_transition(current: TransferStatus, new: TransferStatus) -> str | None:
    """Return an error message if the transition is invalid, else None."""
    allowed = VALID_TRANSITIONS.get(current, set())
    if new not in allowed:
        if new == TransferStatus.CANCELLED:
            return (
                f"Cannot cancel a transfer that is {current.value}. "
                "Cancellation is only allowed from PENDING or CONFIRMED."
            )
        return f"Cannot transition from {current.value} to {new.value}."
    return None


def validate_in_progress_fields(driver_name: str | None) -> str | None:
    """When moving to IN_PROGRESS, driver_name is required."""
    if not driver_name or not driver_name.strip():
        return "driver_name is required when transitioning to IN_PROGRESS."
    return None
