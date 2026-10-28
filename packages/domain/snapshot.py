"""
Aegis Intelligence Snapshot Contract (P4.S2).
Immutable record of a single intelligence evaluation for a registered asset.
Preserves the outputs of all four intelligence services (Health, Anomaly,
Diagnostic, Risk) along with evaluation metadata, evidence references,
and completeness status.

Architecture:
    IntelligenceSnapshot is a domain value object.
    It references existing intelligence types from domain.intelligence.
    It does NOT duplicate telemetry data.
    Serialization to/from dict is provided for persistence layers.
"""

from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from .intelligence import (
    AnomalyDetectionResult,
    AnomalySeverity,
    AnomalyStatus,
    DiagnosticResult,
    DiagnosticStatus,
    HealthAssessment,
    OperationalFinding,
    OperationalPriority,
    OperationalState,
    TrendDirection,
)

SNAPSHOT_CONTRACT_VERSION = "v1"


class EvaluationStatus(StrEnum):
    """Completeness and outcome of an intelligence evaluation cycle."""

    SUCCESS = "SUCCESS"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    PARTIAL_FAILURE = "PARTIAL_FAILURE"
    FAILED = "FAILED"


@dataclass(frozen=True)
class IntelligenceSnapshot:
    """
    Immutable record of one intelligence evaluation for a specific asset.

    Invariants (P4.S2 spec s5.3):
      1. Asset identity: every snapshot belongs to a registered device/asset.
      2. Temporal identity: evaluated_at + telemetry range identify the evidence window.
      3. Evidence integrity: findings do not claim stronger evidence than produced.
      4. Failure honesty: FAILED/PARTIAL_FAILURE status is never masked as healthy.
      5. Historical preservation: newer snapshots do not overwrite older ones.
      6. Current-result selection: latest applicable snapshot is deterministic.
      7. Contract compatibility: existing consumers are not broken.
    """

    snapshot_id: str
    device_id: str
    asset_id: str
    evaluated_at: datetime
    evaluation_status: EvaluationStatus

    # Intelligence results — any may be None for partial/failed evaluations
    health: HealthAssessment | None = None
    anomaly: AnomalyDetectionResult | None = None
    diagnostic: DiagnosticResult | None = None
    finding: OperationalFinding | None = None

    # Evidence window
    telemetry_start: datetime | None = None
    telemetry_end: datetime | None = None

    # Evaluation metadata
    evaluation_duration_ms: float | None = None
    contract_version: str = SNAPSHOT_CONTRACT_VERSION
    errors: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    # --- Derived convenience properties ---

    @property
    def operational_state(self) -> OperationalState:
        """Best available operational state, or UNKNOWN if no health result."""
        if self.health is not None:
            return self.health.operational_state
        return OperationalState.UNKNOWN

    @property
    def is_complete(self) -> bool:
        """True if all four pipeline stages produced results."""
        return all([self.health, self.anomaly, self.diagnostic, self.finding])

    @property
    def is_healthy(self) -> bool:
        """True only if evaluation succeeded AND state is NORMAL.
        Never returns True for failed or incomplete evaluations (Invariant 4)."""
        if self.evaluation_status in (
            EvaluationStatus.FAILED,
            EvaluationStatus.PARTIAL_FAILURE,
        ):
            return False
        return self.operational_state == OperationalState.NORMAL

    # --- Serialization ---

    def to_dict(self) -> dict[str, Any]:
        """Convert to a JSON-serializable dictionary for persistence.
        Handles datetime -> ISO string, StrEnum -> str, tuple -> list."""
        raw = asdict(self)
        return _make_json_safe(raw)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> IntelligenceSnapshot:
        """Reconstruct an IntelligenceSnapshot from a persisted dictionary."""
        # Reconstruct nested intelligence objects
        health = _reconstruct_health(data.get("health"))
        anomaly = _reconstruct_anomaly(data.get("anomaly"))
        diagnostic = _reconstruct_diagnostic(data.get("diagnostic"))
        finding = _reconstruct_finding(data.get("finding"))

        # Parse timestamps
        evaluated_at = _parse_dt(data["evaluated_at"])
        telemetry_start = _parse_dt(data.get("telemetry_start"))
        telemetry_end = _parse_dt(data.get("telemetry_end"))

        # Parse evaluation status
        status_str = data.get("evaluation_status", "FAILED")
        evaluation_status = EvaluationStatus(status_str)

        # Parse errors (may be list from JSON, convert to tuple)
        errors = tuple(data.get("errors", []))

        return cls(
            snapshot_id=str(data["snapshot_id"]),
            device_id=str(data["device_id"]),
            asset_id=str(data["asset_id"]),
            evaluated_at=evaluated_at,
            evaluation_status=evaluation_status,
            health=health,
            anomaly=anomaly,
            diagnostic=diagnostic,
            finding=finding,
            telemetry_start=telemetry_start,
            telemetry_end=telemetry_end,
            evaluation_duration_ms=data.get("evaluation_duration_ms"),
            contract_version=str(data.get("contract_version", SNAPSHOT_CONTRACT_VERSION)),
            errors=errors,
            metadata=dict(data.get("metadata", {})),
        )

    @classmethod
    def create(
        cls,
        device_id: str,
        asset_id: str,
        evaluation_status: EvaluationStatus,
        health: HealthAssessment | None = None,
        anomaly: AnomalyDetectionResult | None = None,
        diagnostic: DiagnosticResult | None = None,
        finding: OperationalFinding | None = None,
        telemetry_start: datetime | None = None,
        telemetry_end: datetime | None = None,
        evaluation_duration_ms: float | None = None,
        errors: tuple[str, ...] = (),
        metadata: dict[str, Any] | None = None,
    ) -> IntelligenceSnapshot:
        """Factory method with auto-generated snapshot_id and timestamp."""
        return cls(
            snapshot_id=uuid.uuid4().hex,
            device_id=device_id,
            asset_id=asset_id,
            evaluated_at=datetime.now(UTC),
            evaluation_status=evaluation_status,
            health=health,
            anomaly=anomaly,
            diagnostic=diagnostic,
            finding=finding,
            telemetry_start=telemetry_start,
            telemetry_end=telemetry_end,
            evaluation_duration_ms=evaluation_duration_ms,
            errors=errors,
            metadata=metadata or {},
        )


