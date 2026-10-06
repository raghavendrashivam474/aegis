"""
Aegis Intelligence Domain Value Objects (P2.S1 + P2.S2 + P2.S3 + P2.S4).
Immutable snapshots for operational state, health, anomaly detection,
explainable degradation evidence, deterministic root-cause hypotheses,
and prioritized operational findings.
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


# =========================================================================
# P2.S3 Context, Risk, Evidence & Root-Cause Hypotheses Types
# =========================================================================

class DiagnosticStatus(StrEnum):
    """Operational diagnostic classification (P2.S3)."""
    NOMINAL = "NOMINAL"
    INVESTIGATING = "INVESTIGATING"
    LIKELY_DEGRADATION = "LIKELY_DEGRADATION"
    MULTIPLE_POSSIBLE_CAUSES = "MULTIPLE_POSSIBLE_CAUSES"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    UNKNOWN = "UNKNOWN"


class HypothesisCategory(StrEnum):
    """Subsystem and fault pattern categories for diagnostic hypotheses (P2.S3)."""
    NOMINAL = "NOMINAL"
    THERMAL_DEGRADATION = "THERMAL_DEGRADATION"
    MECHANICAL_DEGRADATION = "MECHANICAL_DEGRADATION"
    PRESSURE_FLOW_DEGRADATION = "PRESSURE_FLOW_DEGRADATION"
    SYSTEMIC_MULTI_SUBSYSTEM = "SYSTEMIC_MULTI_SUBSYSTEM"
    LOCALIZED_SENSOR_ANOMALY = "LOCALIZED_SENSOR_ANOMALY"
    TRANSIENT_DISTURBANCE = "TRANSIENT_DISTURBANCE"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class DiagnosticEvidence:
    """Structured, inspectable per-signal evidence for diagnosis (P2.S3)."""
    sensor_id: str
    measurement_type: str
    observation: str
    deviation_sigma: float
    trend: TrendDirection
    persistence_count: int
    data_quality: float
    contribution_score: float
    reason: str


@dataclass(frozen=True)
class DiagnosticHypothesis:
    """Deterministic, probabilistic explanation of observed anomalies (P2.S3)."""
    category: HypothesisCategory
    description: str
    confidence: float                      # 0.0 to 1.0 strength of evidence for this hypothesis
    supporting_evidence: tuple[str, ...]   # Human/machine readable supporting evidence points
    contradicting_evidence: tuple[str, ...] # Observed signals that conflict with or weaken hypothesis
    severity: AnomalySeverity


@dataclass(frozen=True)
class DiagnosticContext:
    """Operating circumstances and upstream telemetry status snapshot (P2.S3)."""
    operational_state: OperationalState
    health_score: float
    health_confidence: float
    anomaly_status: AnomalyStatus
    anomaly_score: float
    anomaly_severity: AnomalySeverity
    total_sensors: int
    affected_sensors: int
    dominant_trend: TrendDirection
    max_persistence: int


@dataclass(frozen=True)
class DiagnosticResult:
    """
    Immutable structured diagnostic result (P2.S3).
    Binds upstream health + anomaly context, structured evidence, deterministic
    hypotheses, evidentiary confidence, and explicit epistemic limitations.
    """
    asset_id: str
    device_id: str
    status: DiagnosticStatus
    overall_risk: AnomalySeverity
    context: DiagnosticContext
    evidence: tuple[DiagnosticEvidence, ...]
    hypotheses: tuple[DiagnosticHypothesis, ...]
    primary_hypothesis: DiagnosticHypothesis | None
    confidence: float                      # Evidentiary confidence (0.0 to 1.0)
    primary_finding: str
    limitations: str
    evaluated_at: datetime
    diagnostic_method: str = "Deterministic-Rule-Engine-v1"
    metadata: dict[str, Any] = field(default_factory=dict)


# =========================================================================
# P2.S4 Operational Risk & Prioritized Findings Types
# =========================================================================

class OperationalPriority(StrEnum):
    """Action priority rating for operations personnel (P2.S4)."""
    NONE = "NONE"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


@dataclass(frozen=True)
class OperationalFinding:
    """
    Immutable prioritized operational finding (P2.S4).
    Synthesizes Health, Anomaly, and Diagnostic outputs into an actionable,
    traceable finding with advisory next steps for human operators.
    """
    asset_id: str
    device_id: str
    priority: OperationalPriority
    risk_level: AnomalySeverity
    summary: str
    operational_state: OperationalState
    health_score: float
    anomaly_status: AnomalyStatus
    anomaly_score: float
    diagnostic_status: DiagnosticStatus
    diagnostic_confidence: float
    primary_hypothesis: DiagnosticHypothesis | None
    supporting_evidence: tuple[str, ...]
    recommended_next_action: str
    lead_cycles_estimate: int | None
    confidence: float                      # Composite operational confidence
    traceability_chain: dict[str, Any]
    evaluated_at: datetime
    limitations: str
    metadata: dict[str, Any] = field(default_factory=dict)
