"""
Aegis P2.S2 Verification Test Suite.
Tests anomaly and degradation detection across all required scenarios:
- S2-NORMAL: Nominal operating behavior
- S2-EARLY-DEGRADATION: Emerging, low-magnitude drift
- S2-CLEAR-DEGRADATION: Multi-signal persistent degradation
- S2-NOISY-DATA: Robustness against white noise and jitter
- S2-MISSING-DATA: Sparse/corrupted telemetry confidence penalty
- S2-RECOVERY: Resolution of abnormal status on return to baseline
- S2-REPLAY: Deterministic detection idempotency
- S2-GROUND-TRUTH-CMAPSS: Real NASA C-MAPSS FD001 run-to-failure lifecycle
"""
from __future__ import annotations

import random
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from apps.dataset_replay.adapter import CmapssAdapter
from contracts.mappers import ObservationMapper
from domain.entities import Observation, QualityFlag
from domain.intelligence import (
    AnomalyDetectionResult,
    AnomalySeverity,
    AnomalyStatus,
    TrendDirection,
)
from domain.repository import InMemoryTelemetryRepository
from intelligence.anomaly_service import (
    AnomalyDetectionService,
    AnomalyDetectorConfig,
)


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
# Scenario 1: S2-NORMAL (Nominal Asset Operation)
# =========================================================================

def test_scenario_s2_normal() -> None:
    repo = InMemoryTelemetryRepository()
    base_time = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
    device_id = "centrifuge-01"

    sensors = ["temp-c1", "vib-c1", "press-c1", "current-c1"]
    nominal_vals = {"temp-c1": 42.0, "vib-c1": 1.1, "press-c1": 3.5, "current-c1": 12.0}

    # 60 cycles of nominal operating data
    for cycle in range(1, 61):
        ts = base_time + timedelta(minutes=cycle)
        for s_id in sensors:
            val = nominal_vals[s_id] + ((cycle % 3) - 1) * 0.05
            repo.save_observation(_make_observation(device_id, s_id, ts, val, cycle=cycle))

    service = AnomalyDetectionService(repo)
    result = service.detect(device_id=device_id, asset_id="asset-centrifuge")

    assert result.status == AnomalyStatus.NOMINAL
    assert result.severity == AnomalySeverity.NONE
    assert result.anomaly_score < 0.25
    assert result.confidence >= 0.85
    assert len(result.evidence_list) == 4


# =========================================================================
# Scenario 2: S2-EARLY-DEGRADATION (Emerging Drift)
# =========================================================================

def test_scenario_s2_early_degradation() -> None:
    repo = InMemoryTelemetryRepository()
    base_time = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
    device_id = "blower-02"

    sensors = ["temp-b2", "vib-b2", "press-b2"]
    nominal_vals = {"temp-b2": 50.0, "vib-b2": 2.0, "press-b2": 5.0}

    # 1-50: Nominal baseline
    for cycle in range(1, 51):
        ts = base_time + timedelta(minutes=cycle)
        for s_id in sensors:
            repo.save_observation(_make_observation(device_id, s_id, ts, nominal_vals[s_id], cycle=cycle))

    # 51-60: Early mild drift on temp only (approx 2.2 sigma deviation)
    for cycle in range(51, 61):
        ts = base_time + timedelta(minutes=cycle)
        drift = (cycle - 50) * 0.25
        repo.save_observation(_make_observation(device_id, "temp-b2", ts, 50.0 + drift, cycle=cycle))
        repo.save_observation(_make_observation(device_id, "vib-b2", ts, 2.0, cycle=cycle))
        repo.save_observation(_make_observation(device_id, "press-b2", ts, 5.0, cycle=cycle))

    service = AnomalyDetectionService(repo)
    result = service.detect(device_id=device_id, asset_id="asset-blower")

    # Early stage should flag anomaly or low/medium severity without claiming false critical certainty
    assert result.status in (AnomalyStatus.ANOMALY_DETECTED, AnomalyStatus.DEGRADATION_DETECTED)
    assert result.severity in (AnomalySeverity.LOW, AnomalySeverity.MEDIUM)
    assert 0.25 <= result.anomaly_score < 0.80


# =========================================================================
# Scenario 3: S2-CLEAR-DEGRADATION (Multi-Signal Persistent Deterioration)
# =========================================================================