# =========================================================================
# Serialization helpers (module-private)
# =========================================================================


def _make_json_safe(obj: Any) -> Any:
    """Recursively convert dataclass output to JSON-serializable types."""
    if isinstance(obj, dict):
        return {k: _make_json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_make_json_safe(item) for item in obj]
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, StrEnum):
        return obj.value
    if hasattr(obj, "value") and isinstance(obj.value, str):
        return obj.value
    return obj


def _parse_dt(val: Any) -> datetime | None:
    """Parse a datetime from ISO string or return None."""
    if val is None:
        return None
    if isinstance(val, datetime):
        return val
    try:
        return datetime.fromisoformat(str(val))
    except (ValueError, TypeError):
        return None


def _reconstruct_health(data: dict | None) -> HealthAssessment | None:
    """Reconstruct a HealthAssessment from its serialized dict."""
    if data is None:
        return None
    from .intelligence import SensorSignal

    signals = tuple(
        SensorSignal(
            sensor_id=s["sensor_id"],
            measurement_type=s["measurement_type"],
            baseline_mean=float(s["baseline_mean"]),
            baseline_std=float(s["baseline_std"]),
            current_mean=float(s["current_mean"]),
            deviation_score=float(s["deviation_score"]),
            trend=TrendDirection(s["trend"]),
            data_quality=float(s["data_quality"]),
            sample_count=int(s["sample_count"]),
            insufficient_data=bool(s.get("insufficient_data", False)),
        )
        for s in data.get("sensor_signals", [])
    )
    return HealthAssessment(
        asset_id=str(data["asset_id"]),
        device_id=str(data["device_id"]),
        operational_state=OperationalState(data["operational_state"]),
        health_score=float(data["health_score"]),
        confidence=float(data["confidence"]),
        trend=TrendDirection(data["trend"]),
        sensor_signals=signals,
        evaluated_at=_parse_dt(data["evaluated_at"]) or datetime.now(UTC),
        evidence_summary=str(data.get("evidence_summary", "")),
        metadata=dict(data.get("metadata", {})),
    )


def _reconstruct_anomaly(data: dict | None) -> AnomalyDetectionResult | None:
    """Reconstruct an AnomalyDetectionResult from its serialized dict."""
    if data is None:
        return None
    from .intelligence import SignalEvidence

    evidence = tuple(
        SignalEvidence(
            sensor_id=e["sensor_id"],
            measurement_type=e["measurement_type"],
            deviation_sigma=float(e["deviation_sigma"]),
            trend=TrendDirection(e["trend"]),
            persistence_count=int(e["persistence_count"]),
            contribution_score=float(e["contribution_score"]),
            reason=str(e["reason"]),
        )
        for e in data.get("evidence_list", [])
    )
    return AnomalyDetectionResult(
        asset_id=str(data["asset_id"]),
        device_id=str(data["device_id"]),
        status=AnomalyStatus(data["status"]),
        anomaly_score=float(data["anomaly_score"]),
        confidence=float(data["confidence"]),
        severity=AnomalySeverity(data["severity"]),
        evidence_list=evidence,
        evaluated_at=_parse_dt(data["evaluated_at"]) or datetime.now(UTC),
        detection_method=str(data.get("detection_method", "")),
        lead_cycles_estimate=data.get("lead_cycles_estimate"),
        metadata=dict(data.get("metadata", {})),
    )


