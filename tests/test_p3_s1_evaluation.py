"""
P3.S1 — Fleet-Wide Intelligence Evaluation Tests

These tests verify that the evaluation harness correctly measures
the existing Aegis intelligence across a broader C-MAPSS population.

No intelligence service is modified by these tests.
"""

from packages.evaluation.benchmark import FleetBenchmarkHarness
from packages.evaluation.case_generator import (
    generate_engine_evaluation_cases,
    generate_fleet_evaluation_cases,
)
from packages.evaluation.metrics import (
    compute_detection_metrics,
    compute_fleet_summary,
    compute_lead_time_statistics,
)
from packages.evaluation.models import (
    DetectionMetrics,
    EvaluationCase,
    EvaluationResult,
    GroundTruthLabel,
)


class TestP3S1Baseline:
    """Verify the evaluation infrastructure itself before running fleet benchmarks."""

    def test_evaluation_package_imports(self):
        """Evaluation package must import without touching intelligence."""
        from packages.evaluation import benchmark, case_generator, metrics, models

        assert models is not None
        assert metrics is not None
        assert benchmark is not None
        assert case_generator is not None

    def test_ground_truth_labels_exist(self):
        assert GroundTruthLabel.NOMINAL.value == "NOMINAL"
        assert GroundTruthLabel.DEGRADING.value == "DEGRADING"
        assert GroundTruthLabel.FAILURE_BOUND.value == "FAILURE_BOUND"
        assert GroundTruthLabel.UNKNOWN.value == "UNKNOWN"

    def test_detection_metrics_empty(self):
        m = DetectionMetrics()
        assert m.true_positives == 0
        assert m.precision is None


class TestP3S1CaseGeneration:
    """Verify ground truth case generation across engine lifecycles."""

    def test_generate_cases_standard_engine(self):
        cases = generate_engine_evaluation_cases(
            engine_id="engine-001",
            total_cycles=200,
            nominal_cutoff_ratio=0.3,
            degradation_lead_cycles=30,
        )
        assert len(cases) == 2
        nominal_case = cases[0]
        assert nominal_case.ground_truth == GroundTruthLabel.NOMINAL
        assert nominal_case.window_start == 1
        assert nominal_case.window_end == 60

        degrading_case = cases[1]
        assert degrading_case.ground_truth == GroundTruthLabel.DEGRADING
        assert degrading_case.window_start == 170
        assert degrading_case.window_end == 200

    def test_generate_cases_insufficient_cycles(self):
        cases = generate_engine_evaluation_cases(
            engine_id="unit_short",
            total_cycles=5,
            min_window_size=10,
        )
        assert len(cases) == 1
        assert cases[0].ground_truth == GroundTruthLabel.UNKNOWN

    def test_generate_fleet_cases(self):
        fleet = [("engine-001", 150), ("engine-002", 220), ("engine-003", 8)]
        cases = generate_fleet_evaluation_cases(fleet, degradation_lead_cycles=25)
        assert len(cases) == 5


