"""
Aegis Intelligence Domain Value Objects (P2.S1 + P2.S2).
Immutable snapshots for operational state, health, anomaly detection,
and explainable degradation evidence.
"""
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any


class OperationalState(StrEnum):
    """High-level operational condition of an asset (P2.S1)."""
    NORMAL = "NORMAL"
    DEGRADING = "DEGRADING"
    CRITICAL = "CRITICAL"
    UNKNOWN = "UNKNOWN"


class TrendDirection(StrEnum):
    """Direction of a measurement signal over a time window."""
    STABLE = "STABLE"
    INCREASING = "INCREASING"
    DECREASING = "DECREASING"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class SensorSignal:
    """Per-sensor evidence contributing to an asset health assessment (P2.S1)."""
    sensor_id: str
    measurement_type: str
    baseline_mean: float
    baseline_std: float
    current_mean: float
    deviation_score: float
    trend: TrendDirection
    data_quality: float
    sample_count: int
    insufficient_data: bool = False


@dataclass(frozen=True)
class HealthAssessment:
    """Immutable snapshot of an asset's operational health at a point in time (P2.S1)."""
    asset_id: str
    device_id: str
    operational_state: OperationalState
    health_score: float
    confidence: float
    trend: TrendDirection
    sensor_signals: tuple[SensorSignal, ...]
    evaluated_at: datetime
    evidence_summary: str
    metadata: dict[str, Any] = field(default_factory=dict)


# =========================================================================
# P2.S2 Anomaly & Degradation Types
# =========================================================================

class AnomalyStatus(StrEnum):
    """Classification of detected abnormal behavior (P2.S2)."""
    NOMINAL = "NOMINAL"
    ANOMALY_DETECTED = "ANOMALY_DETECTED"
    DEGRADATION_DETECTED = "DEGRADATION_DETECTED"
    UNKNOWN = "UNKNOWN"


class AnomalySeverity(StrEnum):
    """Operational impact severity of detected anomalies (P2.S2)."""
    NONE = "NONE"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


@dataclass(frozen=True)
class SignalEvidence:
    """Detailed explainable evidence per deviating sensor (P2.S2)."""
    sensor_id: str
    measurement_type: str
    deviation_sigma: float
    trend: TrendDirection
    persistence_count: int
    contribution_score: float
    reason: str


@dataclass(frozen=True)
class AnomalyDetectionResult:
    """Immutable result of multi-signal anomaly and degradation detection (P2.S2)."""
    asset_id: str
    device_id: str
    status: AnomalyStatus
    anomaly_score: float         # Normalized 0.0 to 1.0 (1.0 = highly anomalous)
    confidence: float            # 0.0 to 1.0 (certainty in detection)
    severity: AnomalySeverity
    evidence_list: tuple[SignalEvidence, ...]
    evaluated_at: datetime
    detection_method: str
    lead_cycles_estimate: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
