"""
Aegis P4.S2 — Evaluation Lifecycle Tests.
Verifies that IntelligenceEvaluationService correctly orchestrates
the intelligence pipeline, assembles snapshots, and persists results.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from domain.entities import Observation, QualityFlag
from domain.intelligence import (
    OperationalState,
)
from domain.repository import (
    InMemorySnapshotRepository,
    InMemoryTelemetryRepository,
)
from domain.snapshot import EvaluationStatus

from apps.backend.evaluation_service import (
    IntelligenceEvaluationService,
)

# =========================================================================
# Helpers
# =========================================================================


def _seed_healthy(repo: InMemoryTelemetryRepository, device_id: str) -> None:
    base = datetime(2025, 1, 1, tzinfo=UTC)
    for cycle in range(1, 81):
        ts = base + timedelta(minutes=cycle)
        repo.save_observation(
            Observation(
                observation_id=f"obs-{device_id}-t-{cycle}",
                device_id=device_id,
                sensor_id="temp-s1",
                timestamp=ts,
                value=50.0,
                unit="celsius",
                quality=QualityFlag.GOOD,
            )
        )
        repo.save_observation(
            Observation(
                observation_id=f"obs-{device_id}-v-{cycle}",
                device_id=device_id,
                sensor_id="vib-s1",
                timestamp=ts,
                value=1.5,
                unit="mm/s",
                quality=QualityFlag.GOOD,
            )
        )


def _seed_degrading(repo: InMemoryTelemetryRepository, device_id: str) -> None:
    base = datetime(2025, 1, 1, tzinfo=UTC)
    for cycle in range(1, 81):
        ts = base + timedelta(minutes=cycle)
        drift = max(0, (cycle - 40) * 0.5)
        repo.save_observation(
            Observation(
                observation_id=f"obs-{device_id}-t-{cycle}",
                device_id=device_id,
                sensor_id="temp-s2",
                timestamp=ts,
                value=50.0 + drift,
                unit="celsius",
                quality=QualityFlag.GOOD,
            )
        )
        repo.save_observation(
            Observation(
                observation_id=f"obs-{device_id}-v-{cycle}",
                device_id=device_id,
                sensor_id="vib-s2",
                timestamp=ts,
                value=1.5 + drift * 0.05,
                unit="mm/s",
                quality=QualityFlag.GOOD,
            )
        )


def _make_service(
    telemetry: InMemoryTelemetryRepository | None = None,
    snapshots: InMemorySnapshotRepository | None = None,
) -> tuple[IntelligenceEvaluationService, InMemoryTelemetryRepository, InMemorySnapshotRepository]:
    t = telemetry or InMemoryTelemetryRepository()
    s = snapshots or InMemorySnapshotRepository()
    svc = IntelligenceEvaluationService(t, s)
    return svc, t, s


# =========================================================================
# s8.3 — Evaluation Lifecycle Tests
# =========================================================================


def test_successful_evaluation_produces_valid_snapshot() -> None:
    """A healthy device produces a SUCCESS snapshot with all four results."""
    svc, repo, snap_repo = _make_service()
    _seed_healthy(repo, "dev-ok")

    result = svc.evaluate_asset("dev-ok", "asset-ok")

    assert result.success
    assert result.snapshot.evaluation_status == EvaluationStatus.SUCCESS
    assert result.snapshot.is_complete
    assert result.snapshot.health is not None
    assert result.snapshot.anomaly is not None
    assert result.snapshot.diagnostic is not None
    assert result.snapshot.finding is not None
    assert result.snapshot.operational_state == OperationalState.NORMAL


def test_successful_evaluation_is_persisted() -> None:
    """A successful evaluation persists the snapshot to the repository."""
    svc, repo, snap_repo = _make_service()
    _seed_healthy(repo, "dev-persist")

    svc.evaluate_asset("dev-persist", "asset-persist")

    latest = snap_repo.get_latest("dev-persist")
    assert latest is not None
    assert latest.device_id == "dev-persist"
    assert latest.evaluation_status == EvaluationStatus.SUCCESS


def test_degrading_device_evaluation() -> None:
    """A degrading device produces correct intelligence in the snapshot."""
    svc, repo, snap_repo = _make_service()
    _seed_degrading(repo, "dev-deg")

    result = svc.evaluate_asset("dev-deg", "asset-deg")

    assert result.snapshot.health is not None
    assert result.snapshot.health.health_score < 80.0
    assert result.snapshot.anomaly is not None
    assert result.snapshot.anomaly.anomaly_score >= 0.0


def test_insufficient_telemetry_produces_honest_result() -> None:
    """An empty repository produces INSUFFICIENT_EVIDENCE, not a healthy result.
    Note: the intelligence services return valid objects with UNKNOWN state
    and 0.0 score on empty data, so is_complete may be True. The honesty
    guarantee is that is_healthy is False and the status reflects the gap."""
    svc, repo, snap_repo = _make_service()

    result = svc.evaluate_asset("no-device", "no-asset")

    assert result.snapshot.evaluation_status in (
        EvaluationStatus.INSUFFICIENT_EVIDENCE,
        EvaluationStatus.FAILED,
    )
    # Critical: must NOT appear healthy despite having all four objects
    assert not result.snapshot.is_healthy
    # Health score should reflect the lack of data
    if result.snapshot.health is not None:
        assert result.snapshot.health.health_score == 0.0
        assert result.snapshot.health.operational_state.value == "UNKNOWN"


def test_evaluation_records_telemetry_window() -> None:
    """The snapshot records the telemetry time range."""
    svc, repo, snap_repo = _make_service()
    _seed_healthy(repo, "dev-window")

    result = svc.evaluate_asset("dev-window", "asset-window")

    assert result.snapshot.telemetry_start is not None
    assert result.snapshot.telemetry_end is not None
    assert result.snapshot.telemetry_start < result.snapshot.telemetry_end


def test_evaluation_records_duration() -> None:
    """The snapshot records evaluation duration."""
    svc, repo, snap_repo = _make_service()
    _seed_healthy(repo, "dev-dur")

    result = svc.evaluate_asset("dev-dur", "asset-dur")

    assert result.snapshot.evaluation_duration_ms is not None
    assert result.snapshot.evaluation_duration_ms >= 0.0
    assert result.duration_ms >= 0.0


def test_evaluation_without_persist() -> None:
    """Evaluation can run without persisting (persist=False)."""
    svc, repo, snap_repo = _make_service()
    _seed_healthy(repo, "dev-nopersist")

    result = svc.evaluate_asset("dev-nopersist", "asset-nopersist", persist=False)

    assert result.success
    assert snap_repo.get_latest("dev-nopersist") is None


def test_fleet_evaluation() -> None:
    """Fleet evaluation produces results for all devices."""
    svc, repo, snap_repo = _make_service()
    _seed_healthy(repo, "fleet-dev-1")
    _seed_degrading(repo, "fleet-dev-2")

    results = svc.evaluate_fleet(
        [
            ("fleet-dev-1", "asset-1"),
            ("fleet-dev-2", "asset-2"),
        ]
    )

    assert len(results) == 2
    assert "fleet-dev-1" in results
    assert "fleet-dev-2" in results
    assert results["fleet-dev-1"].snapshot.is_complete
    assert results["fleet-dev-2"].snapshot.is_complete

    # Both should be persisted
    assert snap_repo.get_latest("fleet-dev-1") is not None
    assert snap_repo.get_latest("fleet-dev-2") is not None


def test_repeated_evaluations_create_distinct_snapshots() -> None:
    """Evaluating the same device twice creates two snapshots (history)."""
    svc, repo, snap_repo = _make_service()
    _seed_healthy(repo, "dev-repeat")

    svc.evaluate_asset("dev-repeat", "asset-repeat")
    svc.evaluate_asset("dev-repeat", "asset-repeat")

    history = snap_repo.get_history("dev-repeat")
    assert len(history) == 2
    assert history[0].snapshot_id != history[1].snapshot_id


def test_evaluation_preserves_errors() -> None:
    """Evaluation errors are recorded in the snapshot."""
    svc, repo, snap_repo = _make_service()
    # Empty repo will produce insufficient evidence
    result = svc.evaluate_asset("empty-dev", "empty-asset")

    # The snapshot should have error information or insufficient status
    assert result.snapshot.evaluation_status in (
        EvaluationStatus.INSUFFICIENT_EVIDENCE,
        EvaluationStatus.FAILED,
        EvaluationStatus.PARTIAL_FAILURE,
    )


def test_evaluation_result_success_property() -> None:
    """EvaluationResult.success is True for SUCCESS and INSUFFICIENT_EVIDENCE."""
    svc, repo, snap_repo = _make_service()
    _seed_healthy(repo, "dev-succ")

    result = svc.evaluate_asset("dev-succ", "asset-succ")
    assert result.success is True

    # Empty device
    result2 = svc.evaluate_asset("dev-empty", "asset-empty")
    # INSUFFICIENT_EVIDENCE is still considered a "successful" evaluation
    # (the evaluation ran, it just found no data)
    assert result2.success is True


def test_evidence_chain_integrity_in_snapshot() -> None:
    """Evidence flows through the pipeline into the persisted snapshot."""
    svc, repo, snap_repo = _make_service()
    _seed_degrading(repo, "dev-chain")

    result = svc.evaluate_asset("dev-chain", "asset-chain")
    snap = result.snapshot

    # Health evidence
    assert snap.health is not None
    assert len(snap.health.sensor_signals) > 0

    # Anomaly evidence
    assert snap.anomaly is not None

    # Diagnostic references upstream
    assert snap.diagnostic is not None
    assert snap.diagnostic.context.health_score == snap.health.health_score

    # Finding references upstream
    assert snap.finding is not None
    assert snap.finding.health_score == snap.health.health_score
    assert snap.finding.anomaly_status == snap.anomaly.status
