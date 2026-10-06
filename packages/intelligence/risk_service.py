"""
Aegis Intelligence — Operational Risk & Prioritization Service (P2.S4).
Synthesizes Health (P2.S1), Anomaly (P2.S2), and Diagnostic (P2.S3) snapshots
into prioritized operational findings, explainable backwards traceability chains,
and advisory recommendations for human operators.

Architecture:
    HealthAssessment (P2.S1) ──────┐
    AnomalyDetectionResult (P2.S2) ┼──> OperationalRiskService ──> OperationalFinding
    DiagnosticResult (P2.S3) ──────┘

Pure application service. Zero SQL. Fully deterministic.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from domain.intelligence import (
    AnomalyDetectionResult,
    AnomalySeverity,
    AnomalyStatus,
    DiagnosticHypothesis,
    DiagnosticResult,
    DiagnosticStatus,
    HealthAssessment,
    HypothesisCategory,
    OperationalFinding,
    OperationalPriority,
    OperationalState,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RiskConfig:
    """Tunable thresholds for operational risk prioritization."""
    critical_health_threshold: float = 50.0
    degrading_health_threshold: float = 75.0
    high_anomaly_threshold: float = 0.70
    min_confidence_for_critical: float = 0.40
    min_confidence_for_high: float = 0.35


class OperationalRiskService:
    """
    Application service that prioritizes asset findings and produces actionable advisory steps.
    Usage:
        service = OperationalRiskService()
        finding = service.evaluate(health, anomaly, diagnostic)
    """

    def __init__(self, config: RiskConfig | None = None) -> None:
        self._config = config or RiskConfig()

    def evaluate(
        self,
        health: HealthAssessment,
        anomaly: AnomalyDetectionResult,
        diagnostic: DiagnosticResult,
    ) -> OperationalFinding:
        """
        Evaluate full intelligence pipeline state and generate a prioritized operational finding.
        """
        # Step 1: Handle Insufficient Evidence / Unknown state
        if (
            diagnostic.status == DiagnosticStatus.INSUFFICIENT_EVIDENCE
            or health.operational_state == OperationalState.UNKNOWN
            or anomaly.status == AnomalyStatus.UNKNOWN
        ):
            return self._insufficient_data_finding(health, anomaly, diagnostic)

        # Step 2: Handle Nominal / Healthy state
        if (
            health.operational_state == OperationalState.NORMAL
            and anomaly.status == AnomalyStatus.NOMINAL
            and diagnostic.status == DiagnosticStatus.NOMINAL
        ):
            return self._nominal_finding(health, anomaly, diagnostic)

        # Step 3: Compute deterministic operational priority
        priority = self._determine_priority(health, anomaly, diagnostic)

        # Step 4: Generate advisory recommended next action
        recommended_action = self._generate_recommended_action(
            priority=priority,
            diagnostic=diagnostic,
            anomaly=anomaly,
            health=health,
        )

        # Step 5: Build backward explainability traceability chain
        traceability = self._build_traceability_chain(health, anomaly, diagnostic, priority)

        # Step 6: Construct finding summary
        summary = self._build_summary(priority, diagnostic, health, anomaly)

        # Step 7: Composite operational confidence
        composite_conf = round(
            (0.35 * health.confidence) + (0.35 * anomaly.confidence) + (0.30 * diagnostic.confidence),
            4,
        )

        supporting_evidence = ()
        if diagnostic.primary_hypothesis and diagnostic.primary_hypothesis.supporting_evidence:
            supporting_evidence = diagnostic.primary_hypothesis.supporting_evidence
        elif diagnostic.evidence:
            supporting_evidence = tuple(
                e.observation for e in diagnostic.evidence if e.deviation_sigma >= 1.5
            )

        return OperationalFinding(
            asset_id=health.asset_id,
            device_id=health.device_id,
            priority=priority,
            risk_level=diagnostic.overall_risk,
            summary=summary,
            operational_state=health.operational_state,
            health_score=health.health_score,
            anomaly_status=anomaly.status,
            anomaly_score=anomaly.anomaly_score,
            diagnostic_status=diagnostic.status,
            diagnostic_confidence=diagnostic.confidence,
            primary_hypothesis=diagnostic.primary_hypothesis,
            supporting_evidence=supporting_evidence,
            recommended_next_action=recommended_action,
            lead_cycles_estimate=anomaly.lead_cycles_estimate,
            confidence=composite_conf,
            traceability_chain=traceability,
            evaluated_at=datetime.now(UTC),
            limitations=diagnostic.limitations,
            metadata={
                "affected_sensors_count": diagnostic.context.affected_sensors,
                "total_sensors_count": diagnostic.context.total_sensors,
                "max_persistence": diagnostic.context.max_persistence,
            },
        )

    def _determine_priority(
        self,
        health: HealthAssessment,
        anomaly: AnomalyDetectionResult,
        diagnostic: DiagnosticResult,
    ) -> OperationalPriority:
        """
        Determine operational priority deterministically using a transparent rule matrix.
        Includes safety bounds: priority is constrained if evidentiary confidence is low.
        """
        cfg = self._config
        risk = diagnostic.overall_risk
        diag_conf = diagnostic.confidence

        # Rule 1: Low-confidence constraint — cap escalation if data is uncertain
        if diag_conf < cfg.min_confidence_for_high:
            if risk in (AnomalySeverity.CRITICAL, AnomalySeverity.HIGH):
                return OperationalPriority.MEDIUM
            return OperationalPriority.LOW

        # Rule 2: Competing Hypotheses — cap escalation to MEDIUM for isolation checks
        if diagnostic.status == DiagnosticStatus.MULTIPLE_POSSIBLE_CAUSES:
            return OperationalPriority.MEDIUM

        # Rule 3: Critical Priority Condition
        if (
            (health.health_score < cfg.critical_health_threshold or risk == AnomalySeverity.CRITICAL)
            and anomaly.status == AnomalyStatus.DEGRADATION_DETECTED
            and diag_conf >= cfg.min_confidence_for_critical
        ):
            return OperationalPriority.CRITICAL

        if (
            health.operational_state == OperationalState.CRITICAL
            and risk in (AnomalySeverity.HIGH, AnomalySeverity.CRITICAL)
        ):
            return OperationalPriority.CRITICAL

        # Rule 4: High Priority Condition
        if (
            (health.health_score < cfg.degrading_health_threshold or risk == AnomalySeverity.HIGH)
            and diag_conf >= cfg.min_confidence_for_high
        ):
            return OperationalPriority.HIGH

        if (
            diagnostic.status == DiagnosticStatus.LIKELY_DEGRADATION
            and risk in (AnomalySeverity.MEDIUM, AnomalySeverity.HIGH)
        ):
            return OperationalPriority.HIGH

        # Rule 5: Medium Priority Condition
        if (
            risk == AnomalySeverity.MEDIUM
            or (diagnostic.primary_hypothesis and diagnostic.primary_hypothesis.category == HypothesisCategory.LOCALIZED_SENSOR_ANOMALY)
        ):
            return OperationalPriority.MEDIUM

        # Rule 6: Low Priority Condition (Early drift, transient spike, minor deviation)
        if (
            anomaly.status in (AnomalyStatus.ANOMALY_DETECTED, AnomalyStatus.DEGRADATION_DETECTED)
            or risk == AnomalySeverity.LOW
            or diagnostic.status == DiagnosticStatus.INVESTIGATING
        ):
            return OperationalPriority.LOW

        return OperationalPriority.NONE

    def _generate_recommended_action(
        self,
        priority: OperationalPriority,
        diagnostic: DiagnosticResult,
        anomaly: AnomalyDetectionResult,
        health: HealthAssessment,
    ) -> str:
        """Generate deterministic, advisory next steps (no automated control commands)."""
        hyp = diagnostic.primary_hypothesis
        category = hyp.category if hyp else HypothesisCategory.UNKNOWN

        if priority == OperationalPriority.CRITICAL:
            lead_info = f" (Estimated lead time to intervention: ~{anomaly.lead_cycles_estimate} cycles)" if anomaly.lead_cycles_estimate else ""
            if category == HypothesisCategory.THERMAL_DEGRADATION:
                return f"Schedule immediate maintenance inspection for thermal subsystem; verify cooling circuits and heat exchanger pathways.{lead_info}"
            elif category == HypothesisCategory.MECHANICAL_DEGRADATION:
                return f"Schedule immediate mechanical inspection; inspect bearings, rotor assembly, and alignment for dynamic fatigue.{lead_info}"
            elif category == HypothesisCategory.PRESSURE_FLOW_DEGRADATION:
                return f"Schedule urgent fluid dynamics inspection; check for severe line restrictions or seal compromise.{lead_info}"
            elif category == HypothesisCategory.SYSTEMIC_MULTI_SUBSYSTEM:
                return f"Schedule comprehensive asset overhaul; multi-subsystem degradation detected across physical domains.{lead_info}"
            return f"Schedule immediate operational inspection of the affected asset.{lead_info}"

        elif priority == OperationalPriority.HIGH:
            lead_info = f" (Lead estimate: ~{anomaly.lead_cycles_estimate} cycles)" if anomaly.lead_cycles_estimate else ""
            if category == HypothesisCategory.THERMAL_DEGRADATION:
                return f"Inspect thermal subsystem during next scheduled maintenance window; monitor temperature trends.{lead_info}"
            elif category == HypothesisCategory.MECHANICAL_DEGRADATION:
                return f"Plan mechanical inspection and vibration analysis on next scheduled maintenance stop.{lead_info}"
            elif category == HypothesisCategory.PRESSURE_FLOW_DEGRADATION:
                return f"Inspect pressure and flow regulation components; check filter status.{lead_info}"
            return f"Plan targeted inspection of degraded subsystem during next available maintenance window.{lead_info}"

        elif priority == OperationalPriority.MEDIUM:
            if diagnostic.status == DiagnosticStatus.MULTIPLE_POSSIBLE_CAUSES:
                return "Review telemetry and initiate targeted diagnostic checks to isolate competing candidate causes across affected subsystems."
            elif category == HypothesisCategory.LOCALIZED_SENSOR_ANOMALY:
                return "Review sensor health, wiring, and calibration for the isolated deviating sensor."
            return "Increase telemetry monitoring frequency and review subsystem operational trends."

        elif priority == OperationalPriority.LOW:
            if category == HypothesisCategory.TRANSIENT_DISTURBANCE:
                return "Continue observation; transient disturbance noted with no persistent degradation pattern."
            return "Continue standard observation; early drift detected, escalation is not yet required."

        return "No operational intervention required. Continue standard telemetry logging."

    def _build_traceability_chain(
        self,
        health: HealthAssessment,
        anomaly: AnomalyDetectionResult,
        diagnostic: DiagnosticResult,
        priority: OperationalPriority,
    ) -> dict[str, Any]:
        """Construct full backward explainability trace."""
        primary_hyp_dict = None
        if diagnostic.primary_hypothesis:
            primary_hyp_dict = {
                "category": diagnostic.primary_hypothesis.category.value,
                "description": diagnostic.primary_hypothesis.description,
                "confidence": diagnostic.primary_hypothesis.confidence,
                "supporting_evidence": list(diagnostic.primary_hypothesis.supporting_evidence),
                "contradicting_evidence": list(diagnostic.primary_hypothesis.contradicting_evidence),
            }

        deviating_signals_trace = [
            {
                "sensor_id": e.sensor_id,
                "measurement_type": e.measurement_type,
                "deviation_sigma": e.deviation_sigma,
                "trend": e.trend.value,
                "persistence_count": e.persistence_count,
                "data_quality": e.data_quality,
            }
            for e in diagnostic.evidence
            if e.deviation_sigma >= 1.5
        ]

        return {
            "finding_priority": priority.value,
            "risk_interpretation": diagnostic.overall_risk.value,
            "diagnostic_status": diagnostic.status.value,
            "diagnostic_confidence": diagnostic.confidence,
            "primary_hypothesis": primary_hyp_dict,
            "anomaly_detection": {
                "status": anomaly.status.value,
                "score": anomaly.anomaly_score,
                "severity": anomaly.severity.value,
                "detection_method": anomaly.detection_method,
                "lead_cycles_estimate": anomaly.lead_cycles_estimate,
            },
            "health_assessment": {
                "operational_state": health.operational_state.value,
                "health_score": health.health_score,
                "confidence": health.confidence,
                "trend": health.trend.value,
            },
            "signal_evidence_residuals": deviating_signals_trace,
        }

    def _build_summary(
        self,
        priority: OperationalPriority,
        diagnostic: DiagnosticResult,
        health: HealthAssessment,
        anomaly: AnomalyDetectionResult,
    ) -> str:
        """Create a clear, operator-readable summary sentence."""
        hyp_desc = diagnostic.primary_hypothesis.description if diagnostic.primary_hypothesis else "No abnormal hypotheses"
        return (
            f"[{priority.value} PRIORITY] Asset {health.asset_id} ({health.device_id}): "
            f"Health {health.health_score:.1f}/100, State {health.operational_state.value}. "
            f"{hyp_desc} (Risk: {diagnostic.overall_risk.value})"
        )

    def _nominal_finding(
        self,
        health: HealthAssessment,
        anomaly: AnomalyDetectionResult,
        diagnostic: DiagnosticResult,
    ) -> OperationalFinding:
        """Produce clean NOMINAL finding."""
        trace = self._build_traceability_chain(health, anomaly, diagnostic, OperationalPriority.NONE)
        return OperationalFinding(
            asset_id=health.asset_id,
            device_id=health.device_id,
            priority=OperationalPriority.NONE,
            risk_level=AnomalySeverity.NONE,
            summary=f"[NOMINAL] Asset {health.asset_id} ({health.device_id}) is operating stably within normal parameters (Health: {health.health_score:.1f}/100).",
            operational_state=health.operational_state,
            health_score=health.health_score,
            anomaly_status=anomaly.status,
            anomaly_score=anomaly.anomaly_score,
            diagnostic_status=diagnostic.status,
            diagnostic_confidence=diagnostic.confidence,
            primary_hypothesis=diagnostic.primary_hypothesis,
            supporting_evidence=("All monitored sensor signals within nominal baseline bounds.",),
            recommended_next_action="No operational intervention required. Continue standard telemetry logging.",
            lead_cycles_estimate=None,
            confidence=0.95,
            traceability_chain=trace,
            evaluated_at=datetime.now(UTC),
            limitations="Nominal assessment applies only to monitored signals within the evaluated time window.",
            metadata={"nominal": True},
        )

    def _insufficient_data_finding(
        self,
        health: HealthAssessment,
        anomaly: AnomalyDetectionResult,
        diagnostic: DiagnosticResult,
    ) -> OperationalFinding:
        """Produce safe INSUFFICIENT_DATA finding."""
        trace = self._build_traceability_chain(health, anomaly, diagnostic, OperationalPriority.LOW)
        return OperationalFinding(
            asset_id=health.asset_id,
            device_id=health.device_id,
            priority=OperationalPriority.LOW,
            risk_level=AnomalySeverity.NONE,
            summary=f"[LOW PRIORITY] Asset {health.asset_id} ({health.device_id}): Telemetry data insufficient to determine health or risk.",
            operational_state=health.operational_state,
            health_score=health.health_score,
            anomaly_status=anomaly.status,
            anomaly_score=anomaly.anomaly_score,
            diagnostic_status=diagnostic.status,
            diagnostic_confidence=diagnostic.confidence,
            primary_hypothesis=None,
            supporting_evidence=(),
            recommended_next_action="Verify edge sensor connectivity, telemetry pipeline latency, and data quality flags.",
            lead_cycles_estimate=None,
            confidence=0.0,
            traceability_chain=trace,
            evaluated_at=datetime.now(UTC),
            limitations="Sparse or corrupted telemetry prevents reliable risk prioritization.",
            metadata={"reason": "Insufficient telemetry or low upstream confidence"},
        )
