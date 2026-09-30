"""
Aegis Domain Package.

Exposes domain entities, aggregates, exceptions, and persistence ports.
"""

from .entities import (
    Asset,
    Device,
    EntityStatus,
    Observation,
    QualityFlag,
    Sensor,
    World,
)
from .exceptions import (
    DuplicateEntityError,
    EntityNotFoundError,
    InvariantViolationError,
)
from .model import WorldModel
from .repository import (
    DeviceRegistry,
    InMemoryDeviceRegistry,
    InMemoryTelemetryRepository,
    InMemoryWorldRepository,
    TelemetryRepository,
    WorldRepository,
)

__all__ = [
    "Asset",
    "Device",
    "DeviceRegistry",
    "DuplicateEntityError",
    "EntityNotFoundError",
    "EntityStatus",
    "InMemoryDeviceRegistry",
    "InMemoryTelemetryRepository",
    "InMemoryWorldRepository",
    "InvariantViolationError",
    "Observation",
    "QualityFlag",
    "Sensor",
    "TelemetryRepository",
    "World",
    "WorldModel",
    "WorldRepository",
]
