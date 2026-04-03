"""Request logging middleware.

Logs method, path, status code, and duration for every request in a
structured key=value format that's easy to parse in log aggregators.
"""

import logging
import time

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("app.access")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = (time.perf_counter() - start) * 1000

        logger.info(
            'method=%s path="%s" status=%d duration_ms=%.1f',
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
        )
        return response
