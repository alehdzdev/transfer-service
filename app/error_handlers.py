"""Map domain exceptions to structured HTTP responses.

Response shape:
    {"error": {"type": "not_found", "message": "Vehicle not found."}}

This gives clients a machine-readable `type` field they can switch on,
instead of parsing a bare detail string.
"""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.exceptions import ConflictError, NotFoundError, ServiceError, ValidationError

_STATUS_MAP: dict[type[ServiceError], tuple[int, str]] = {
    NotFoundError: (404, "not_found"),
    ConflictError: (409, "conflict"),
    ValidationError: (422, "validation_error"),
}


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ServiceError)
    async def _handle_service_error(request: Request, exc: ServiceError) -> JSONResponse:
        status, error_type = _STATUS_MAP.get(type(exc), (500, "internal_error"))
        return JSONResponse(
            status_code=status,
            content={"detail": exc.message, "error": {"type": error_type, "message": exc.message}},
        )
