"""
Aegis P2.S1 Verification Test Suite.
Tests operational state and asset health assessment across all defined scenarios:
- S1-NORMAL: Healthy, stable operating baseline
- S1-DEGRADING: Progressive telemetry degradation
- S1-INSUFFICIENT-DATA: Sparse observations
- S1-BAD-DATA: Degraded data quality / BAD quality flags
- S1-RECOVERY: Return to nominal behavior
- S1-DETERMINISM: Repeatable assessments
- S1-CMAPSS-REAL: Real C-MAPSS dataset engine lifecycle evaluation
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from apps.dataset_replay.adapter import CmapssAdapter
from domain.entities import Observation, QualityFlag
from domain.intelligence import (
    HealthAssessment,
    OperationalState,
    TrendDirection,
)
from domain.repository import InMemoryTelemetryRepository
from intelligence.health_service import HealthAssessmentService, HealthConfig
from intelligence.statistics import (
    compute_deviation_score,
    compute_mean,
    compute_sensor_health,
    compute_std,
    compute_trend,
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
# Unit Tests: Statistical Foundation
# =========================================================================

def test_pure_statistics_mean_and_std() -> None:
    values = [10.0, 10.0, 10.0, 10.0]
    assert compute_mean(values) == 10.0
    assert compute_std(values) == 0.0

    sample = [2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0]
    mean = compute_mean(sample)
    std = compute_std(sample, mean)
    assert round(mean, 2) == 5.0
    assert round(std, 2) == 2.14


def test_pure_statistics_trend_detection() -> None:
    # Stable series
    stable = [100.0, 100.1, 99.9, 100.0, 100.05, 99.95]
    assert compute_trend(stable, slope_threshold=0.01) == TrendDirection.STABLE

    # Increasing series
    increasing = [100.0, 102.0, 105.0, 108.0, 112.0, 116.0]
    assert compute_trend(increasing, slope_threshold=0.01) == TrendDirection.INCREASING

    # Decreasing series
    decreasing = [100.0, 97.0, 94.0, 91.0, 87.0, 82.0]
    assert compute_trend(decreasing, slope_threshold=0.01) == TrendDirection.DECREASING

    # Too few points
    assert compute_trend([1.0, 2.0]) == TrendDirection.UNKNOWN


def test_pure_statistics_deviation_and_health_mapping() -> None:
    # 0 deviation -> 100 health
    assert compute_deviation_score(100.0, 100.0, 2.0) == 0.0
    assert compute_sensor_health(0.0) == 100.0

    # 2 sigma deviation with weight 15 -> 70 health
    dev_2sigma = compute_deviation_score(104.0, 100.0, 2.0)
    assert dev_2sigma == 2.0
    assert compute_sensor_health(dev_2sigma, weight=15.0) == 70.0

    # Extreme deviation -> clamped at 0.0
    dev_extreme = compute_deviation_score(200.0, 100.0, 2.0)
    assert compute_sensor_health(dev_extreme, weight=15.0) == 0.0


# =========================================================================
# Scenario 1: S1-NORMAL (Stable / Healthy Asset)
# =========================================================================

def test_scenario_s1_normal() -> None:
    repo = InMemoryTelemetryRepository()
    base_time = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
    device_id = "pump-001"

    # Feed 70 cycles of stable readings across 3 sensors
    sensors = ["temp-p1", "vib-p1", "press-p1"]
    nominal_vals = {"temp-p1": 65.0, "vib-p1": 2.5, "press-p1": 4.0}

    for cycle in range(1, 71):
        ts = base_time + timedelta(minutes=cycle)
        for s_id in sensors:
            val = nominal_vals[s_id] + ((cycle % 3) - 1) * 0.1
            repo.save_observation(_make_observation(device_id, s_id, ts, val, cycle=cycle))

    service = HealthAssessmentService(repo)
    assessment = service.assess(device_id=device_id, asset_id="asset-water-pump")

    assert assessment.operational_state == OperationalState.NORMAL
    assert assessment.health_score >= 85.0
    assert assessment.confidence >= 0.85
    assert assessment.trend == TrendDirection.STABLE
    assert len(assessment.sensor_signals) == 3


# =========================================================================
# Scenario 2: S1-DEGRADING (Progressively Deteriorating Telemetry)
# =========================================================================

def test_scenario_s1_degrading() -> None:
    repo = InMemoryTelemetryRepository()
    base_time = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
    device_id = "compressor-002"
    sensor_id = "temp-c2"

    # First 50 cycles: Healthy baseline (mean ~ 70.0, small noise)
    for cycle in range(1, 51):
        ts = base_time + timedelta(minutes=cycle)
        val = 70.0 + (0.1 if cycle % 2 == 0 else -0.1)
        repo.save_observation(_make_observation(device_id, sensor_id, ts, val, cycle=cycle))

    # Next 30 cycles (51-80): Rapid temperature escalation
    for cycle in range(51, 81):
        ts = base_time + timedelta(minutes=cycle)
        val = 70.0 + (cycle - 50) * 1.5  # Reaches 115.0
        repo.save_observation(_make_observation(device_id, sensor_id, ts, val, cycle=cycle))

    service = HealthAssessmentService(repo)
    assessment = service.assess(device_id=device_id, asset_id="asset-compressor")

    assert assessment.operational_state in (OperationalState.DEGRADING, OperationalState.CRITICAL)
    assert assessment.health_score < 60.0
    assert assessment.trend == TrendDirection.INCREASING
    assert "deviation" in assessment.evidence_summary.lower()


# =========================================================================
# Scenario 3: S1-INSUFFICIENT-DATA (Sparse Observations)
# =========================================================================

def test_scenario_s1_insufficient_data() -> None:
    repo = InMemoryTelemetryRepository()
    base_time = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
    device_id = "valve-003"

    # Only 4 observations total (less than default min_baseline_samples=10)
    for i in range(1, 5):
        ts = base_time + timedelta(minutes=i)
        repo.save_observation(_make_observation(device_id, "flow-v3", ts, 12.0, cycle=i))

    service = HealthAssessmentService(repo)
    assessment = service.assess(device_id=device_id, asset_id="asset-valve")

    assert assessment.operational_state == OperationalState.UNKNOWN
    assert assessment.confidence < 0.4
    assert len(assessment.sensor_signals) == 1
    assert assessment.sensor_signals[0].insufficient_data is True


# =========================================================================
# Scenario 4: S1-BAD-DATA (Filtering and Confidence Penalty)
# =========================================================================

def test_scenario_s1_bad_data_handling() -> None:
    repo = InMemoryTelemetryRepository()
    base_time = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
    device_id = "sensor-unit-004"
    sensor_id = "vibration-raw"

    # 40 observations total, but 35 are flagged QualityFlag.BAD
    for i in range(1, 41):
        ts = base_time + timedelta(minutes=i)
        quality = QualityFlag.BAD if i > 5 else QualityFlag.GOOD
        val = 9999.0 if quality == QualityFlag.BAD else 2.5
        repo.save_observation(_make_observation(device_id, sensor_id, ts, val, quality=quality, cycle=i))

    service = HealthAssessmentService(repo)
    assessment = service.assess(device_id=device_id, asset_id="asset-unit-4")

    # Due to fewer than 10 GOOD observations, insufficient_data flag triggers
    assert assessment.operational_state == OperationalState.UNKNOWN
    assert assessment.confidence < 0.4
    assert assessment.sensor_signals[0].insufficient_data is True


# =========================================================================
# Scenario 5: S1-RECOVERY (Return towards Healthy Baseline)
# =========================================================================

def test_scenario_s1_recovery() -> None:
    repo = InMemoryTelemetryRepository()
    base_time = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
    device_id = "motor-005"
    sensor_id = "temp-m5"

    # 1-50: Healthy baseline (50.0)
    for cycle in range(1, 51):
        ts = base_time + timedelta(minutes=cycle)
        repo.save_observation(_make_observation(device_id, sensor_id, ts, 50.0, cycle=cycle))

    # 51-65: Temporary spike (degradation period)
    for cycle in range(51, 66):
        ts = base_time + timedelta(minutes=cycle)
        repo.save_observation(_make_observation(device_id, sensor_id, ts, 85.0, cycle=cycle))

    # 66-90: Cooled back down to nominal baseline (50.0)
    for cycle in range(66, 91):
        ts = base_time + timedelta(minutes=cycle)
        repo.save_observation(_make_observation(device_id, sensor_id, ts, 50.1, cycle=cycle))

    # Evaluate using current window of 20 (cycles 71-90)
    service = HealthAssessmentService(repo, HealthConfig(current_window=20))
    assessment = service.assess(device_id=device_id, asset_id="asset-motor")

    # Assessment should recognize recovery to nominal operating range
    assert assessment.health_score >= 80.0
    assert assessment.trend in (TrendDirection.STABLE, TrendDirection.DECREASING)


# =========================================================================
# Scenario 6: S1-DETERMINISM (Idempotent Results)
# =========================================================================

def test_scenario_s1_determinism() -> None:
    repo = InMemoryTelemetryRepository()
    base_time = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
    device_id = "turbine-006"

    for cycle in range(1, 60):
        ts = base_time + timedelta(minutes=cycle)
        repo.save_observation(_make_observation(device_id, "rpm-t6", ts, 3000.0 + (cycle * 0.2), cycle=cycle))

    service = HealthAssessmentService(repo)
    res1 = service.assess(device_id=device_id, asset_id="asset-turbine")
    res2 = service.assess(device_id=device_id, asset_id="asset-turbine")

    assert res1.health_score == res2.health_score
    assert res1.confidence == res2.confidence
    assert res1.operational_state == res2.operational_state
    assert res1.trend == res2.trend
    assert len(res1.sensor_signals) == len(res2.sensor_signals)


# =========================================================================
# Scenario 7: Real NASA C-MAPSS FD001 Lifecycle Evaluation
# =========================================================================

def test_scenario_s1_cmapss_real_data_evaluation() -> None:
    """Evaluate HealthAssessmentService against real NASA C-MAPSS engine-001 lifecycle."""
    adapter = CmapssAdapter()
    if not adapter.config.dataset_file_path.exists():
        pytest.skip("C-MAPSS dataset file not available in test environment.")

    # Ingest engine-001 records into an in-memory repository
    early_repo = InMemoryTelemetryRepository()
    full_repo = InMemoryTelemetryRepository()

    from contracts.mappers import ObservationMapper

    envelopes = list(adapter.iter_envelopes(limit_units=[1]))
    assert len(envelopes) > 100, f"Expected >100 cycles for engine 1, got {len(envelopes)}"

    # Early stage: first 50 cycles
    for env in envelopes[:50]:
        for p in env.observations:
            early_repo.save_observation(ObservationMapper.to_domain(p, env.source_device_id))

    # Full lifecycle: all cycles up to failure (~192 cycles)
    for env in envelopes:
        for p in env.observations:
            full_repo.save_observation(ObservationMapper.to_domain(p, env.source_device_id))

    service_early = HealthAssessmentService(early_repo)
    assessment_early = service_early.assess("engine-001", asset_id="turbofan-fleet")

    service_full = HealthAssessmentService(full_repo)
    assessment_late = service_full.assess("engine-001", asset_id="turbofan-fleet")

    # Verification:
    # 1. Early stage of engine-001 is healthy
    assert assessment_early.operational_state == OperationalState.NORMAL
    assert assessment_early.health_score >= 80.0
    assert assessment_early.confidence >= 0.8

    # 2. Late stage near failure shows distinct degradation
    assert assessment_late.health_score < assessment_early.health_score
    assert assessment_late.operational_state in (OperationalState.DEGRADING, OperationalState.CRITICAL)
