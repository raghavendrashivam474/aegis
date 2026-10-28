"""
Aegis Intelligence Evaluation Lifecycle Service (P4.S2).
Orchestrates the full intelligence pipeline (Health -> Anomaly ->
Diagnostic -> Risk) for a registered asset and persists the result
as an IntelligenceSnapshot.

Architecture:
    TelemetryRepository (port)
          |
    IntelligenceEvaluationService
          |
          +--> HealthAssessmentService
          +--> AnomalyDetectionService
          +--> DiagnosticService
          +--> OperationalRiskService
          |
          v
    IntelligenceSnapshotRepository (port)

No SQL. No Streamlit. No hardcoded thresholds.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime

from domain.intelligence import (
    AnomalyDetectionResult,
    DiagnosticResult,
    HealthAssessment,
    OperationalFinding,
)
from domain.repository import (
    IntelligenceSnapshotRepository,
    TelemetryRepository,
)
from domain.snapshot import EvaluationStatus, IntelligenceSnapshot
from intelligence.anomaly_service import (
    AnomalyDetectionService,
    AnomalyDetectorConfig,
)
from intelligence.diagnostic_service import DiagnosticConfig, DiagnosticService
from intelligence.health_service import HealthAssessmentService, HealthConfig
from intelligence.risk_service import OperationalRiskService, RiskConfig

logger = logging.getLogger(__name__)


class EvaluationResult:
    """Outcome of an evaluation attempt, including the snapshot and any errors."""

    __slots__ = ("snapshot", "errors", "duration_ms")

    def __init__(
        self,
        snapshot: IntelligenceSnapshot,
        errors: list[str],
        duration_ms: float,
    ) -> None:
        self.snapshot = snapshot
        self.errors = errors
        self.duration_ms = duration_ms

    @property
    def success(self) -> bool:
        return self.snapshot.evaluation_status in (
            EvaluationStatus.SUCCESS,
            EvaluationStatus.INSUFFICIENT_EVIDENCE,
        )


class IntelligenceEvaluationService:
    """
    Application service that evaluates an asset intelligence and
    persists the resulting snapshot.

    Usage:
        eval_svc = IntelligenceEvaluationService(telemetry_repo, snapshot_repo)
        result = eval_svc.evaluate_asset("device-motor-01", "asset-pump-01")
    """

    def __init__(
        self,
        telemetry_repo: TelemetryRepository,
        snapshot_repo: IntelligenceSnapshotRepository,
        health_config: HealthConfig | None = None,
        anomaly_config: AnomalyDetectorConfig | None = None,
        diagnostic_config: DiagnosticConfig | None = None,
        risk_config: RiskConfig | None = None,
    ) -> None:
        self._telemetry_repo = telemetry_repo
        self._snapshot_repo = snapshot_repo
        self._health_config = health_config
        self._anomaly_config = anomaly_config
        self._diagnostic_config = diagnostic_config
        self._risk_config = risk_config

    def evaluate_asset(
        self,
        device_id: str,
        asset_id: str,
        persist: bool = True,
    ) -> EvaluationResult:
        """Run the full intelligence pipeline for one asset."""
        start_time = time.monotonic()
        errors: list[str] = []

        telemetry_start, telemetry_end = self._get_telemetry_window(device_id)
        health, anomaly, diagnostic, finding = self._run_pipeline_stages(
            device_id,
            asset_id,
            errors,
        )

        status = self._determine_status(health, anomaly, diagnostic, finding, errors)
        duration_ms = (time.monotonic() - start_time) * 1000.0

        snapshot = IntelligenceSnapshot.create(
            device_id=device_id,
            asset_id=asset_id,
            evaluation_status=status,
            health=health,
            anomaly=anomaly,
            diagnostic=diagnostic,
            finding=finding,
            telemetry_start=telemetry_start,
            telemetry_end=telemetry_end,
            evaluation_duration_ms=round(duration_ms, 2),
            errors=tuple(errors),
        )

        if persist:
            self._persist_snapshot(snapshot, device_id, errors)

        return EvaluationResult(
            snapshot=snapshot,
            errors=errors,
            duration_ms=duration_ms,
        )

    def evaluate_fleet(
        self,
        device_asset_pairs: list[tuple[str, str]],
        persist: bool = True,
    ) -> dict[str, EvaluationResult]:
        """Evaluate multiple devices and return results keyed by device_id."""
        results: dict[str, EvaluationResult] = {}
        for device_id, asset_id in device_asset_pairs:
            try:
                results[device_id] = self.evaluate_asset(
                    device_id,
                    asset_id,
                    persist=persist,
                )
            except Exception as exc:
                logger.error("Unexpected error evaluating %s: %s", device_id, exc)
                snap = IntelligenceSnapshot.create(
                    device_id=device_id,
                    asset_id=asset_id,
                    evaluation_status=EvaluationStatus.FAILED,
                    errors=(f"Unexpected: {exc}",),
                )
                results[device_id] = EvaluationResult(
                    snapshot=snap,
                    errors=[f"Unexpected: {exc}"],
                    duration_ms=0.0,
                )
        return results

    # --- Private helpers ---

    def _run_pipeline_stages(
        self,
        device_id: str,
        asset_id: str,
        errors: list[str],
    ) -> tuple[
        HealthAssessment | None,
        AnomalyDetectionResult | None,
        DiagnosticResult | None,
        OperationalFinding | None,
    ]:
        """Execute the four pipeline stages with error isolation."""
        health = self._run_stage(
            "Health",
            lambda: HealthAssessmentService(
                self._telemetry_repo,
                self._health_config,
            ).assess(device_id, asset_id),
            errors,
            device_id,
        )
        anomaly = self._run_stage(
            "Anomaly",
            lambda: AnomalyDetectionService(
                self._telemetry_repo,
                self._anomaly_config,
            ).detect(device_id, asset_id),
            errors,
            device_id,
        )

        diagnostic = self._run_diagnostic(health, anomaly, errors, device_id)
        finding = self._run_risk(health, anomaly, diagnostic, errors, device_id)

        return health, anomaly, diagnostic, finding

    def _run_diagnostic(
        self,
        health: HealthAssessment | None,
        anomaly: AnomalyDetectionResult | None,
        errors: list[str],
        device_id: str,
    ) -> DiagnosticResult | None:
        """Run diagnostic stage if upstream results are available."""
        if health is None or anomaly is None:
            errors.append("Diagnostic: skipped (missing upstream results)")
            return None
        return self._run_stage(
            "Diagnostic",
            lambda: DiagnosticService(self._diagnostic_config).diagnose(
                health,
                anomaly,
            ),
            errors,
            device_id,
        )

    def _run_risk(
        self,
        health: HealthAssessment | None,
        anomaly: AnomalyDetectionResult | None,
        diagnostic: DiagnosticResult | None,
        errors: list[str],
        device_id: str,
    ) -> OperationalFinding | None:
        """Run risk stage if all upstream results are available."""
        if health is None or anomaly is None or diagnostic is None:
            errors.append("Risk: skipped (missing upstream results)")
            return None
        return self._run_stage(
            "Risk",
            lambda: OperationalRiskService(self._risk_config).evaluate(
                health,
                anomaly,
                diagnostic,
            ),
            errors,
            device_id,
        )

    @staticmethod
    def _run_stage(
        stage_name: str,
        fn,
        errors: list[str],
        device_id: str,
    ):
        """Run a single pipeline stage with error capture."""
        try:
            return fn()
        except Exception as exc:
            errors.append(f"{stage_name}: {exc}")
            logger.warning("%s failed for %s: %s", stage_name, device_id, exc)
            return None

    def _persist_snapshot(
        self,
        snapshot: IntelligenceSnapshot,
        device_id: str,
        errors: list[str],
    ) -> None:
        """Persist a snapshot, recording any failure."""
        try:
            self._snapshot_repo.save(snapshot)
        except Exception as exc:
            errors.append(f"Persistence: {exc}")
            logger.error("Failed to persist snapshot for %s: %s", device_id, exc)

    def _get_telemetry_window(
        self,
        device_id: str,
    ) -> tuple[datetime | None, datetime | None]:
        """Determine the time range of available telemetry."""
        try:
            observations = self._telemetry_repo.get_observations(
                device_id=device_id,
                limit=10000,
            )
            if not observations:
                return None, None
            timestamps = [o.timestamp for o in observations]
            return min(timestamps), max(timestamps)
        except Exception:
            return None, None

    @staticmethod
    def _determine_status(
        health: HealthAssessment | None,
        anomaly: AnomalyDetectionResult | None,
        diagnostic: DiagnosticResult | None,
        finding: OperationalFinding | None,
        errors: list[str],
    ) -> EvaluationStatus:
        """Determine the evaluation completeness status."""
        if all([health, anomaly, diagnostic, finding]):
            if health.health_score == 0.0 and health.operational_state.value == "UNKNOWN":
                return EvaluationStatus.INSUFFICIENT_EVIDENCE
            return EvaluationStatus.SUCCESS
        if not any([health, anomaly]):
            return EvaluationStatus.FAILED if errors else EvaluationStatus.INSUFFICIENT_EVIDENCE
        return EvaluationStatus.PARTIAL_FAILURE
