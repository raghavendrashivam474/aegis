"""
Aegis P2.S3 Verification Test Suite.
Tests deterministic diagnostic reasoning and explainable root-cause hypotheses:
- S3-NOMINAL: Healthy, stable operating baseline
- S3-SINGLE-SENSOR: Isolated single-sensor anomaly
- S3-CORRELATED-DEVIATION: Correlated subsystem degradation
- S3-TRANSIENT: Short-lived transient spike
- S3-PERSISTENT: Multi-cycle persistent degradation
- S3-CONFLICTING-EVIDENCE: Retaining and penalizing conflicting signals
- S3-INSUFFICIENT: Sparse/corrupted telemetry handling
- S3-DETERMINISM: Evaluation idempotency and reproducibility
- S3-CMAPSS-REAL: NASA C-MAPSS FD001 run-to-failure lifecycle diagnosis
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
    HypothesisCategory,
    OperationalState,
)
from domain.repository import InMemoryTelemetryRepository
from intelligence.anomaly_service import AnomalyDetectionService
from intelligence.diagnostic_service import DiagnosticService
from intelligence.health_service import HealthAssessmentService


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
# Scenario 1: S3-NOMINAL (Stable / Healthy Asset)
# =========================================================================
def test_scenario_s3_nominal() -> None:
    repo = InMemoryTelemetryRepository()
    base_time = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
    device_id = "pump-001"
    sensors = ["temp-p1", "vib-p1", "press-p1"]
    nominal_vals = {"temp-p1": 65.0, "vib-p1": 2.5, "press-p1": 4.0}

    for cycle in range(1, 60):
        ts = base_time + timedelta(minutes=cycle)
        for s_id in sensors:
            val = nominal_vals[s_id] + ((cycle % 3) - 1) * 0.05
            repo.save_observation(_make_observation(device_id, s_id, ts, val, cycle=cycle))

    health = HealthAssessmentService(repo).assess(device_id, "asset-pump")
    anomaly = AnomalyDetectionService(repo).detect(device_id, "asset-pump")
    diagnostic = DiagnosticService().diagnose(health, anomaly)

    assert diagnostic.status == DiagnosticStatus.NOMINAL
    assert diagnostic.overall_risk == AnomalySeverity.NONE
    assert diagnostic.primary_hypothesis is not None
    assert diagnostic.primary_hypothesis.category == HypothesisCategory.NOMINAL
    assert diagnostic.confidence >= 0.90
    assert len(diagnostic.evidence) == 3


# =========================================================================
# Scenario 2: S3-SINGLE-SENSOR (Isolated Sensor Anomaly)
# =========================================================================
def test_scenario_s3_single_sensor() -> None:
    repo = InMemoryTelemetryRepository()
    base_time = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
    device_id = "centrifuge-02"

    # 1-50: Nominal baseline for 3 sensors
    for cycle in range(1, 51):
        ts = base_time + timedelta(minutes=cycle)
        repo.save_observation(_make_observation(device_id, "temp-c2", ts, 40.0, cycle=cycle))
        repo.save_observation(_make_observation(device_id, "vib-c2", ts, 1.0, cycle=cycle))
        repo.save_observation(_make_observation(device_id, "press-c2", ts, 5.0, cycle=cycle))

    # 51-60: Only temp-c2 jumps to high reading; vib and press stay nominal
    for cycle in range(51, 61):
        ts = base_time + timedelta(minutes=cycle)
        repo.save_observation(_make_observation(device_id, "temp-c2", ts, 55.0, cycle=cycle))
        repo.save_observation(_make_observation(device_id, "vib-c2", ts, 1.0, cycle=cycle))
        repo.save_observation(_make_observation(device_id, "press-c2", ts, 5.0, cycle=cycle))

    health = HealthAssessmentService(repo).assess(device_id, "asset-centrifuge")
    anomaly = AnomalyDetectionService(repo).detect(device_id, "asset-centrifuge")
    diagnostic = DiagnosticService().diagnose(health, anomaly)

    # Should diagnose localized sensor anomaly, not systemic failure
    categories = [h.category for h in diagnostic.hypotheses]
    assert HypothesisCategory.LOCALIZED_SENSOR_ANOMALY in categories
    assert diagnostic.primary_hypothesis is not None
    assert len(diagnostic.primary_hypothesis.contradicting_evidence) >= 1


# =========================================================================
# Scenario 3: S3-CORRELATED-DEVIATION (Subsystem Drift)
# =========================================================================
def test_scenario_s3_correlated_deviation() -> None:
    repo = InMemoryTelemetryRepository()
    base_time = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
    device_id = "furnace-03"

    # 1-50: Baseline
    for cycle in range(1, 51):
        ts = base_time + timedelta(minutes=cycle)
        repo.save_observation(_make_observation(device_id, "temp_zone1", ts, 100.0, cycle=cycle))
        repo.save_observation(_make_observation(device_id, "temp_zone2", ts, 105.0, cycle=cycle))
        repo.save_observation(_make_observation(device_id, "vib_blower", ts, 2.0, cycle=cycle))

    # 51-70: Both thermal sensors escalate concurrently
    for cycle in range(51, 71):
        ts = base_time + timedelta(minutes=cycle)
        drift = (cycle - 50) * 1.2
        repo.save_observation(_make_observation(device_id, "temp_zone1", ts, 100.0 + drift, cycle=cycle))
        repo.save_observation(_make_observation(device_id, "temp_zone2", ts, 105.0 + drift, cycle=cycle))
        repo.save_observation(_make_observation(device_id, "vib_blower", ts, 2.0, cycle=cycle))

    health = HealthAssessmentService(repo).assess(device_id, "asset-furnace")
    anomaly = AnomalyDetectionService(repo).detect(device_id, "asset-furnace")
    diagnostic = DiagnosticService().diagnose(health, anomaly)

    assert diagnostic.status in (DiagnosticStatus.LIKELY_DEGRADATION, DiagnosticStatus.INVESTIGATING)
    assert diagnostic.primary_hypothesis is not None
    assert diagnostic.primary_hypothesis.category == HypothesisCategory.THERMAL_DEGRADATION
    assert len(diagnostic.primary_hypothesis.supporting_evidence) >= 2


# =========================================================================
# Scenario 4: S3-TRANSIENT (Brief Spike with Low Persistence)
# =========================================================================
def test_scenario_s3_transient() -> None:
    repo = InMemoryTelemetryRepository()
    base_time = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
    device_id = "motor-04"

    # 1-50: Baseline
    for cycle in range(1, 51):
        ts = base_time + timedelta(minutes=cycle)
        repo.save_observation(_make_observation(device_id, "temp-m4", ts, 50.0, cycle=cycle))
        repo.save_observation(_make_observation(device_id, "vib-m4", ts, 1.5, cycle=cycle))

    # 51-52: Brief spike on cycle 52 only
    repo.save_observation(_make_observation(device_id, "temp-m4", base_time + timedelta(minutes=51), 50.0, cycle=51))
    repo.save_observation(_make_observation(device_id, "vib-m4", base_time + timedelta(minutes=51), 1.5, cycle=51))
    repo.save_observation(_make_observation(device_id, "temp-m4", base_time + timedelta(minutes=52), 75.0, cycle=52))
    repo.save_observation(_make_observation(device_id, "vib-m4", base_time + timedelta(minutes=52), 1.5, cycle=52))

    health = HealthAssessmentService(repo).assess(device_id, "asset-motor")
    anomaly = AnomalyDetectionService(repo).detect(device_id, "asset-motor")
    diagnostic = DiagnosticService().diagnose(health, anomaly)

    # Diagnostic should classify as localized/transient and not claim critical system failure
    assert diagnostic.overall_risk in (AnomalySeverity.LOW, AnomalySeverity.MEDIUM)


# =========================================================================
# Scenario 5: S3-PERSISTENT (Multi-Signal Progressive Degradation)
# =========================================================================
def test_scenario_s3_persistent() -> None:
    repo = InMemoryTelemetryRepository()
    base_time = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
    device_id = "turbine-05"

    # 1-50: Baseline
    for cycle in range(1, 51):
        ts = base_time + timedelta(minutes=cycle)
        repo.save_observation(_make_observation(device_id, "temp-t5", ts, 80.0, cycle=cycle))
        repo.save_observation(_make_observation(device_id, "vib-t5", ts, 2.0, cycle=cycle))
        repo.save_observation(_make_observation(device_id, "press-t5", ts, 30.0, cycle=cycle))

    # 51-85: Heavy multi-signal deterioration
    for cycle in range(51, 86):
        ts = base_time + timedelta(minutes=cycle)
        drift = cycle - 50
        repo.save_observation(_make_observation(device_id, "temp-t5", ts, 80.0 + (drift * 1.5), cycle=cycle))
        repo.save_observation(_make_observation(device_id, "vib-t5", ts, 2.0 + (drift * 0.2), cycle=cycle))
        repo.save_observation(_make_observation(device_id, "press-t5", ts, 30.0 - (drift * 0.5), cycle=cycle))

    health = HealthAssessmentService(repo).assess(device_id, "asset-turbine")
    anomaly = AnomalyDetectionService(repo).detect(device_id, "asset-turbine")
    diagnostic = DiagnosticService().diagnose(health, anomaly)

    assert diagnostic.status == DiagnosticStatus.LIKELY_DEGRADATION
    assert diagnostic.overall_risk in (AnomalySeverity.HIGH, AnomalySeverity.CRITICAL)
    assert diagnostic.primary_hypothesis is not None
    assert diagnostic.context.max_persistence >= 5
    assert len(diagnostic.hypotheses) >= 1


# =========================================================================
# Scenario 6: S3-CONFLICTING-EVIDENCE (Contradictory Telemetry Signals)
# =========================================================================
def test_scenario_s3_conflicting_evidence() -> None:
    repo = InMemoryTelemetryRepository()
    base_time = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
    device_id = "compressor-06"

    # 1-50: Baseline
    for cycle in range(1, 51):
        ts = base_time + timedelta(minutes=cycle)
        repo.save_observation(_make_observation(device_id, "temp_inlet", ts, 45.0, cycle=cycle))
        repo.save_observation(_make_observation(device_id, "vib_c6", ts, 1.2, cycle=cycle))

    # 51-65: temp_inlet deviates strongly, but vib_c6 remains nominal
    for cycle in range(51, 66):
        ts = base_time + timedelta(minutes=cycle)
        repo.save_observation(_make_observation(device_id, "temp_inlet", ts, 68.0, cycle=cycle))
        repo.save_observation(_make_observation(device_id, "vib_c6", ts, 1.2, cycle=cycle))

    health = HealthAssessmentService(repo).assess(device_id, "asset-compressor")
    anomaly = AnomalyDetectionService(repo).detect(device_id, "asset-compressor")
    diagnostic = DiagnosticService().diagnose(health, anomaly)

    # Hypotheses should retain contradicting evidence
    has_contradiction = any(len(h.contradicting_evidence) > 0 for h in diagnostic.hypotheses)
    assert has_contradiction is True


# =========================================================================
# Scenario 7: S3-INSUFFICIENT (Sparse Telemetry)
# =========================================================================
def test_scenario_s3_insufficient_data() -> None:
    repo = InMemoryTelemetryRepository()
    base_time = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
    device_id = "sparse-07"

    # Only 3 observations
    for i in range(1, 4):
        repo.save_observation(_make_observation(device_id, "temp-s7", base_time + timedelta(minutes=i), 50.0, cycle=i))

    health = HealthAssessmentService(repo).assess(device_id, "asset-sparse")
    anomaly = AnomalyDetectionService(repo).detect(device_id, "asset-sparse")
    diagnostic = DiagnosticService().diagnose(health, anomaly)

    assert diagnostic.status == DiagnosticStatus.INSUFFICIENT_EVIDENCE
    assert diagnostic.confidence == 0.0
    assert "insufficient" in diagnostic.primary_finding.lower()


# =========================================================================
# Scenario 8: S3-DETERMINISM (Idempotent Results)
# =========================================================================
def test_scenario_s3_determinism() -> None:
    repo = InMemoryTelemetryRepository()
    base_time = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
    device_id = "repeater-08"

    for cycle in range(1, 60):
        ts = base_time + timedelta(minutes=cycle)
        repo.save_observation(_make_observation(device_id, "temp-r8", ts, 50.0 + cycle * 0.1, cycle=cycle))
        repo.save_observation(_make_observation(device_id, "vib-r8", ts, 2.0 + cycle * 0.02, cycle=cycle))

    health = HealthAssessmentService(repo).assess(device_id, "asset-repeater")
    anomaly = AnomalyDetectionService(repo).detect(device_id, "asset-repeater")

    diag1 = DiagnosticService().diagnose(health, anomaly)
    diag2 = DiagnosticService().diagnose(health, anomaly)

    assert diag1.status == diag2.status
    assert diag1.overall_risk == diag2.overall_risk
    assert diag1.confidence == diag2.confidence
    assert diag1.primary_finding == diag2.primary_finding
    assert len(diag1.hypotheses) == len(diag2.hypotheses)
    assert len(diag1.evidence) == len(diag2.evidence)


# =========================================================================
# Scenario 9: Real NASA C-MAPSS FD001 Lifecycle Diagnosis
# =========================================================================
def test_scenario_s3_cmapss_ground_truth_diagnosis() -> None:
    """Evaluate diagnostic layer on NASA C-MAPSS Engine-001 run-to-failure lifecycle."""
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

    assert d_early.status == DiagnosticStatus.NOMINAL
    assert d_early.overall_risk == AnomalySeverity.NONE

    # 2. Late stage near end-of-life (All 120 cycles)
    repo_late = InMemoryTelemetryRepository()
    for env in envelopes:
        for p in env.observations:
            repo_late.save_observation(ObservationMapper.to_domain(p, env.source_device_id))

    h_late = HealthAssessmentService(repo_late).assess("engine-001", "turbofan-fleet")
    a_late = AnomalyDetectionService(repo_late).detect("engine-001", "turbofan-fleet")
    d_late = DiagnosticService().diagnose(h_late, a_late)

    assert d_late.status == DiagnosticStatus.LIKELY_DEGRADATION
    assert d_late.overall_risk in (AnomalySeverity.HIGH, AnomalySeverity.CRITICAL)
    assert d_late.primary_hypothesis is not None
    assert len(d_late.evidence) >= 5
    assert len(d_late.hypotheses) >= 1
