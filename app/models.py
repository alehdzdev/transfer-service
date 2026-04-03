from datetime import datetime

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.enums import TransferStatus, VehicleStatus, VehicleType


class Vehicle(Base):
    __tablename__ = "vehicles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    type: Mapped[VehicleType] = mapped_column(Enum(VehicleType), nullable=False)
    capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    plate_number: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    status: Mapped[VehicleStatus] = mapped_column(
        Enum(VehicleStatus), nullable=False, default=VehicleStatus.AVAILABLE
    )

    transfers: Mapped[list["Transfer"]] = relationship(back_populates="vehicle")


class Transfer(Base):
    __tablename__ = "transfers"
    __table_args__ = (
        # Index 1: Speeds up the availability query which filters transfers by
        # vehicle_id + pickup_time range + status. Composite index lets MySQL
        # satisfy the WHERE clause in a single B-tree scan instead of doing a
        # full table scan or intersecting separate indexes.
        Index("ix_transfer_vehicle_pickup_status", "vehicle_id", "pickup_time", "status"),
        # Index 2: Speeds up GET /transfers?date=YYYY-MM-DD which filters by
        # pickup_time date. A standalone index on pickup_time is better than
        # relying on the composite index above because the date-list query
        # does not filter by vehicle_id, so the composite index would not be
        # usable (leftmost-prefix rule).
        Index("ix_transfer_pickup_time", "pickup_time"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    vehicle_id: Mapped[int] = mapped_column(ForeignKey("vehicles.id"), nullable=False)
    passenger_name: Mapped[str] = mapped_column(String(200), nullable=False)
    flight_number: Mapped[str] = mapped_column(String(20), nullable=False)
    pickup_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    pickup_location: Mapped[str] = mapped_column(String(300), nullable=False)
    dropoff_location: Mapped[str] = mapped_column(String(300), nullable=False)
    pax_count: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[TransferStatus] = mapped_column(
        Enum(TransferStatus), nullable=False, default=TransferStatus.PENDING
    )
    driver_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    estimated_duration_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    vehicle: Mapped["Vehicle"] = relationship(back_populates="transfers")
    status_history: Mapped[list["TransferStatusHistory"]] = relationship(
        back_populates="transfer", order_by="TransferStatusHistory.changed_at"
    )


class TransferStatusHistory(Base):
    __tablename__ = "transfer_status_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    transfer_id: Mapped[int] = mapped_column(ForeignKey("transfers.id"), nullable=False)
    old_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    new_status: Mapped[str] = mapped_column(String(20), nullable=False)
    changed_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

    transfer: Mapped["Transfer"] = relationship(back_populates="status_history")


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    transfer_id: Mapped[int] = mapped_column(ForeignKey("transfers.id"), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    sent_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
