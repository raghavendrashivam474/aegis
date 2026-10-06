"""
Aegis P2.S4 Verification Test Suite.
Tests deterministic operational risk prioritization and explainable findings:
- S4-NOMINAL: Healthy stable asset
- S4-EARLY-DRIFT: Low-magnitude drift produces LOW priority monitoring advice
- S4-HIGH-RISK: Persistent degradation produces CRITICAL priority maintenance advice
- S4-MULTIPLE-HYPOTHESES: Retaining uncertainty with isolation recommendation
- S4-LOW-CONFIDENCE: Constraining priority escalation under uncertain telemetry
- S4-RECOVERY: Alert resolution on telemetry recovery
- S4-DETERMINISM: Idempotent results and identical traceability chains
- S4-END-TO-END: Real NASA C-MAPSS FD001 full intelligence pipeline traceability
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from apps.dataset_replay.adapter import CmapssAdapter
from contracts.mappers import ObservationMapper
from domain.entities import Observation, QualityFlag
from domain.intelligence import (
    AnomalySeverity,
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
    unit: str = "celsius",
    quality: QualityFlag = QualityFlag.GOOD,
    cycle: int = 1,
) -> Observation:
    return Observation(
        observation_id=uuid.uuid4().hex,
        device_id=device_id,
        sensor_id=sensor_id,
        timestamp=timestamp,
        value=value,
        unit=unit,
        quality=quality,
        metadata={"cycle": cycle, "device_id": device_id},
    )


# =========================================================================
# Scenario 1: S4-NOMINAL (Healthy Stable Asset)
# =========================================================================
def test_scenario_s4_nominal() -> None:
    repo = InMemoryTelemetryRepository()
    base_time = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
    device_id = "pump-01"
    sensors = ["temp-p1", "vib-p1", "press-p1"]
    nominal_vals = {"temp-p1": 50.0, "vib-p1": 1.5, "press-p1": 6.0}

    for cycle in range(1, 60):
        ts = base_time + timedelta(minutes=cycle)
        for s_id in sensors:
            repo.save_observation(_make_observation(device_id, s_id, ts, nominal_vals[s_id], cycle=cycle))

    health = HealthAssessmentService(repo).assess(device_id, "asset-pump")
    anomaly = AnomalyDetectionService(repo).detect(device_id, "asset-pump")
    diagnostic = DiagnosticService().diagnose(health, anomaly)
    finding = OperationalRiskService().evaluate(health, anomaly, diagnostic)

    assert finding.priority == OperationalPriority.NONE
    assert finding.risk_level == AnomalySeverity.NONE
    assert "no operational intervention" in finding.recommended_next_action.lower()
    assert finding.confidence >= 0.90
    assert finding.traceability_chain["finding_priority"] == "NONE"


# =========================================================================
# Scenario 2: S4-EARLY-DRIFT (Emerging Low-Magnitude Drift)
# =========================================================================
def test_scenario_s4_early_drift() -> None:
    repo = InMemoryTelemetryRepository()
    base_time = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
    device_id = "blower-02"

    for cycle in range(1, 51):
        ts = base_time + timedelta(minutes=cycle)
        repo.save_observation(_make_observation(device_id, "temp-b2", ts, 50.0, cycle=cycle))
        repo.save_observation(_make_observation(device_id, "vib-b2", ts, 2.0, cycle=cycle))

    for cycle in range(51, 61):
        ts = base_time + timedelta(minutes=cycle)
        drift = (cycle - 50) * 0.3
        repo.save_observation(_make_observation(device_id, "temp-b2", ts, 50.0 + drift, cycle=cycle))
        repo.save_observation(_make_observation(device_id, "vib-b2", ts, 2.0, cycle=cycle))

    health = HealthAssessmentService(repo).assess(device_id, "asset-blower")
    anomaly = AnomalyDetectionService(repo).detect(device_id, "asset-blower")
    diagnostic = DiagnosticService().diagnose(health, anomaly)
    finding = OperationalRiskService().evaluate(health, anomaly, diagnostic)

    # Should flag LOW or MEDIUM priority without jumping prematurely to CRITICAL
    assert finding.priority in (OperationalPriority.LOW, OperationalPriority.MEDIUM)
    assert "observation" in finding.recommended_next_action.lower() or "monitor" in finding.recommended_next_action.lower() or "review" in finding.recommended_next_action.lower()


# =========================================================================
# Scenario 3: S4-HIGH-RISK (Severe Persistent Multi-Subsystem Degradation)
# =========================================================================
def test_scenario_s4_high_risk() -> None:
    repo = InMemoryTelemetryRepository()
    base_time = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
    device_id = "hydraulic-03"

    for cycle in range(1, 51):
        ts = base_time + timedelta(minutes=cycle)
        repo.save_observation(_make_observation(device_id, "temp-h3", ts, 60.0, cycle=cycle))
        repo.save_observation(_make_observation(device_id, "vib-h3", ts, 1.5, cycle=cycle))
        repo.save_observation(_make_observation(device_id, "press-h3", ts, 150.0, cycle=cycle))

    for cycle in range(51, 86):
        ts = base_time + timedelta(minutes=cycle)
        drift = cycle - 50
        repo.save_observation(_make_observation(device_id, "temp-h3", ts, 60.0 + (drift * 1.5), cycle=cycle))
        repo.save_observation(_make_observation(device_id, "vib-h3", ts, 1.5 + (drift * 0.2), cycle=cycle))
        repo.save_observation(_make_observation(device_id, "press-h3", ts, 150.0 - (drift * 1.5), cycle=cycle))

    health = HealthAssessmentService(repo).assess(device_id, "asset-hydraulic")
    anomaly = AnomalyDetectionService(repo).detect(device_id, "asset-hydraulic")
    diagnostic = DiagnosticService().diagnose(health, anomaly)
    finding = OperationalRiskService().evaluate(health, anomaly, diagnostic)

    assert finding.priority in (OperationalPriority.HIGH, OperationalPriority.CRITICAL)
    assert finding.risk_level in (AnomalySeverity.HIGH, AnomalySeverity.CRITICAL)
    assert "maintenance" in finding.recommended_next_action.lower() or "inspection" in finding.recommended_next_action.lower() or "overhaul" in finding.recommended_next_action.lower()
    assert len(finding.traceability_chain["signal_evidence_residuals"]) >= 2


# =========================================================================
# Scenario 4: S4-MULTIPLE-HYPOTHESES (Competing Hypotheses)
# =========================================================================
def test_scenario_s4_multiple_hypotheses() -> None:
    repo = InMemoryTelemetryRepository()
    base_time = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
    device_id = "turbine-04"

    for cycle in range(1, 51):
        ts = base_time + timedelta(minutes=cycle)
        repo.save_observation(_make_observation(device_id, "temp_t4", ts, 70.0, cycle=cycle))
        repo.save_observation(_make_observation(device_id, "speed_t4", ts, 3000.0, cycle=cycle))

    for cycle in range(51, 65):
        ts = base_time + timedelta(minutes=cycle)
        repo.save_observation(_make_observation(device_id, "temp_t4", ts, 85.0, cycle=cycle))
        repo.save_observation(_make_observation(device_id, "speed_t4", ts, 3000.0, cycle=cycle))

    health = HealthAssessmentService(repo).assess(device_id, "asset-turbine")
    anomaly = AnomalyDetectionService(repo).detect(device_id, "asset-turbine")
    diagnostic = DiagnosticService().diagnose(health, anomaly)
    finding = OperationalRiskService().evaluate(health, anomaly, diagnostic)

    assert finding.priority in (OperationalPriority.LOW, OperationalPriority.MEDIUM)
    assert finding.traceability_chain["primary_hypothesis"] is not None


# =========================================================================
# Scenario 5: S4-LOW-CONFIDENCE (Constraining Escalation)
# =========================================================================
def test_scenario_s4_low_confidence() -> None:
    repo = InMemoryTelemetryRepository()
    base_time = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
    device_id = "sparse-05"

    # Only 3 observations
    for i in range(1, 4):
        repo.save_observation(_make_observation(device_id, "temp-s5", base_time + timedelta(minutes=i), 50.0, cycle=i))

    health = HealthAssessmentService(repo).assess(device_id, "asset-sparse")
    anomaly = AnomalyDetectionService(repo).detect(device_id, "asset-sparse")
    diagnostic = DiagnosticService().diagnose(health, anomaly)
    finding = OperationalRiskService().evaluate(health, anomaly, diagnostic)

    # Should not produce critical alarm when telemetry is missing
    assert finding.priority == OperationalPriority.LOW
    assert "quality" in finding.recommended_next_action.lower() or "connectivity" in finding.recommended_next_action.lower()


# =========================================================================
# Scenario 6: S4-RECOVERY (Resolution of Previous Alert)
# =========================================================================
def test_scenario_s4_recovery() -> None:
    repo = InMemoryTelemetryRepository()
    base_time = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
    device_id = "motor-06"

    # 1-50: Nominal
    for cycle in range(1, 51):
        ts = base_time + timedelta(minutes=cycle)
        repo.save_observation(_make_observation(device_id, "temp-m6", ts, 45.0, cycle=cycle))

    # 51-65: Temporary spike
    for cycle in range(51, 66):
        ts = base_time + timedelta(minutes=cycle)
        repo.save_observation(_make_observation(device_id, "temp-m6", ts, 85.0, cycle=cycle))

    # 66-95: Return to nominal
    for cycle in range(66, 96):
        ts = base_time + timedelta(minutes=cycle)
        repo.save_observation(_make_observation(device_id, "temp-m6", ts, 45.05, cycle=cycle))

    health = HealthAssessmentService(repo).assess(device_id, "asset-motor")
    anomaly = AnomalyDetectionService(repo).detect(device_id, "asset-motor")
    diagnostic = DiagnosticService().diagnose(health, anomaly)
    finding = OperationalRiskService().evaluate(health, anomaly, diagnostic)

    assert finding.priority == OperationalPriority.NONE
    assert finding.risk_level == AnomalySeverity.NONE
    assert "no operational intervention" in finding.recommended_next_action.lower()


# =========================================================================
# Scenario 7: S4-DETERMINISM (Idempotent Prioritization)
# =========================================================================
def test_scenario_s4_determinism() -> None:
    repo = InMemoryTelemetryRepository()
    base_time = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
    device_id = "repeater-07"

    for cycle in range(1, 60):
        ts = base_time + timedelta(minutes=cycle)
        repo.save_observation(_make_observation(device_id, "temp-r7", ts, 50.0 + cycle * 0.1, cycle=cycle))
        repo.save_observation(_make_observation(device_id, "vib-r7", ts, 2.0 + cycle * 0.02, cycle=cycle))

    health = HealthAssessmentService(repo).assess(device_id, "asset-repeater")
    anomaly = AnomalyDetectionService(repo).detect(device_id, "asset-repeater")
    diagnostic = DiagnosticService().diagnose(health, anomaly)

    f1 = OperationalRiskService().evaluate(health, anomaly, diagnostic)
    f2 = OperationalRiskService().evaluate(health, anomaly, diagnostic)

    assert f1.priority == f2.priority
    assert f1.risk_level == f2.risk_level
    assert f1.recommended_next_action == f2.recommended_next_action
    assert f1.confidence == f2.confidence
    assert f1.traceability_chain == f2.traceability_chain


# =========================================================================
# Scenario 8: S4-END-TO-END (NASA C-MAPSS FD001 Full Intelligence Chain)
# =========================================================================
def test_scenario_s4_end_to_end_cmapss() -> None:
    """Evaluate complete 4-stage pipeline against real NASA C-MAPSS Engine-001 lifecycle."""
    adapter = CmapssAdapter()
    if not adapter.config.dataset_file_path.exists():
        pytest.skip("C-MAPSS dataset file not available in test environment.")

    envelopes = list(adapter.iter_envelopes(limit_units=[1]))
    assert len(envelopes) >= 100

    # 1. Early stage nominal baseline (Cycles 1-45)
    repo_early = InMemoryTelemetryRepository()
    for env in envelopes[:45]:
        for p in env.observations:
            repo_early.save_observation(ObservationMapper.to_domain(p, env.source_device_id))

    h_early = HealthAssessmentService(repo_early).assess("engine-001", "turbofan-fleet")
    a_early = AnomalyDetectionService(repo_early).detect("engine-001", "turbofan-fleet")
    d_early = DiagnosticService().diagnose(h_early, a_early)
    f_early = OperationalRiskService().evaluate(h_early, a_early, d_early)

    assert f_early.priority == OperationalPriority.NONE
    assert f_early.risk_level == AnomalySeverity.NONE

    # 2. Late stage near end-of-life (All 120 cycles)
    repo_late = InMemoryTelemetryRepository()
    for env in envelopes:
        for p in env.observations:
            repo_late.save_observation(ObservationMapper.to_domain(p, env.source_device_id))

    h_late = HealthAssessmentService(repo_late).assess("engine-001", "turbofan-fleet")
    a_late = AnomalyDetectionService(repo_late).detect("engine-001", "turbofan-fleet")
    d_late = DiagnosticService().diagnose(h_late, a_late)
    f_late = OperationalRiskService().evaluate(h_late, a_late, d_late)

    assert f_late.priority in (OperationalPriority.HIGH, OperationalPriority.CRITICAL)
    assert f_late.risk_level in (AnomalySeverity.HIGH, AnomalySeverity.CRITICAL)
    assert f_late.primary_hypothesis is not None
    assert "maintenance" in f_late.recommended_next_action.lower() or "overhaul" in f_late.recommended_next_action.lower() or "inspection" in f_late.recommended_next_action.lower()

    # Complete backwards traceability verification
    chain = f_late.traceability_chain
    assert "finding_priority" in chain
    assert "risk_interpretation" in chain
    assert "primary_hypothesis" in chain
    assert "anomaly_detection" in chain
    assert "health_assessment" in chain
    assert len(chain["signal_evidence_residuals"]) >= 5
