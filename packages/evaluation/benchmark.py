"""
P3 Evaluation — Fleet Benchmark Harness

Executes the existing Aegis intelligence pipeline across C-MAPSS engine
trajectories without modifying the underlying production services.

Pipeline flow per evaluation window:
  Telemetry (Observations up to evaluation cycle) -> InMemoryTelemetryRepository
    ↓
  HealthAssessmentService.assess(device_id, asset_id)
    ↓
  AnomalyDetectionService.detect(device_id, asset_id)
    ↓
  DiagnosticService.diagnose(health, anomaly)
    ↓
  OperationalRiskService.evaluate(health, anomaly, diagnostic)
    ↓
  EvaluationResult (immutable evaluation record)
"""

import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

from domain.entities import Observation, QualityFlag
from domain.repository import InMemoryTelemetryRepository

from packages.evaluation.models import EvaluationCase, EvaluationResult, GroundTruthLabel
from packages.intelligence.anomaly_service import AnomalyDetectionService
from packages.intelligence.diagnostic_service import DiagnosticService
from packages.intelligence.health_service import HealthAssessmentService
from packages.intelligence.risk_service import OperationalRiskService

MAPSS_SENSOR_NAMES = [
    "sensor-t2-inlet",
    "sensor-t24-lpc",
    "sensor-t30-hpc",
    "sensor-t50-lpt",
    "sensor-p2-inlet",
    "sensor-p15-bypass",
    "sensor-p30-hpc",
    "sensor-nf-fan",
    "sensor-nc-core",
    "sensor-epr",
    "sensor-ps30-static",
    "sensor-phi-fuel-flow",
    "sensor-nrf-fan",
    "sensor-nrc-core",
    "sensor-bpr",
    "sensor-far-ratio",
    "sensor-htbleed",
    "sensor-nf-dmd",
    "sensor-pcnfr-dmd",
    "sensor-w31-cool",
    "sensor-w32-cool",
]


class FleetBenchmarkHarness:
    """Benchmark orchestrator reusing protected Phase 2 intelligence services."""

    def load_cmapss_trajectories(
        self,
        file_path: str = "datasets/cmapss_fd001/train_FD001.txt",
    ) -> dict[str, list[Observation]]:
        """Load and convert raw C-MAPSS file into mapped domain Observations per unit."""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"C-MAPSS dataset file not found at: {file_path}")

        base_time = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
        trajectories: dict[str, list[Observation]] = {}

        with open(path, encoding="utf-8") as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) < 26:
                    continue

                unit_id = int(float(parts[0]))
                cycle = int(float(parts[1]))
                sensor_values = [float(v) for v in parts[5:26]]

                engine_id = f"engine-{unit_id:03d}"
                if engine_id not in trajectories:
                    trajectories[engine_id] = []

                timestamp = base_time + timedelta(hours=cycle)

                for s_name, val in zip(MAPSS_SENSOR_NAMES, sensor_values):
                    obs = Observation(
                        observation_id=str(uuid.uuid4()),
                        device_id=engine_id,
                        sensor_id=f"{s_name}-{engine_id}",
                        timestamp=timestamp,
                        value=val,
                        unit="raw",
                        quality=QualityFlag.GOOD,
                        metadata={"cycle": cycle, "sensor_name": s_name},
                    )
                    trajectories[engine_id].append(obs)

        return trajectories

    def evaluate_case(
        self,
        case: EvaluationCase,
        observations: list[Observation],
        asset_id: str = "turbofan-fleet",
    ) -> EvaluationResult:
        """Run the end-to-end intelligence chain on a cumulative trajectory up to window_end."""
        # Include history from start up to case.window_end so baseline window is preserved
        window_obs = [
            obs for obs in observations if obs.metadata.get("cycle", 0) <= case.window_end
        ]

        if not window_obs:
            return EvaluationResult(
                case=case,
                operational_state="UNKNOWN",
                anomaly_status="UNKNOWN",
                anomaly_score=0.0,
                diagnostic_status="UNKNOWN",
                priority="NONE",
                confidence=0.0,
                passed=False,
                reason="No telemetry observations in specified window",
            )

        # Build repository for cumulative trajectory
        repo = InMemoryTelemetryRepository()
        repo.save_batch(window_obs)
        device_id = window_obs[0].device_id

        # 1. Health Assessment
        health = HealthAssessmentService(repo).assess(device_id, asset_id)

        # 2. Anomaly Detection
        anomaly = AnomalyDetectionService(repo).detect(device_id, asset_id)

        # 3. Diagnostic Reasoning
        diagnosis = DiagnosticService().diagnose(health, anomaly)

        # 4. Operational Risk Evaluation
        finding = OperationalRiskService().evaluate(health, anomaly, diagnosis)

        # Determine pass/fail against ground truth expectations
        passed, reason = self._check_expectation(case.ground_truth, anomaly, finding)

        return EvaluationResult(
            case=case,
            operational_state=health.operational_state.value
            if hasattr(health.operational_state, "value")
            else str(health.operational_state),
            anomaly_status=anomaly.status.value
            if hasattr(anomaly.status, "value")
            else str(anomaly.status),
            anomaly_score=anomaly.anomaly_score,
            diagnostic_status=diagnosis.status.value
            if hasattr(diagnosis.status, "value")
            else str(diagnosis.status),
            priority=finding.priority.value
            if hasattr(finding.priority, "value")
            else str(finding.priority),
            confidence=finding.confidence,
            passed=passed,
            reason=reason,
        )

    def _check_expectation(
        self,
        ground_truth: GroundTruthLabel,
        anomaly,
        finding,
    ) -> tuple[bool, str]:
        """Verify if pipeline interpretation matches ground-truth contract."""
        anomaly_str = (
            anomaly.status.value if hasattr(anomaly.status, "value") else str(anomaly.status)
        )
        prio_str = (
            finding.priority.value if hasattr(finding.priority, "value") else str(finding.priority)
        )

        if ground_truth == GroundTruthLabel.NOMINAL:
            # Nominal engine should NOT trigger persistent degradation or CRITICAL/HIGH risk
            if "DEGRADATION" in anomaly_str.upper() or prio_str.upper() in ("HIGH", "CRITICAL"):
                return (
                    False,
                    f"False alarm on nominal window: anomaly={anomaly_str}, priority={prio_str}",
                )
            return True, "Nominal window correctly classified"

        elif ground_truth in (GroundTruthLabel.DEGRADING, GroundTruthLabel.FAILURE_BOUND):
            # Degrading engine SHOULD detect anomaly or degradation
            is_detected = (
                "DEGRADATION" in anomaly_str.upper()
                or "ANOMALY" in anomaly_str.upper()
                or anomaly.anomaly_score > 0.6
            )
            if is_detected:
                return True, "Degradation correctly detected"
            return (
                False,
                f"Missed degradation: anomaly={anomaly_str}, score={anomaly.anomaly_score:.2f}",
            )

        elif ground_truth == GroundTruthLabel.UNKNOWN:
            return True, "Unknown ground truth handled gracefully"

        return False, f"Unhandled ground truth label: {ground_truth}"

    def run_fleet_benchmark(
        self,
        cases: list[EvaluationCase],
        trajectories: dict[str, list[Observation]],
    ) -> list[EvaluationResult]:
        """Evaluate a full batch of cases across loaded engine trajectories."""
        results: list[EvaluationResult] = []
        for case in cases:
            engine_obs = trajectories.get(case.engine_id, [])
            res = self.evaluate_case(case, engine_obs)
            results.append(res)
        return results
