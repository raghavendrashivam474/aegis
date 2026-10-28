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
    DiagnosticContext,
    DiagnosticEvidence,
    DiagnosticHypothesis,
    DiagnosticResult,
    DiagnosticStatus,
    HealthAssessment,
    HypothesisCategory,
    OperationalFinding,
    OperationalPriority,
    OperationalState,
    SensorSignal,
    SignalEvidence,
    TrendDirection,
)
from .model import WorldModel
from .repository import (
    DeviceRegistry,
    InMemoryDeviceRegistry,
    InMemorySnapshotRepository,
    InMemoryTelemetryRepository,
    InMemoryWorldRepository,
    IntelligenceSnapshotRepository,
    TelemetryRepository,
    WorldRepository,
)
from .snapshot import (
    SNAPSHOT_CONTRACT_VERSION,
    EvaluationStatus,
    IntelligenceSnapshot,
)

__all__ = [
    "AnomalyDetectionResult",
    "AnomalySeverity",
    "AnomalyStatus",
    "Asset",
    "Device",
    "DeviceRegistry",
    "DiagnosticContext",
    "DiagnosticEvidence",
    "DiagnosticHypothesis",
    "DiagnosticResult",
    "DiagnosticStatus",
    "DuplicateEntityError",
    "EntityNotFoundError",
    "EntityStatus",
    "HealthAssessment",
    "HypothesisCategory",
    "InMemoryDeviceRegistry",
    "InMemoryTelemetryRepository",
    "InMemorySnapshotRepository",
    "IntelligenceSnapshotRepository",
    "InMemoryWorldRepository",
    "InvariantViolationError",
    "Observation",
    "OperationalFinding",
    "OperationalPriority",
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
    "EvaluationStatus",
    "IntelligenceSnapshot",
    "SNAPSHOT_CONTRACT_VERSION",
]
