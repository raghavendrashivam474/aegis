"""
Aegis P4.S2 — Intelligence Snapshot Contract Tests.
Verifies that the IntelligenceSnapshot value object satisfies all
invariants defined in the P4.S2 specification (s5.3, s5.4, s8.1).

Tests run without PostgreSQL, Streamlit, or any infrastructure.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from domain.intelligence import (
    AnomalyDetectionResult,
    AnomalySeverity,
    AnomalyStatus,
    DiagnosticContext,
    DiagnosticResult,
    DiagnosticStatus,
    HealthAssessment,
    OperationalFinding,
    OperationalPriority,
    OperationalState,
    SensorSignal,
    SignalEvidence,
    TrendDirection,
)
from domain.snapshot import (
    SNAPSHOT_CONTRACT_VERSION,
    EvaluationStatus,
    IntelligenceSnapshot,
)

# =========================================================================
# Fixtures / Helpers
# =========================================================================

NOW = datetime(2025, 6, 15, 12, 0, 0, tzinfo=UTC)


def _make_health(
    device_id: str = "dev-01",
    state: OperationalState = OperationalState.NORMAL,
    score: float = 92.0,
) -> HealthAssessment:
    return HealthAssessment(
        asset_id=f"asset-{device_id}",
        device_id=device_id,
        operational_state=state,
        health_score=score,
        confidence=0.95,
        trend=TrendDirection.STABLE,
        sensor_signals=(
            SensorSignal(
                sensor_id="temp-01",
                measurement_type="temperature",
                baseline_mean=50.0,
                baseline_std=1.2,
                current_mean=50.5,
                deviation_score=0.42,
                trend=TrendDirection.STABLE,
                data_quality=0.98,
                sample_count=80,
            ),
        ),
        evaluated_at=NOW,
        evidence_summary="All sensors nominal.",
    )


def _make_anomaly(
    device_id: str = "dev-01",
    status: AnomalyStatus = AnomalyStatus.NOMINAL,
    score: float = 0.05,
) -> AnomalyDetectionResult:
    return AnomalyDetectionResult(
        asset_id=f"asset-{device_id}",
        device_id=device_id,
        status=status,
        anomaly_score=score,
        confidence=0.90,
        severity=AnomalySeverity.NONE,
        evidence_list=(
            SignalEvidence(
                sensor_id="temp-01",
                measurement_type="temperature",
                deviation_sigma=0.42,
                trend=TrendDirection.STABLE,
                persistence_count=0,
                contribution_score=0.1,
                reason="Within baseline.",
            ),
        ),
        evaluated_at=NOW,
        detection_method="Statistical-v1",
    )


def _make_diagnostic(
    device_id: str = "dev-01",
    status: DiagnosticStatus = DiagnosticStatus.NOMINAL,
) -> DiagnosticResult:
    return DiagnosticResult(
        asset_id=f"asset-{device_id}",
        device_id=device_id,
        status=status,
        overall_risk=AnomalySeverity.NONE,
        context=DiagnosticContext(
            operational_state=OperationalState.NORMAL,
            health_score=92.0,
            health_confidence=0.95,
            anomaly_status=AnomalyStatus.NOMINAL,
            anomaly_score=0.05,
            anomaly_severity=AnomalySeverity.NONE,
            total_sensors=4,
            affected_sensors=0,
            dominant_trend=TrendDirection.STABLE,
            max_persistence=0,
        ),
        evidence=(),
        hypotheses=(),
        primary_hypothesis=None,
        confidence=0.85,
        primary_finding="No degradation detected.",
        limitations="Limited observation window.",
        evaluated_at=NOW,
    )


def _make_finding(
    device_id: str = "dev-01",
    priority: OperationalPriority = OperationalPriority.NONE,
) -> OperationalFinding:
    return OperationalFinding(
        asset_id=f"asset-{device_id}",
        device_id=device_id,
        priority=priority,
        risk_level=AnomalySeverity.NONE,
        summary="Asset operating normally.",
        operational_state=OperationalState.NORMAL,
        health_score=92.0,
        anomaly_status=AnomalyStatus.NOMINAL,
        anomaly_score=0.05,
        diagnostic_status=DiagnosticStatus.NOMINAL,
        diagnostic_confidence=0.85,
        primary_hypothesis=None,
        supporting_evidence=("Health nominal.", "No anomalies."),
        recommended_next_action="Continue monitoring.",
        lead_cycles_estimate=None,
        confidence=0.88,
        traceability_chain={"health_score": 92.0, "anomaly_status": "NOMINAL"},
        evaluated_at=NOW,
        limitations="Advisory only.",
    )


def _make_full_snapshot(
    device_id: str = "dev-01",
    status: EvaluationStatus = EvaluationStatus.SUCCESS,
) -> IntelligenceSnapshot:
    return IntelligenceSnapshot.create(
        device_id=device_id,
        asset_id=f"asset-{device_id}",
        evaluation_status=status,
        health=_make_health(device_id),
        anomaly=_make_anomaly(device_id),
        diagnostic=_make_diagnostic(device_id),
        finding=_make_finding(device_id),
        telemetry_start=NOW - timedelta(hours=2),
        telemetry_end=NOW,
        evaluation_duration_ms=125.5,
    )


# =========================================================================
# s8.1 — Snapshot Contract Tests
# =========================================================================


def test_snapshot_construction_with_all_fields() -> None:
    """A valid snapshot can be constructed with all intelligence results."""
    snap = _make_full_snapshot()
    assert snap.device_id == "dev-01"
    assert snap.asset_id == "asset-dev-01"
    assert snap.evaluation_status == EvaluationStatus.SUCCESS
    assert snap.health is not None
    assert snap.anomaly is not None
    assert snap.diagnostic is not None
    assert snap.finding is not None
    assert snap.is_complete
    assert snap.contract_version == SNAPSHOT_CONTRACT_VERSION


def test_snapshot_has_unique_identity() -> None:
    """Each snapshot gets a unique snapshot_id (Invariant 1 + 2)."""
    s1 = _make_full_snapshot()
    s2 = _make_full_snapshot()
    assert s1.snapshot_id != s2.snapshot_id
    assert len(s1.snapshot_id) == 32  # UUID hex


def test_snapshot_has_evaluation_timestamp() -> None:
    """Snapshot records when the evaluation occurred (Invariant 2)."""
    snap = _make_full_snapshot()
    assert snap.evaluated_at is not None
    assert snap.evaluated_at.tzinfo is not None


def test_snapshot_preserves_health_evidence() -> None:
    """Health sensor signals survive the snapshot (Invariant 3)."""
    snap = _make_full_snapshot()
    assert snap.health is not None
    assert len(snap.health.sensor_signals) == 1
    sig = snap.health.sensor_signals[0]
    assert sig.sensor_id == "temp-01"
    assert sig.baseline_mean == 50.0
    assert sig.deviation_score == 0.42


def test_snapshot_preserves_anomaly_evidence() -> None:
    """Anomaly evidence list survives the snapshot (Invariant 3)."""
    snap = _make_full_snapshot()
    assert snap.anomaly is not None
    assert len(snap.anomaly.evidence_list) == 1
    assert snap.anomaly.evidence_list[0].deviation_sigma == 0.42


def test_snapshot_preserves_diagnostic_context() -> None:
    """Diagnostic context and hypotheses survive the snapshot."""
    snap = _make_full_snapshot()
    assert snap.diagnostic is not None
    assert snap.diagnostic.context.total_sensors == 4
    assert snap.diagnostic.context.affected_sensors == 0


def test_snapshot_preserves_finding_traceability() -> None:
    """Operational finding traceability chain is preserved."""
    snap = _make_full_snapshot()
    assert snap.finding is not None
    assert snap.finding.traceability_chain["health_score"] == 92.0
    assert snap.finding.recommended_next_action == "Continue monitoring."


def test_snapshot_operational_state_from_health() -> None:
    """operational_state property delegates to health assessment."""
    snap = _make_full_snapshot()
    assert snap.operational_state == OperationalState.NORMAL

    _ = _make_full_snapshot()  # baseline before override
    # Replace health with degrading state via create
    snap_deg = IntelligenceSnapshot.create(
        device_id="dev-02",
        asset_id="asset-dev-02",
        evaluation_status=EvaluationStatus.SUCCESS,
        health=_make_health("dev-02", OperationalState.DEGRADING, 65.0),
    )
    assert snap_deg.operational_state == OperationalState.DEGRADING


def test_snapshot_operational_state_unknown_without_health() -> None:
    """Without a health result, operational_state defaults to UNKNOWN."""
    snap = IntelligenceSnapshot.create(
        device_id="dev-03",
        asset_id="asset-dev-03",
        evaluation_status=EvaluationStatus.INSUFFICIENT_EVIDENCE,
    )
    assert snap.operational_state == OperationalState.UNKNOWN


# =========================================================================
# Invariant 4 — Failure Honesty
# =========================================================================


def test_failed_evaluation_is_not_healthy() -> None:
    """A FAILED snapshot must never report is_healthy=True (Invariant 4)."""
    snap = IntelligenceSnapshot.create(
        device_id="dev-fail",
        asset_id="asset-fail",
        evaluation_status=EvaluationStatus.FAILED,
        health=_make_health("dev-fail", OperationalState.NORMAL, 99.0),
    )
    assert not snap.is_healthy, "Failed evaluation must not appear healthy"


def test_partial_failure_is_not_healthy() -> None:
    """A PARTIAL_FAILURE snapshot must never report is_healthy=True."""
    snap = IntelligenceSnapshot.create(
        device_id="dev-partial",
        asset_id="asset-partial",
        evaluation_status=EvaluationStatus.PARTIAL_FAILURE,
        health=_make_health("dev-partial", OperationalState.NORMAL, 95.0),
        anomaly=_make_anomaly("dev-partial"),
    )
    assert not snap.is_healthy


def test_insufficient_evidence_is_not_complete() -> None:
    """INSUFFICIENT_EVIDENCE snapshot is not complete."""
    snap = IntelligenceSnapshot.create(
        device_id="dev-insuf",
        asset_id="asset-insuf",
        evaluation_status=EvaluationStatus.INSUFFICIENT_EVIDENCE,
        health=_make_health("dev-insuf", OperationalState.UNKNOWN, 0.0),
    )
    assert not snap.is_complete
    assert not snap.is_healthy


def test_success_with_normal_state_is_healthy() -> None:
    """A SUCCESS snapshot with NORMAL state IS healthy."""
    snap = _make_full_snapshot()
    assert snap.is_healthy


def test_success_with_degrading_state_is_not_healthy() -> None:
    """A SUCCESS snapshot with DEGRADING state is NOT healthy."""
    snap = IntelligenceSnapshot.create(
        device_id="dev-deg",
        asset_id="asset-deg",
        evaluation_status=EvaluationStatus.SUCCESS,
        health=_make_health("dev-deg", OperationalState.DEGRADING, 60.0),
        anomaly=_make_anomaly("dev-deg", AnomalyStatus.DEGRADATION_DETECTED, 0.6),
        diagnostic=_make_diagnostic("dev-deg", DiagnosticStatus.LIKELY_DEGRADATION),
        finding=_make_finding("dev-deg", OperationalPriority.HIGH),
    )
    assert not snap.is_healthy


# =========================================================================
# Invariant 5 — Historical Preservation
# =========================================================================


def test_snapshots_are_immutable() -> None:
    """Frozen dataclass prevents mutation (supports Invariant 5)."""
    snap = _make_full_snapshot()
    try:
        snap.evaluation_status = EvaluationStatus.FAILED  # type: ignore[misc]
        assert False, "Should not be able to mutate a frozen snapshot"
    except (AttributeError, TypeError):
        pass  # Expected


def test_different_evaluations_produce_different_snapshots() -> None:
    """Two evaluations of the same device produce distinct snapshots."""
    s1 = _make_full_snapshot("dev-hist")
    s2 = _make_full_snapshot("dev-hist")
    assert s1.snapshot_id != s2.snapshot_id
    # Both should be independently valid
    assert s1.is_complete
    assert s2.is_complete


# =========================================================================
# Serialization Round-Trip (to_dict / from_dict)
# =========================================================================


def test_round_trip_full_snapshot() -> None:
    """A complete snapshot survives to_dict -> from_dict round-trip."""
    original = _make_full_snapshot()
    data = original.to_dict()
    restored = IntelligenceSnapshot.from_dict(data)

    assert restored.snapshot_id == original.snapshot_id
    assert restored.device_id == original.device_id
    assert restored.asset_id == original.asset_id
    assert restored.evaluation_status == original.evaluation_status
    assert restored.contract_version == original.contract_version
    assert restored.is_complete


def test_round_trip_preserves_health_details() -> None:
    """Health assessment fields survive serialization round-trip."""
    original = _make_full_snapshot()
    restored = IntelligenceSnapshot.from_dict(original.to_dict())

    assert restored.health is not None
    assert restored.health.operational_state == OperationalState.NORMAL
    assert restored.health.health_score == 92.0
    assert restored.health.confidence == 0.95
    assert len(restored.health.sensor_signals) == 1
    assert restored.health.sensor_signals[0].sensor_id == "temp-01"


def test_round_trip_preserves_anomaly_details() -> None:
    """Anomaly detection fields survive serialization round-trip."""
    original = _make_full_snapshot()
    restored = IntelligenceSnapshot.from_dict(original.to_dict())

    assert restored.anomaly is not None
    assert restored.anomaly.status == AnomalyStatus.NOMINAL
    assert restored.anomaly.anomaly_score == 0.05
    assert len(restored.anomaly.evidence_list) == 1


def test_round_trip_preserves_diagnostic_details() -> None:
    """Diagnostic result fields survive serialization round-trip."""
    original = _make_full_snapshot()
    restored = IntelligenceSnapshot.from_dict(original.to_dict())

    assert restored.diagnostic is not None
    assert restored.diagnostic.status == DiagnosticStatus.NOMINAL
    assert restored.diagnostic.context.total_sensors == 4
    assert restored.diagnostic.primary_finding == "No degradation detected."


def test_round_trip_preserves_finding_details() -> None:
    """Operational finding fields survive serialization round-trip."""
    original = _make_full_snapshot()
    restored = IntelligenceSnapshot.from_dict(original.to_dict())

    assert restored.finding is not None
    assert restored.finding.priority == OperationalPriority.NONE
    assert restored.finding.risk_level == AnomalySeverity.NONE
    assert restored.finding.recommended_next_action == "Continue monitoring."
    assert restored.finding.traceability_chain["health_score"] == 92.0


def test_round_trip_empty_snapshot() -> None:
    """A minimal snapshot (no intelligence results) round-trips correctly."""
    original = IntelligenceSnapshot.create(
        device_id="dev-empty",
        asset_id="asset-empty",
        evaluation_status=EvaluationStatus.FAILED,
        errors=("Repository unavailable",),
    )
    restored = IntelligenceSnapshot.from_dict(original.to_dict())

    assert restored.device_id == "dev-empty"
    assert restored.evaluation_status == EvaluationStatus.FAILED
    assert restored.health is None
    assert restored.anomaly is None
    assert restored.diagnostic is None
    assert restored.finding is None
    assert restored.errors == ("Repository unavailable",)
    assert not restored.is_complete
    assert not restored.is_healthy


def test_to_dict_produces_json_safe_types() -> None:
    """to_dict output contains only JSON-serializable types."""
    snap = _make_full_snapshot()
    data = snap.to_dict()

    # Timestamps must be strings, not datetime objects
    assert isinstance(data["evaluated_at"], str)
    assert isinstance(data["telemetry_start"], str)
    assert isinstance(data["telemetry_end"], str)

    # Enums must be strings
    assert isinstance(data["evaluation_status"], str)
    assert data["evaluation_status"] == "SUCCESS"

    # Nested health timestamps
    assert isinstance(data["health"]["evaluated_at"], str)
    assert data["health"]["operational_state"] == "NORMAL"


def test_round_trip_preserves_telemetry_window() -> None:
    """Telemetry time range survives round-trip."""
    original = _make_full_snapshot()
    restored = IntelligenceSnapshot.from_dict(original.to_dict())

    assert restored.telemetry_start is not None
    assert restored.telemetry_end is not None
    assert restored.telemetry_start < restored.telemetry_end


def test_round_trip_preserves_evaluation_duration() -> None:
    """Evaluation duration metadata survives round-trip."""
    original = _make_full_snapshot()
    restored = IntelligenceSnapshot.from_dict(original.to_dict())
    assert restored.evaluation_duration_ms == 125.5


# =========================================================================
# EvaluationStatus Enum Completeness
# =========================================================================


def test_evaluation_status_has_all_required_values() -> None:
    """EvaluationStatus covers all s5.4 required distinctions."""
    assert EvaluationStatus.SUCCESS.value == "SUCCESS"
    assert EvaluationStatus.INSUFFICIENT_EVIDENCE.value == "INSUFFICIENT_EVIDENCE"
    assert EvaluationStatus.PARTIAL_FAILURE.value == "PARTIAL_FAILURE"
    assert EvaluationStatus.FAILED.value == "FAILED"
    assert len(EvaluationStatus) == 4


# =========================================================================
# Existing Domain Contract Compatibility (s8.1 last bullet)
# =========================================================================


def test_snapshot_does_not_modify_existing_intelligence_types() -> None:
    """Intelligence domain objects remain frozen and unchanged."""
    health = _make_health()
    assert health.operational_state == OperationalState.NORMAL
    assert health.health_score == 92.0

    # Verify the original types are still frozen
    try:
        health.health_score = 0.0  # type: ignore[misc]
        assert False, "HealthAssessment should be frozen"
    except (AttributeError, TypeError):
        pass


def test_snapshot_reuses_existing_enums() -> None:
    """Snapshot uses OperationalState, AnomalyStatus, etc. from domain.intelligence."""
    snap = _make_full_snapshot()
    assert isinstance(snap.operational_state, OperationalState)
    assert isinstance(snap.health.operational_state, OperationalState)
    assert isinstance(snap.anomaly.status, AnomalyStatus)
    assert isinstance(snap.diagnostic.status, DiagnosticStatus)
    assert isinstance(snap.finding.priority, OperationalPriority)


def test_snapshot_contract_version_is_stable() -> None:
    """Contract version is a known constant for compatibility tracking."""
    assert SNAPSHOT_CONTRACT_VERSION == "v1"
    snap = _make_full_snapshot()
    assert snap.contract_version == "v1"