def test_scenario_s2_clear_degradation() -> None:
    repo = InMemoryTelemetryRepository()
    base_time = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
    device_id = "hydraulic-pack-03"

    # 1-50: Baseline
    for cycle in range(1, 51):
        ts = base_time + timedelta(minutes=cycle)
        repo.save_observation(_make_observation(device_id, "temp-hp3", ts, 60.0, cycle=cycle))
        repo.save_observation(_make_observation(device_id, "vib-hp3", ts, 1.5, cycle=cycle))
        repo.save_observation(_make_observation(device_id, "press-hp3", ts, 150.0, cycle=cycle))

    # 51-85: Heavy multi-signal deterioration (Temperature + Vibration escalating, Pressure dropping)
    for cycle in range(51, 86):
        ts = base_time + timedelta(minutes=cycle)
        drift = cycle - 50
        repo.save_observation(_make_observation(device_id, "temp-hp3", ts, 60.0 + (drift * 1.5), cycle=cycle))
        repo.save_observation(_make_observation(device_id, "vib-hp3", ts, 1.5 + (drift * 0.2), cycle=cycle))
        repo.save_observation(_make_observation(device_id, "press-hp3", ts, 150.0 - (drift * 2.0), cycle=cycle))

    service = AnomalyDetectionService(repo)
    result = service.detect(device_id=device_id, asset_id="asset-hydraulic")

    assert result.status == AnomalyStatus.DEGRADATION_DETECTED
    assert result.severity in (AnomalySeverity.HIGH, AnomalySeverity.CRITICAL)
    assert result.anomaly_score >= 0.75
    assert result.confidence >= 0.85
    # Structured inspectable evidence check
    assert len(result.evidence_list) == 3
    assert any("deviation" in e.reason.lower() for e in result.evidence_list)


# =========================================================================
# Scenario 4: S2-NOISY-DATA (Sensor Jitter / White Noise Robustness)
# =========================================================================

def test_scenario_s2_noisy_data() -> None:
    repo = InMemoryTelemetryRepository()
    base_time = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
    device_id = "noisy-sensor-unit-04"

    rng = random.Random(42)  # Seeded pseudo-random noise

    for cycle in range(1, 70):
        ts = base_time + timedelta(minutes=cycle)
        # Baseline with natural ±0.3 zero-mean Gaussian noise
        val1 = 100.0 + rng.gauss(0.0, 0.3)
        val2 = 25.0 + rng.gauss(0.0, 0.1)
        val3 = 4.0 + rng.gauss(0.0, 0.05)
        repo.save_observation(_make_observation(device_id, "temp-n4", ts, val1, cycle=cycle))
        repo.save_observation(_make_observation(device_id, "press-n4", ts, val2, cycle=cycle))
        repo.save_observation(_make_observation(device_id, "flow-n4", ts, val3, cycle=cycle))

    service = AnomalyDetectionService(repo)
    result = service.detect(device_id=device_id, asset_id="asset-noisy")

    # Noise should not produce false critical/high anomaly detection
    assert result.status == AnomalyStatus.NOMINAL
    assert result.severity == AnomalySeverity.NONE
    assert result.anomaly_score < 0.30


# =========================================================================
# Scenario 5: S2-MISSING-DATA (Sparse Telemetry / Confidence Penalty)
# =========================================================================

def test_scenario_s2_missing_and_corrupted_data() -> None:
    repo = InMemoryTelemetryRepository()
    base_time = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
    device_id = "sparse-node-05"

    # Only 3 observations total
    for i in range(1, 4):
        ts = base_time + timedelta(minutes=i)
        repo.save_observation(_make_observation(device_id, "temp-s5", ts, 50.0, cycle=i))

    service = AnomalyDetectionService(repo)
    result = service.detect(device_id=device_id, asset_id="asset-sparse")

    assert result.status == AnomalyStatus.UNKNOWN
    assert result.confidence == 0.0
    assert result.severity == AnomalySeverity.NONE


# =========================================================================
# Scenario 6: S2-RECOVERY (Resolution of Abnormal Status)
# =========================================================================

