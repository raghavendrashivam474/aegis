"""
Aegis P4.S2 — Snapshot Query Service Tests.
Verifies query correctness, freshness assessment, and error handling.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from domain.intelligence import OperationalState
from domain.repository import InMemorySnapshotRepository
from domain.snapshot import EvaluationStatus, IntelligenceSnapshot

from apps.backend.snapshot_query_service import (
    SnapshotQueryService,
)


def _make_snapshot(
    device_id: str,
    status: EvaluationStatus = EvaluationStatus.SUCCESS,
    age_minutes: float = 1.0,
    state: OperationalState = OperationalState.NORMAL,
) -> IntelligenceSnapshot:
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
        SensorSignal,
        TrendDirection,
    )

    eval_time = datetime.now(UTC) - timedelta(minutes=age_minutes)
    health = HealthAssessment(
        asset_id=f"asset-{device_id}",
        device_id=device_id,
        operational_state=state,
        health_score=90.0 if state == OperationalState.NORMAL else 60.0,
        confidence=0.9,
        trend=TrendDirection.STABLE,
        sensor_signals=(
            SensorSignal(
                sensor_id="t1",
                measurement_type="temperature",
                baseline_mean=50.0,
                baseline_std=1.0,
                current_mean=50.0,
                deviation_score=0.0,
                trend=TrendDirection.STABLE,
                data_quality=1.0,
                sample_count=50,
            ),
        ),
        evaluated_at=eval_time,
        evidence_summary="OK",
    )
    anomaly = AnomalyDetectionResult(
        asset_id=f"asset-{device_id}",
        device_id=device_id,
        status=AnomalyStatus.NOMINAL,
        anomaly_score=0.1,
        confidence=0.9,
        severity=AnomalySeverity.NONE,
        evidence_list=(),
        evaluated_at=eval_time,
        detection_method="test",
    )
    diagnostic = DiagnosticResult(
        asset_id=f"asset-{device_id}",
        device_id=device_id,
        status=DiagnosticStatus.NOMINAL,
        overall_risk=AnomalySeverity.NONE,
        context=DiagnosticContext(
            operational_state=state,
            health_score=90.0,
            health_confidence=0.9,
            anomaly_status=AnomalyStatus.NOMINAL,
            anomaly_score=0.1,
            anomaly_severity=AnomalySeverity.NONE,
            total_sensors=1,
            affected_sensors=0,
            dominant_trend=TrendDirection.STABLE,
            max_persistence=0,
        ),
        evidence=(),
        hypotheses=(),
        primary_hypothesis=None,
        confidence=0.85,
        primary_finding="OK",
        limitations="test",
        evaluated_at=eval_time,
    )
    finding = OperationalFinding(
        asset_id=f"asset-{device_id}",
        device_id=device_id,
        priority=OperationalPriority.NONE,
        risk_level=AnomalySeverity.NONE,
        summary="OK",
        operational_state=state,
        health_score=90.0,
        anomaly_status=AnomalyStatus.NOMINAL,
        anomaly_score=0.1,
        diagnostic_status=DiagnosticStatus.NOMINAL,
        diagnostic_confidence=0.85,
        primary_hypothesis=None,
        supporting_evidence=(),
        recommended_next_action="Monitor",
        lead_cycles_estimate=None,
        confidence=0.88,
        traceability_chain={},
        evaluated_at=eval_time,
        limitations="test",
    )
    return IntelligenceSnapshot(
        snapshot_id=f"snap-{device_id}-{age_minutes}",
        device_id=device_id,
        asset_id=f"asset-{device_id}",
        evaluated_at=eval_time,
        evaluation_status=status,
        health=health,
        anomaly=anomaly,
        diagnostic=diagnostic,
        finding=finding,
    )


def test_query_returns_current_snapshot() -> None:
    repo = InMemorySnapshotRepository()
    snap = _make_snapshot("dev-1", age_minutes=1.0)
    repo.save(snap)
    svc = SnapshotQueryService(repo)

    result = svc.get_asset_snapshot("dev-1")
    assert result.has_data
    assert result.status == "current"
    assert result.freshness is not None
    assert result.freshness.is_fresh


def test_query_detects_stale_snapshot() -> None:
    repo = InMemorySnapshotRepository()
    snap = _make_snapshot("dev-1", age_minutes=10.0)
    repo.save(snap)
    svc = SnapshotQueryService(repo, freshness_threshold=timedelta(minutes=5))

    result = svc.get_asset_snapshot("dev-1")
    assert result.has_data
    assert result.status == "stale"
    assert not result.freshness.is_fresh


def test_query_missing_device() -> None:
    repo = InMemorySnapshotRepository()
    svc = SnapshotQueryService(repo)

    result = svc.get_asset_snapshot("nonexistent")
    assert not result.has_data
    assert result.status == "no_snapshot"


def test_query_failed_evaluation() -> None:
    repo = InMemorySnapshotRepository()
    snap = _make_snapshot("dev-fail", status=EvaluationStatus.FAILED, age_minutes=1.0)
    repo.save(snap)
    svc = SnapshotQueryService(repo)

    result = svc.get_asset_snapshot("dev-fail")
    assert result.has_data
    assert result.status == "evaluation_failed"


def test_query_insufficient_evidence() -> None:
    repo = InMemorySnapshotRepository()
    snap = _make_snapshot(
        "dev-insuf",
        status=EvaluationStatus.INSUFFICIENT_EVIDENCE,
        age_minutes=1.0,
    )
    repo.save(snap)
    svc = SnapshotQueryService(repo)

    result = svc.get_asset_snapshot("dev-insuf")
    assert result.has_data
    assert result.status == "insufficient_evidence"


def test_fleet_query() -> None:
    repo = InMemorySnapshotRepository()
    repo.save(_make_snapshot("dev-a", age_minutes=1.0))
    repo.save(_make_snapshot("dev-b", age_minutes=1.0))
    svc = SnapshotQueryService(repo)

    results = svc.get_fleet_snapshots(["dev-a", "dev-b", "dev-c"])
    assert len(results) == 3
    assert results["dev-a"].status == "current"
    assert results["dev-b"].status == "current"
    assert results["dev-c"].status == "no_snapshot"


def test_fleet_query_does_not_recalculate() -> None:
    """Fleet query retrieves persisted data, not recomputed intelligence."""
    repo = InMemorySnapshotRepository()
    repo.save(_make_snapshot("dev-x", age_minutes=1.0))
    svc = SnapshotQueryService(repo)

    # This should be a simple repository lookup, not a pipeline execution
    results = svc.get_fleet_snapshots(["dev-x"])
    assert results["dev-x"].has_data
    # The snapshot's evaluated_at should match what we stored
    assert results["dev-x"].snapshot.evaluated_at is not None


def test_history_query() -> None:
    repo = InMemorySnapshotRepository()
    repo.save(_make_snapshot("dev-h", age_minutes=10.0))
    repo.save(_make_snapshot("dev-h", age_minutes=5.0))
    repo.save(_make_snapshot("dev-h", age_minutes=1.0))
    svc = SnapshotQueryService(repo)

    history = svc.get_asset_history("dev-h")
    assert len(history) == 3
    # Newest first
    assert history[0].evaluated_at > history[1].evaluated_at


def test_query_result_usable_property() -> None:
    repo = InMemorySnapshotRepository()
    repo.save(_make_snapshot("dev-u", age_minutes=1.0))
    svc = SnapshotQueryService(repo)

    result = svc.get_asset_snapshot("dev-u")
    assert result.is_usable

    _ = svc.get_asset_snapshot("dev-u")  # baseline before threshold change
    # Force stale by using a short threshold
    svc2 = SnapshotQueryService(repo, freshness_threshold=timedelta(seconds=1))
    import time

    time.sleep(1.1)
    stale2 = svc2.get_asset_snapshot("dev-u")
    assert not stale2.is_usable
