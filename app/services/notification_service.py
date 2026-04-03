"""Notification service — handles async notifications via background tasks.

Uses the existing SessionLocal factory instead of creating a new engine
per invocation (the old code did create_engine() per call, which is
expensive and leaks connection pools under load).
"""

import logging

from app.database import SessionLocal
from app.models import Notification

logger = logging.getLogger(__name__)


def send_confirmation(transfer_id: int) -> None:
    """Log a confirmation notification to the database.

    Designed to run as a FastAPI BackgroundTask — uses its own session
    because the request session is already closed by the time this executes.
    """
    with SessionLocal() as session:
        notification = Notification(
            transfer_id=transfer_id,
            message=f"Transfer {transfer_id} has been confirmed. Notification sent.",
        )
        session.add(notification)
        session.commit()
    logger.info("Confirmation notification sent for transfer %s", transfer_id)