def test_scenario_s2_recovery() -> None:
    repo = InMemoryTelemetryRepository()
    base_time = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
    device_id = "generator-06"
    sensor_id = "temp-g6"

    # 1-50: Baseline (40.0)
    for cycle in range(1, 51):
        ts = base_time + timedelta(minutes=cycle)
        repo.save_observation(_make_observation(device_id, sensor_id, ts, 40.0, cycle=cycle))

    # 51-65: Temporary thermal spike (80.0)
    for cycle in range(51, 66):
        ts = base_time + timedelta(minutes=cycle)
        repo.save_observation(_make_observation(device_id, sensor_id, ts, 80.0, cycle=cycle))

    # 66-95: Cooled back down to nominal (40.05)
    for cycle in range(66, 96):
        ts = base_time + timedelta(minutes=cycle)
        repo.save_observation(_make_observation(device_id, sensor_id, ts, 40.05, cycle=cycle))

    # Evaluate with 20-cycle evaluation window (cycles 76-95, fully nominal)
    service = AnomalyDetectionService(repo, AnomalyDetectorConfig(eval_window=20))
    result = service.detect(device_id=device_id, asset_id="asset-generator")

    # Must resolve back to NOMINAL
    assert result.status == AnomalyStatus.NOMINAL
    assert result.severity == AnomalySeverity.NONE
    assert result.anomaly_score < 0.25


# =========================================================================
# Scenario 7: S2-REPLAY (Determinism & Idempotency)
# =========================================================================

def test_scenario_s2_replay_determinism() -> None:
    repo = InMemoryTelemetryRepository()
    base_time = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
    device_id = "turbine-07"

    for cycle in range(1, 65):
        ts = base_time + timedelta(minutes=cycle)
        repo.save_observation(_make_observation(device_id, "speed-t7", ts, 3600.0 + (cycle * 0.5), cycle=cycle))

    service = AnomalyDetectionService(repo)
    res1 = service.detect(device_id=device_id, asset_id="asset-turbine")
    res2 = service.detect(device_id=device_id, asset_id="asset-turbine")

    assert res1.status == res2.status
    assert res1.anomaly_score == res2.anomaly_score
    assert res1.confidence == res2.confidence
    assert res1.severity == res2.severity
    assert len(res1.evidence_list) == len(res2.evidence_list)


# =========================================================================
# Scenario 8: NASA C-MAPSS FD001 Ground-Truth Evaluation
# =========================================================================

def test_scenario_s2_cmapss_ground_truth_evaluation() -> None:
    """Evaluate detector on NASA C-MAPSS Engine-001 run-to-failure lifecycle."""
    adapter = CmapssAdapter()
    if not adapter.config.dataset_file_path.exists():
        pytest.skip("C-MAPSS dataset file not available in test environment.")

    envelopes = list(adapter.iter_envelopes(limit_units=[1]))
    assert len(envelopes) >= 100

    # 1. Early stage baseline (Cycles 1-50): Ground truth = NOMINAL
    repo_early = InMemoryTelemetryRepository()
    for env in envelopes[:50]:
        for p in env.observations:
            repo_early.save_observation(ObservationMapper.to_domain(p, env.source_device_id))

    service_early = AnomalyDetectionService(repo_early)
    early_result = service_early.detect("engine-001", asset_id="turbofan-fleet")

    assert early_result.status == AnomalyStatus.NOMINAL
    assert early_result.severity == AnomalySeverity.NONE
    assert early_result.anomaly_score < 0.25

    # 2. Late stage near end-of-life (All 120 cycles): Ground truth = DEGRADATION_DETECTED
    repo_late = InMemoryTelemetryRepository()
    for env in envelopes:
        for p in env.observations:
            repo_late.save_observation(ObservationMapper.to_domain(p, env.source_device_id))

    service_late = AnomalyDetectionService(repo_late)
    late_result = service_late.detect("engine-001", asset_id="turbofan-fleet")

    assert late_result.status == AnomalyStatus.DEGRADATION_DETECTED
    assert late_result.severity in (AnomalySeverity.HIGH, AnomalySeverity.CRITICAL)
    assert late_result.anomaly_score >= 0.70
    assert late_result.lead_cycles_estimate is not None
    assert late_result.lead_cycles_estimate > 0

    # Ensure evidence is inspectable
    degrading_evidence = [e for e in late_result.evidence_list if e.deviation_sigma > 2.0]
    assert len(degrading_evidence) >= 5, "Expected >=5 deviating sensors in degraded C-MAPSS engine"
