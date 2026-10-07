"""
Aegis P3.S2 Showcase — Robustness & Failure Scenario Matrix

Executes the protected Phase 2 intelligence pipeline against 9 distinct
imperfect telemetry conditions and reports verified system behavior.
"""

import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from domain.entities import Observation, QualityFlag
from domain.intelligence import (
    AnomalySeverity,
    AnomalyStatus,
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


def _make_series(sensor_names, cycles, base_values, device_id="engine-robust-01", drift_rate=None):
    base_time = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
    drift_rate = drift_rate or {}
    obs_list = []
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


def _run_pipeline(observations, device_id="engine-001"):
    repo = InMemoryTelemetryRepository()
    repo.save_batch(observations)
    health = HealthAssessmentService(repo).assess(device_id, "turbofan-fleet")
    anomaly = AnomalyDetectionService(repo).detect(device_id, "turbofan-fleet")
    diag = DiagnosticService().diagnose(health, anomaly)
    risk = OperationalRiskService().evaluate(health, anomaly, diag)
    return health, anomaly, diag, risk


def run_showcase():
    print("=" * 82)
    print("  AEGIS PHASE 3.S2: ROBUSTNESS & FAILURE SCENARIO MATRIX")
    print("=" * 82)

    harness = FleetBenchmarkHarness()
    trajectories = harness.load_cmapss_trajectories()
    engine_001 = trajectories["engine-001"]
    nominal_slice = [o for o in engine_001 if o.metadata.get("cycle", 0) <= 40]

    matrix_rows = []

    # 1. S2-NOMINAL
    h, a, _, r = _run_pipeline(nominal_slice)
    p = r.priority == OperationalPriority.NONE and a.status == AnomalyStatus.NOMINAL
    matrix_rows.append(
        (
            "S2-NOMINAL",
            "Clean nominal data",
            "NORMAL / NONE",
            f"{h.operational_state.value} / {r.priority.value}",
            "PASS" if p else "FAIL",
        )
    )

    # 2. S2-NOISE
    noisy = inject_noise(nominal_slice, scale=0.03, seed=100)
    h, a, _, r = _run_pipeline(noisy)
    p = r.priority in (OperationalPriority.NONE, OperationalPriority.LOW) and a.anomaly_score < 0.60
    matrix_rows.append(
        (
            "S2-NOISE",
            "Gaussian noise (3% std)",
            "No premature escal.",
            f"Score {a.anomaly_score:.2f} / {r.priority.value}",
            "PASS" if p else "FAIL",
        )
    )

    # 3. S2-MISSING
    sparse = inject_missing(nominal_slice, drop_ratio=0.60, seed=101)
    h, _, _, r = _run_pipeline(sparse)
    p = r.priority in (OperationalPriority.NONE, OperationalPriority.LOW) and r.confidence <= 0.95
    matrix_rows.append(
        (
            "S2-MISSING",
            "60% packet drop",
            "Reduced confidence",
            f"Conf {r.confidence:.2f} / {r.priority.value}",
            "PASS" if p else "FAIL",
        )
    )

    # 4. S2-BAD-DATA
    bad = inject_quality_degradation(nominal_slice, QualityFlag.BAD, ratio=0.25, seed=102)
    h, _, _, r = _run_pipeline(bad)
    p = r.priority in (OperationalPriority.NONE, OperationalPriority.LOW)
    matrix_rows.append(
        (
            "S2-BAD-DATA",
            "25% BAD flags",
            "Bad data excluded",
            f"{h.operational_state.value} / {r.priority.value}",
            "PASS" if p else "FAIL",
        )
    )

    # 5. S2-UNCERTAIN
    clean_synth = _make_series(
        ["sensor-t30", "sensor-p30"], 40, {"sensor-t30": 550.0, "sensor-p30": 30.0}
    )
    unc = inject_quality_degradation(clean_synth, QualityFlag.UNCERTAIN, ratio=0.50, seed=103)
    _, _, _, r = _run_pipeline(unc, "engine-robust-01")
    p = r.confidence < 1.0
    matrix_rows.append(
        (
            "S2-UNCERTAIN",
            "50% UNCERTAIN flags",
            "Uncertainty preserved",
            f"Conf {r.confidence:.2f}",
            "PASS" if p else "FAIL",
        )
    )

    # 6. S2-TRANSIENT
    spiked = inject_transient_spike(
        clean_synth, target_sensor_name="sensor-t30", cycle_index=20, multiplier=2.5
    )
    _, a, _, r = _run_pipeline(spiked, "engine-robust-01")
    p = (
        r.priority in (OperationalPriority.NONE, OperationalPriority.LOW)
        and a.status != AnomalyStatus.DEGRADATION_DETECTED
    )
    matrix_rows.append(
        (
            "S2-TRANSIENT",
            "Single-cycle spike",
            "No persistent degrad.",
            f"{a.status.value} / {r.priority.value}",
            "PASS" if p else "FAIL",
        )
    )

    # 7. S2-SUSTAINED
    _, a, _, r = _run_pipeline(engine_001)
    p = a.status == AnomalyStatus.DEGRADATION_DETECTED and r.priority in (
        OperationalPriority.HIGH,
        OperationalPriority.CRITICAL,
    )
    matrix_rows.append(
        (
            "S2-SUSTAINED",
            "Run-to-failure drift",
            "Degradation escalated",
            f"{a.status.value} / {r.priority.value}",
            "PASS" if p else "FAIL",
        )
    )

    # 8. S2-CONFLICT
    conf_series = _make_series(
        ["sensor-t30", "sensor-p30"],
        50,
        {"sensor-t30": 550.0, "sensor-p30": 30.0},
        drift_rate={"sensor-t30": 1.5, "sensor-p30": -0.05},
    )
    _, _, d, r = _run_pipeline(conf_series, "engine-robust-01")
    p = d is not None and r.traceability_chain is not None
    matrix_rows.append(
        (
            "S2-CONFLICT",
            "Opposing sensors",
            "Evidence retained",
            "Chain verified",
            "PASS" if p else "FAIL",
        )
    )

    # 9. S2-RECOVERY
    deg_slice = [o for o in engine_001 if o.metadata.get("cycle", 0) <= 120]
    rec_series = inject_recovery(nominal_slice[:30], deg_slice, recovery_cycles=40)
    _, _, _, r = _run_pipeline(rec_series, "engine-001")
    p = r.priority == OperationalPriority.NONE and r.risk_level == AnomalySeverity.NONE
    matrix_rows.append(
        (
            "S2-RECOVERY",
            "Degraded -> Nominal",
            "Finding cleared",
            f"{r.priority.value} / {r.risk_level.value}",
            "PASS" if p else "FAIL",
        )
    )

    # 10. S2-INSUFFICIENT
    short_series = _make_series(["sensor-t30"], 3, {"sensor-t30": 550.0})
    h, _, _, r = _run_pipeline(short_series, "engine-robust-01")
    p = r.priority in (OperationalPriority.NONE, OperationalPriority.LOW)
    matrix_rows.append(
        (
            "S2-INSUFFICIENT",
            "Only 3 observations",
            "Graceful uncertainty",
            f"{h.operational_state.value} / {r.priority.value}",
            "PASS" if p else "FAIL",
        )
    )

    print(
        f"{'Scenario':<16} | {'Condition':<24} | {'Expected':<22} | {'Actual':<22} | {'Status':<6}"
    )
    print("-" * 100)
    for s_id, cond, exp, act, st in matrix_rows:
        print(f"{s_id:<16} | {cond:<24} | {exp:<22} | {act:<22} | {st:<6}")
    print("=" * 100)


if __name__ == "__main__":
    run_showcase()