class TestP3S1MetricCalculations:
    """Verify precision, recall, F1, FPR, lead times and fleet summary calculations."""

    def _make_res(
        self,
        gt: GroundTruthLabel,
        status: str,
        score: float,
        prio: str = "NONE",
        passed: bool = True,
    ) -> EvaluationResult:
        c = EvaluationCase(engine_id="test", window_start=1, window_end=20, ground_truth=gt)
        return EvaluationResult(
            case=c,
            operational_state="NORMAL",
            anomaly_status=status,
            anomaly_score=score,
            diagnostic_status="NOMINAL",
            priority=prio,
            confidence=0.9,
            passed=passed,
        )

    def test_detection_metrics_calculation(self):
        results = [
            self._make_res(GroundTruthLabel.NOMINAL, "NOMINAL", 0.05),
            self._make_res(GroundTruthLabel.NOMINAL, "NOMINAL", 0.10),
            self._make_res(GroundTruthLabel.NOMINAL, "DEGRADATION_DETECTED", 0.85),
            self._make_res(GroundTruthLabel.DEGRADING, "DEGRADATION_DETECTED", 0.9),
            self._make_res(GroundTruthLabel.DEGRADING, "DEGRADATION_DETECTED", 0.7),
            self._make_res(GroundTruthLabel.DEGRADING, "NOMINAL", 0.1),
            self._make_res(GroundTruthLabel.UNKNOWN, "NOMINAL", 0.1),
        ]
        metrics = compute_detection_metrics(results)
        assert metrics.true_positives == 2
        assert metrics.true_negatives == 2
        assert metrics.false_positives == 1
        assert metrics.false_negatives == 1
        assert abs(metrics.precision - (2 / 3)) < 1e-4
        assert abs(metrics.recall - (2 / 3)) < 1e-4
        assert abs(metrics.f1 - (2 / 3)) < 1e-4
        assert abs(metrics.false_positive_rate - (1 / 3)) < 1e-4

    def test_lead_time_statistics(self):
        empty = compute_lead_time_statistics([])
        assert empty["count"] == 0
        assert empty["mean"] is None

        stats = compute_lead_time_statistics([25, 30, 35, 40, 50])
        assert stats["count"] == 5
        assert stats["mean"] == 36.0
        assert stats["median"] == 35.0
        assert stats["min"] == 25.0
        assert stats["max"] == 50.0

    def test_fleet_summary(self):
        results = [
            self._make_res(GroundTruthLabel.NOMINAL, "NOMINAL", 0.05, prio="NONE", passed=True),
            self._make_res(
                GroundTruthLabel.NOMINAL, "DEGRADATION_DETECTED", 0.9, prio="HIGH", passed=False
            ),
            self._make_res(
                GroundTruthLabel.DEGRADING,
                "DEGRADATION_DETECTED",
                0.9,
                prio="CRITICAL",
                passed=True,
            ),
        ]
        summary = compute_fleet_summary(results)
        assert summary["total_cases"] == 3
        assert summary["passed_cases"] == 2
        assert abs(summary["pass_rate"] - (2 / 3)) < 1e-4


class TestP3S1HarnessExecution:
    """Verify end-to-end harness execution using real C-MAPSS data."""

    @classmethod
    def setup_class(cls):
        cls.harness = FleetBenchmarkHarness()
        cls.trajectories = cls.harness.load_cmapss_trajectories()

    def test_load_cmapss_units(self):
        assert len(self.trajectories) >= 5
        assert "engine-001" in self.trajectories
        assert len(self.trajectories["engine-001"]) > 100

    def test_evaluate_single_engine_nominal_and_degraded(self):
        engine_001_obs = self.trajectories["engine-001"]
        max_cycle = max(obs.metadata.get("cycle", 0) for obs in engine_001_obs)

        # 1. Early nominal window (cycles 1-40)
        nominal_case = EvaluationCase(
            engine_id="engine-001",
            window_start=1,
            window_end=40,
            ground_truth=GroundTruthLabel.NOMINAL,
        )
        res_nom = self.harness.evaluate_case(nominal_case, engine_001_obs)
        assert res_nom.passed is True
        assert res_nom.anomaly_score < 0.6

        # 2. Late degraded window (last 35 cycles)
        degraded_case = EvaluationCase(
            engine_id="engine-001",
            window_start=max_cycle - 35,
            window_end=max_cycle,
            ground_truth=GroundTruthLabel.DEGRADING,
        )
        res_deg = self.harness.evaluate_case(degraded_case, engine_001_obs)
        assert res_deg.passed is True
        assert res_deg.anomaly_score > 0.6
        assert res_deg.priority in ("HIGH", "CRITICAL")

    def test_reproducibility_determinism(self):
        """REQ-P3S1-006: Run same evaluation twice, results MUST be bit-identical."""
        cases = [
            EvaluationCase("engine-001", 1, 40, GroundTruthLabel.NOMINAL),
            EvaluationCase("engine-001", 150, 192, GroundTruthLabel.DEGRADING),
            EvaluationCase("engine-002", 1, 30, GroundTruthLabel.NOMINAL),
        ]

        run_1 = self.harness.run_fleet_benchmark(cases, self.trajectories)
        run_2 = self.harness.run_fleet_benchmark(cases, self.trajectories)

        assert len(run_1) == len(run_2)
        for r1, r2 in zip(run_1, run_2):
            assert r1.anomaly_score == r2.anomaly_score
            assert r1.operational_state == r2.operational_state
            assert r1.anomaly_status == r2.anomaly_status
            assert r1.diagnostic_status == r2.diagnostic_status
            assert r1.priority == r2.priority
            assert r1.confidence == r2.confidence
            assert r1.passed == r2.passed
