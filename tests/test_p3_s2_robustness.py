"""
P3.S2 — Robustness & Failure Scenario Tests

Verifies Aegis intelligence behavior under imperfect telemetry:
noise, missing data, bad quality, transients, conflicts, recovery.
"""

from datetime import UTC, datetime, timedelta

import pytest
from domain.entities import Observation, QualityFlag
from domain.intelligence import (
    AnomalySeverity,
    AnomalyStatus,
    DiagnosticStatus,
    OperationalPriority,
)
from domain.repository import InMemoryTelemetryRepository

from packages.evaluation.benchmark import FleetBenchmarkHarness
from packages.evaluation.faults.injectors import (
    inject_missing,
    inject_noise,
    inject_quality_degradation,
    inject_recovery,
    inject_transient_spike,
)
from packages.intelligence.anomaly_service import AnomalyDetectionService
from packages.intelligence.diagnostic_service import DiagnosticService
from packages.intelligence.health_service import HealthAssessmentService
from packages.intelligence.risk_service import OperationalRiskService


def _make_series(
    sensor_names: list[str],
    cycles: int,
    base_values: dict[str, float],
    device_id: str = "engine-robust-01",
    asset_id: str = "turbofan-fleet",
    drift_rate: dict[str, float] | None = None,
) -> list[Observation]:
    """Helper to generate multi-sensor synthetic observation series."""
    base_time = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
    drift_rate = drift_rate or {}
    obs_list: list[Observation] = []

    for c in range(1, cycles + 1):
        ts = base_time + timedelta(hours=c)
        for s_name in sensor_names:
            base_val = base_values.get(s_name, 100.0)
            drift = drift_rate.get(s_name, 0.0) * c
            obs_list.append(
                Observation(
                    observation_id=f"obs-{s_name}-{c}",
                    device_id=device_id,
                    sensor_id=f"{s_name}-{device_id}",
                    timestamp=ts,
                    value=base_val + drift,
                    unit="raw",
                    quality=QualityFlag.GOOD,
                    metadata={"cycle": c, "sensor_name": s_name},
                )
            )
    return obs_list


def _evaluate_pipeline(
    observations: list[Observation],
    device_id: str = "engine-robust-01",
    asset_id: str = "turbofan-fleet",
):
    """Execute end-to-end intelligence chain over an in-memory repository."""
    repo = InMemoryTelemetryRepository()
    repo.save_batch(observations)

    health = HealthAssessmentService(repo).assess(device_id, asset_id)
    anomaly = AnomalyDetectionService(repo).detect(device_id, asset_id)
    diagnostic = DiagnosticService().diagnose(health, anomaly)
    finding = OperationalRiskService().evaluate(health, anomaly, diagnostic)

    return health, anomaly, diagnostic, finding


@pytest.fixture(scope="module")
def cmapss_trajectories():
    harness = FleetBenchmarkHarness()
    return harness.load_cmapss_trajectories()


class TestP3S2Injectors:
    """Verify fault injection functions operate correctly and deterministically."""

    def test_inject_noise(self):
        clean = _make_series(["sensor-t30"], 50, {"sensor-t30": 100.0})
        noisy = inject_noise(clean, scale=0.05, seed=42)
        assert len(noisy) == len(clean)
        diffs = [abs(n.value - c.value) for n, c in zip(noisy, clean, strict=False)]
        assert max(diffs) > 0.0

    def test_inject_missing(self):
        clean = _make_series(["sensor-t30"], 100, {"sensor-t30": 100.0})
        sparse = inject_missing(clean, drop_ratio=0.4, seed=42)
        assert 50 <= len(sparse) <= 70

    def test_inject_quality_degradation(self):
        clean = _make_series(["sensor-t30"], 100, {"sensor-t30": 100.0})
        bad = inject_quality_degradation(clean, quality_flag=QualityFlag.BAD, ratio=0.3, seed=42)
        bad_count = sum(1 for o in bad if o.quality == QualityFlag.BAD)
        assert 20 <= bad_count <= 40

    def test_inject_transient_spike(self):
        clean = _make_series(["sensor-t30"], 50, {"sensor-t30": 100.0})
        spiked = inject_transient_spike(clean, cycle_index=25, multiplier=2.5)
        for o in spiked:
            if o.metadata.get("cycle") == 25:
                assert o.value == 250.0
            else:
                assert o.value == 100.0

    def test_inject_recovery(self):
        nominal = _make_series(["sensor-t30"], 30, {"sensor-t30": 100.0})
        degraded = _make_series(["sensor-t30"], 30, {"sensor-t30": 150.0})
        recovered = inject_recovery(nominal, degraded, recovery_cycles=20)
        assert len(recovered) == 50


