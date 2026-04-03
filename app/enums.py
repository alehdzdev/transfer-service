"""Domain enums — no ORM dependency.

These live outside models.py so that schemas, domain logic, and services
can import them without pulling in SQLAlchemy.
"""

import enum


class VehicleType(str, enum.Enum):
    SEDAN = "SEDAN"
    VAN = "VAN"
    BUS = "BUS"


class VehicleStatus(str, enum.Enum):
    AVAILABLE = "AVAILABLE"
    IN_USE = "IN_USE"
    MAINTENANCE = "MAINTENANCE"


class TransferStatus(str, enum.Enum):
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
