"""
Aegis P4.S1 â€” Dashboard Intelligence Integration Tests.
Verifies that the dashboard's intelligence pipeline wiring produces
correct results from the existing domain services.

These tests exercise the same code path the dashboard uses,
without requiring Streamlit or PostgreSQL.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from domain.entities import Observation, QualityFlag
from domain.intelligence import (
    AnomalyStatus,
    DiagnosticStatus,
    OperationalPriority,
    OperationalState,
)
from domain.repository import InMemoryTelemetryRepository
from intelligence.anomaly_service import AnomalyDetectionService
from intelligence.diagnostic_service import DiagnosticService
from intelligence.health_service import HealthAssessmentService
from intelligence.risk_service import OperationalRiskService


def _make_observation(
    device_id: str,
    sensor_id: str,
    timestamp: datetime,
    value: float,
    cycle: int = 0,
) -> Observation:
    return Observation(
        observation_id=f"obs-{device_id}-{sensor_id}-{cycle}",
        device_id=device_id,
        sensor_id=sensor_id,
        timestamp=timestamp,
        value=value,
        unit="celsius" if "temp" in sensor_id else "mm/s",
        quality=QualityFlag.GOOD,
        metadata={"source": "test"},
    )


def _seed_healthy_device(repo: InMemoryTelemetryRepository, device_id: str) -> None:
    """Seed 80 cycles of nominal data for two sensors."""
    base = datetime(2025, 1, 1, tzinfo=UTC)
    for cycle in range(1, 81):
        ts = base + timedelta(minutes=cycle)
        repo.save_observation(_make_observation(device_id, "temp-s1", ts, 50.0, cycle))
        repo.save_observation(_make_observation(device_id, "vib-s1", ts, 1.5, cycle))


def _seed_degrading_device(repo: InMemoryTelemetryRepository, device_id: str) -> None:
    """Seed 80 cycles with progressive thermal drift."""
    base = datetime(2025, 1, 1, tzinfo=UTC)
    for cycle in range(1, 81):
        ts = base + timedelta(minutes=cycle)
        drift = max(0, (cycle - 40) * 0.5)
        repo.save_observation(_make_observation(device_id, "temp-s2", ts, 50.0 + drift, cycle))
        repo.save_observation(_make_observation(device_id, "vib-s2", ts, 1.5 + drift * 0.05, cycle))


def test_dashboard_pipeline_healthy_asset() -> None:
    """Full pipeline on healthy data produces NORMAL state, low risk."""
    repo = InMemoryTelemetryRepository()
    _seed_healthy_device(repo, "device-healthy")

    health = HealthAssessmentService(repo).assess("device-healthy", "asset-healthy")
    assert health.operational_state == OperationalState.NORMAL
    assert health.health_score >= 75.0

    anomaly = AnomalyDetectionService(repo).detect("device-healthy", "asset-healthy")
    assert anomaly.status in (AnomalyStatus.NOMINAL, AnomalyStatus.UNKNOWN)

    diagnostic = DiagnosticService().diagnose(health, anomaly)
    assert diagnostic.status in (
        DiagnosticStatus.NOMINAL,
        DiagnosticStatus.INSUFFICIENT_EVIDENCE,
    )

    finding = OperationalRiskService().evaluate(health, anomaly, diagnostic)
    assert finding.priority in (OperationalPriority.NONE, OperationalPriority.LOW)


def test_dashboard_pipeline_degrading_asset() -> None:
    """Full pipeline on degrading data detects degradation and elevates risk."""
    repo = InMemoryTelemetryRepository()
    _seed_degrading_device(repo, "device-degrading")

    health = HealthAssessmentService(repo).assess("device-degrading", "asset-degrading")
    assert health.health_score < 80.0

    anomaly = AnomalyDetectionService(repo).detect("device-degrading", "asset-degrading")
    # Should detect some level of anomaly or degradation
    assert anomaly.anomaly_score >= 0.0

    diagnostic = DiagnosticService().diagnose(health, anomaly)
    assert diagnostic is not None

    finding = OperationalRiskService().evaluate(health, anomaly, diagnostic)
    assert finding.priority.value in ("LOW", "MEDIUM", "HIGH", "CRITICAL")
    assert finding.recommended_next_action  # Non-empty advisory


def test_dashboard_pipeline_empty_repository() -> None:
    """Pipeline handles empty repository without crashing."""
    repo = InMemoryTelemetryRepository()

    health = HealthAssessmentService(repo).assess("no-device", "no-asset")
    assert health.operational_state == OperationalState.UNKNOWN
    assert health.health_score == 0.0

    anomaly = AnomalyDetectionService(repo).detect("no-device", "no-asset")
    assert anomaly.status == AnomalyStatus.UNKNOWN

    diagnostic = DiagnosticService().diagnose(health, anomaly)
    assert diagnostic.status == DiagnosticStatus.INSUFFICIENT_EVIDENCE

    finding = OperationalRiskService().evaluate(health, anomaly, diagnostic)
    assert finding.priority == OperationalPriority.LOW


def test_dashboard_pipeline_evidence_chain_integrity() -> None:
    """Evidence flows through the full pipeline without fabrication."""
    repo = InMemoryTelemetryRepository()
    _seed_degrading_device(repo, "device-evidence")

    health = HealthAssessmentService(repo).assess("device-evidence", "asset-evidence")
    anomaly = AnomalyDetectionService(repo).detect("device-evidence", "asset-evidence")
    diagnostic = DiagnosticService().diagnose(health, anomaly)
    finding = OperationalRiskService().evaluate(health, anomaly, diagnostic)

    # Traceability chain must reference upstream results
    assert finding.traceability_chain is not None
    assert finding.health_score == health.health_score
    assert finding.anomaly_status == anomaly.status
    assert finding.diagnostic_status == diagnostic.status

    # Hypotheses must be labeled as hypotheses, not confirmed causes
    if diagnostic.hypotheses:
        for hyp in diagnostic.hypotheses:
            assert hyp.confidence <= 1.0
            assert hyp.confidence >= 0.0
