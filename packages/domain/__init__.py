"""
Aegis Domain Package.
Exposes domain entities, aggregates, exceptions, persistence ports,
and intelligence value objects.
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
from .intelligence import (
    AnomalyDetectionResult,
    AnomalySeverity,
    AnomalyStatus,
    HealthAssessment,
    OperationalState,
    SensorSignal,
    SignalEvidence,
    TrendDirection,
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
    "AnomalyDetectionResult",
    "AnomalySeverity",
    "AnomalyStatus",
    "Asset",
    "Device",
    "DeviceRegistry",
    "DuplicateEntityError",
    "EntityNotFoundError",
    "EntityStatus",
    "HealthAssessment",
    "InMemoryDeviceRegistry",
    "InMemoryTelemetryRepository",
    "InMemoryWorldRepository",
    "InvariantViolationError",
    "Observation",
    "OperationalState",
    "QualityFlag",
    "Sensor",
    "SensorSignal",
    "SignalEvidence",
    "TelemetryRepository",
    "TrendDirection",
    "World",
    "WorldModel",
    "WorldRepository",
]
