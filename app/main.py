import logging

from fastapi import FastAPI

from app.config import settings
from app.error_handlers import register_error_handlers
from app.middleware import RequestLoggingMiddleware
from app.routers.transfers import router as transfers_router
from app.routers.vehicles import availability_router, router as vehicles_router

logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
)

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="Backend service for a DMC that manages airport transfer bookings.",
)

register_error_handlers(app)
app.add_middleware(RequestLoggingMiddleware)

app.include_router(vehicles_router)
app.include_router(availability_router)
app.include_router(transfers_router)
