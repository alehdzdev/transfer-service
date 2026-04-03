"""Add driver_name, estimated_duration_minutes, notes to transfers

Revision ID: 002
Revises: 001
Create Date: 2026-04-03
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("transfers", sa.Column("driver_name", sa.String(100), nullable=True))
    op.add_column("transfers", sa.Column("estimated_duration_minutes", sa.Integer, nullable=True))
    op.add_column("transfers", sa.Column("notes", sa.Text, nullable=True))


def downgrade() -> None:
    op.drop_column("transfers", "notes")
    op.drop_column("transfers", "estimated_duration_minutes")
    op.drop_column("transfers", "driver_name")
