"""Domain exceptions — decoupled from HTTP.

Services raise these; the FastAPI exception handler maps them to HTTP
responses. This means the same service code works behind a CLI, a
message consumer, or any other entry point without dragging in HTTPException.
"""


class ServiceError(Exception):
    """Base for all domain/service errors."""

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


class NotFoundError(ServiceError):
    """Requested resource does not exist."""


class ConflictError(ServiceError):
    """Action conflicts with current state (e.g. invalid status transition)."""


class ValidationError(ServiceError):
    """Domain-level validation failure (not Pydantic schema validation)."""
