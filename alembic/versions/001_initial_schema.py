"""Initial schema — vehicles, transfers, status history, notifications

Revision ID: 001
Revises:
Create Date: 2026-04-03
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "vehicles",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("type", sa.Enum("SEDAN", "VAN", "BUS", name="vehicletype"), nullable=False),
        sa.Column("capacity", sa.Integer, nullable=False),
        sa.Column("plate_number", sa.String(20), unique=True, nullable=False),
        sa.Column(
            "status",
            sa.Enum("AVAILABLE", "IN_USE", "MAINTENANCE", name="vehiclestatus"),
            nullable=False,
            server_default="AVAILABLE",
        ),
    )

    op.create_table(
        "transfers",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("vehicle_id", sa.Integer, sa.ForeignKey("vehicles.id"), nullable=False),
        sa.Column("passenger_name", sa.String(200), nullable=False),
        sa.Column("flight_number", sa.String(20), nullable=False),
        sa.Column("pickup_time", sa.DateTime, nullable=False),
        sa.Column("pickup_location", sa.String(300), nullable=False),
        sa.Column("dropoff_location", sa.String(300), nullable=False),
        sa.Column("pax_count", sa.Integer, nullable=False),
        sa.Column(
            "status",
            sa.Enum("PENDING", "CONFIRMED", "IN_PROGRESS", "COMPLETED", "CANCELLED", name="transferstatus"),
            nullable=False,
            server_default="PENDING",
        ),
    )

    # Index 1: composite index for the availability query
    # Serves: GET /availability — filters by vehicle_id + pickup_time range + status.
    # The leftmost column is vehicle_id so MySQL can use this index when joining
    # or filtering per-vehicle, then range-scan on pickup_time, then filter on status.
    op.create_index(
        "ix_transfer_vehicle_pickup_status",
        "transfers",
        ["vehicle_id", "pickup_time", "status"],
    )

    # Index 2: standalone index on pickup_time
    # Serves: GET /transfers?date=YYYY-MM-DD — filters only by pickup_time range.
    # Cannot rely on the composite index above because vehicle_id is not in the
    # WHERE clause, violating the leftmost-prefix rule.
    op.create_index("ix_transfer_pickup_time", "transfers", ["pickup_time"])

    op.create_table(
        "transfer_status_history",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("transfer_id", sa.Integer, sa.ForeignKey("transfers.id"), nullable=False),
        sa.Column("old_status", sa.String(20), nullable=True),
        sa.Column("new_status", sa.String(20), nullable=False),
        sa.Column("changed_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("transfer_id", sa.Integer, sa.ForeignKey("transfers.id"), nullable=False),
        sa.Column("message", sa.Text, nullable=False),
        sa.Column("sent_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("notifications")
    op.drop_table("transfer_status_history")
    op.drop_index("ix_transfer_pickup_time", table_name="transfers")
    op.drop_index("ix_transfer_vehicle_pickup_status", table_name="transfers")
    op.drop_table("transfers")
    op.drop_table("vehicles")