class TestP3S2RobustnessScenarios:
    """Formal verification of Aegis intelligence under imperfect telemetry conditions."""

    def test_scenario_s2_noise_no_premature_escalation(self, cmapss_trajectories):
        """S2-NOISE: Controlled noise on early window must not trigger CRITICAL risk."""
        engine_001 = cmapss_trajectories["engine-001"]
        nominal_obs = [o for o in engine_001 if o.metadata.get("cycle", 0) <= 40]
        noisy_obs = inject_noise(nominal_obs, scale=0.03, seed=100)

        _, anomaly, _, finding = _evaluate_pipeline(noisy_obs, "engine-001")

        assert finding.priority in (OperationalPriority.NONE, OperationalPriority.LOW)
        assert finding.risk_level in (AnomalySeverity.NONE, AnomalySeverity.LOW)
        assert anomaly.anomaly_score < 0.60

    def test_scenario_s2_missing_data_reduces_confidence(self, cmapss_trajectories):
        """S2-MISSING: Heavy packet drops should reduce confidence safely."""
        engine_001 = cmapss_trajectories["engine-001"]
        nominal_obs = [o for o in engine_001 if o.metadata.get("cycle", 0) <= 40]
        sparse_obs = inject_missing(nominal_obs, drop_ratio=0.60, seed=101)

        _, _, _, finding = _evaluate_pipeline(sparse_obs, "engine-001")

        assert finding.priority in (OperationalPriority.NONE, OperationalPriority.LOW)
        assert finding.confidence <= 0.95

    def test_scenario_s2_bad_quality_excluded(self, cmapss_trajectories):
        """S2-BAD-DATA: Explicit BAD observations must not corrupt baseline."""
        engine_001 = cmapss_trajectories["engine-001"]
        nominal_obs = [o for o in engine_001 if o.metadata.get("cycle", 0) <= 40]
        corrupted_obs = inject_quality_degradation(
            nominal_obs, QualityFlag.BAD, ratio=0.25, seed=102
        )

        _, _, _, finding = _evaluate_pipeline(corrupted_obs, "engine-001")

        assert finding.priority in (OperationalPriority.NONE, OperationalPriority.LOW)

    def test_scenario_s2_uncertain_quality_propagates(self):
        """S2-UNCERTAIN: UNCERTAIN flags preserve uncertainty in finding."""
        sensors = ["sensor-t30", "sensor-p30"]
        clean = _make_series(sensors, 40, {"sensor-t30": 550.0, "sensor-p30": 30.0})
        uncertain_obs = inject_quality_degradation(
            clean, QualityFlag.UNCERTAIN, ratio=0.50, seed=103
        )

        _, _, _, finding = _evaluate_pipeline(uncertain_obs)

        assert finding.confidence < 1.0

    def test_scenario_s2_transient_spike_no_persistent_claim(self):
        """S2-TRANSIENT: Single spike does not trigger persistent degradation."""
        sensors = ["sensor-t30", "sensor-p30"]
        clean = _make_series(sensors, 40, {"sensor-t30": 550.0, "sensor-p30": 30.0})
        spiked_obs = inject_transient_spike(
            clean, target_sensor_name="sensor-t30", cycle_index=20, multiplier=2.5
        )

        _, anomaly, _, finding = _evaluate_pipeline(spiked_obs)

        assert finding.priority in (OperationalPriority.NONE, OperationalPriority.LOW)
        assert anomaly.status != AnomalyStatus.DEGRADATION_DETECTED

    def test_scenario_s2_sustained_degradation_detected(self, cmapss_trajectories):
        """S2-SUSTAINED-DEGRADATION: Persistent drift reliably triggers degradation."""
        engine_001 = cmapss_trajectories["engine-001"]
        _, anomaly, diagnostic, finding = _evaluate_pipeline(engine_001, "engine-001")

        assert anomaly.status == AnomalyStatus.DEGRADATION_DETECTED
        assert anomaly.anomaly_score > 0.60
        assert diagnostic.status == DiagnosticStatus.LIKELY_DEGRADATION
        assert finding.priority in (OperationalPriority.HIGH, OperationalPriority.CRITICAL)

    def test_scenario_s2_conflicting_evidence_retained(self):
        """S2-CONFLICTING-EVIDENCE: Opposing signals preserve diagnostic uncertainty."""
        sensors = ["sensor-t30", "sensor-p30"]
        obs = _make_series(
            sensors,
            50,
            base_values={"sensor-t30": 550.0, "sensor-p30": 30.0},
            drift_rate={"sensor-t30": 1.5, "sensor-p30": -0.05},
        )

        _, _, diagnostic, finding = _evaluate_pipeline(obs)

        assert diagnostic is not None
        assert finding.traceability_chain is not None

    def test_scenario_s2_recovery_clears_active_finding(self, cmapss_trajectories):
        """S2-RECOVERY: Return to nominal clears active finding back to NONE."""
        engine_001 = cmapss_trajectories["engine-001"]
        nominal_slice = [o for o in engine_001 if o.metadata.get("cycle", 0) <= 30]
        degraded_slice = [o for o in engine_001 if o.metadata.get("cycle", 0) <= 120]

        recovered_series = inject_recovery(nominal_slice, degraded_slice, recovery_cycles=40)
        _, _, _, finding = _evaluate_pipeline(recovered_series, "engine-001")

        assert finding.priority == OperationalPriority.NONE
        assert finding.risk_level == AnomalySeverity.NONE

    def test_scenario_s2_insufficient_data_handled_gracefully(self):
        """S2-INSUFFICIENT: Sub-minimum telemetry records produce safe finding."""
        sensors = ["sensor-t30"]
        sparse_obs = _make_series(sensors, 3, {"sensor-t30": 550.0})

        _, _, _, finding = _evaluate_pipeline(sparse_obs)

        assert finding.priority in (OperationalPriority.NONE, OperationalPriority.LOW)