def _reconstruct_diagnostic(data: dict | None) -> DiagnosticResult | None:
    """Reconstruct a DiagnosticResult from its serialized dict."""
    if data is None:
        return None
    from .intelligence import (
        DiagnosticContext,
        DiagnosticEvidence,
        DiagnosticHypothesis,
        HypothesisCategory,
    )

    # Context
    ctx_data = data.get("context", {})
    context = DiagnosticContext(
        operational_state=OperationalState(ctx_data.get("operational_state", "UNKNOWN")),
        health_score=float(ctx_data.get("health_score", 0.0)),
        health_confidence=float(ctx_data.get("health_confidence", 0.0)),
        anomaly_status=AnomalyStatus(ctx_data.get("anomaly_status", "UNKNOWN")),
        anomaly_score=float(ctx_data.get("anomaly_score", 0.0)),
        anomaly_severity=AnomalySeverity(ctx_data.get("anomaly_severity", "NONE")),
        total_sensors=int(ctx_data.get("total_sensors", 0)),
        affected_sensors=int(ctx_data.get("affected_sensors", 0)),
        dominant_trend=TrendDirection(ctx_data.get("dominant_trend", "UNKNOWN")),
        max_persistence=int(ctx_data.get("max_persistence", 0)),
    )

    # Evidence
    evidence = tuple(
        DiagnosticEvidence(
            sensor_id=e["sensor_id"],
            measurement_type=e["measurement_type"],
            observation=str(e.get("observation", "")),
            deviation_sigma=float(e["deviation_sigma"]),
            trend=TrendDirection(e["trend"]),
            persistence_count=int(e["persistence_count"]),
            data_quality=float(e["data_quality"]),
            contribution_score=float(e["contribution_score"]),
            reason=str(e["reason"]),
        )
        for e in data.get("evidence", [])
    )

    # Hypotheses
    hypotheses = tuple(
        DiagnosticHypothesis(
            category=HypothesisCategory(h["category"]),
            description=str(h["description"]),
            confidence=float(h["confidence"]),
            supporting_evidence=tuple(h.get("supporting_evidence", [])),
            contradicting_evidence=tuple(h.get("contradicting_evidence", [])),
            severity=AnomalySeverity(h["severity"]),
        )
        for h in data.get("hypotheses", [])
    )

    # Primary hypothesis
    ph_data = data.get("primary_hypothesis")
    primary_hypothesis = None
    if ph_data:
        primary_hypothesis = DiagnosticHypothesis(
            category=HypothesisCategory(ph_data["category"]),
            description=str(ph_data["description"]),
            confidence=float(ph_data["confidence"]),
            supporting_evidence=tuple(ph_data.get("supporting_evidence", [])),
            contradicting_evidence=tuple(ph_data.get("contradicting_evidence", [])),
            severity=AnomalySeverity(ph_data["severity"]),
        )

    return DiagnosticResult(
        asset_id=str(data["asset_id"]),
        device_id=str(data["device_id"]),
        status=DiagnosticStatus(data["status"]),
        overall_risk=AnomalySeverity(data["overall_risk"]),
        context=context,
        evidence=evidence,
        hypotheses=hypotheses,
        primary_hypothesis=primary_hypothesis,
        confidence=float(data["confidence"]),
        primary_finding=str(data.get("primary_finding", "")),
        limitations=str(data.get("limitations", "")),
        evaluated_at=_parse_dt(data["evaluated_at"]) or datetime.now(UTC),
        diagnostic_method=str(data.get("diagnostic_method", "Deterministic-Rule-Engine-v1")),
        metadata=dict(data.get("metadata", {})),
    )


def _reconstruct_finding(data: dict | None) -> OperationalFinding | None:
    """Reconstruct an OperationalFinding from its serialized dict."""
    if data is None:
        return None
    from .intelligence import DiagnosticHypothesis, HypothesisCategory

    ph_data = data.get("primary_hypothesis")
    primary_hypothesis = None
    if ph_data:
        primary_hypothesis = DiagnosticHypothesis(
            category=HypothesisCategory(ph_data["category"]),
            description=str(ph_data["description"]),
            confidence=float(ph_data["confidence"]),
            supporting_evidence=tuple(ph_data.get("supporting_evidence", [])),
            contradicting_evidence=tuple(ph_data.get("contradicting_evidence", [])),
            severity=AnomalySeverity(ph_data["severity"]),
        )

    return OperationalFinding(
        asset_id=str(data["asset_id"]),
        device_id=str(data["device_id"]),
        priority=OperationalPriority(data["priority"]),
        risk_level=AnomalySeverity(data["risk_level"]),
        summary=str(data.get("summary", "")),
        operational_state=OperationalState(data["operational_state"]),
        health_score=float(data["health_score"]),
        anomaly_status=AnomalyStatus(data["anomaly_status"]),
        anomaly_score=float(data["anomaly_score"]),
        diagnostic_status=DiagnosticStatus(data["diagnostic_status"]),
        diagnostic_confidence=float(data["diagnostic_confidence"]),
        primary_hypothesis=primary_hypothesis,
        supporting_evidence=tuple(data.get("supporting_evidence", [])),
        recommended_next_action=str(data.get("recommended_next_action", "")),
        lead_cycles_estimate=data.get("lead_cycles_estimate"),
        confidence=float(data["confidence"]),
        traceability_chain=dict(data.get("traceability_chain", {})),
        evaluated_at=_parse_dt(data["evaluated_at"]) or datetime.now(UTC),
        limitations=str(data.get("limitations", "")),
        metadata=dict(data.get("metadata", {})),
    )
