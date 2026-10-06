"""
Aegis Intelligence — Diagnostic Service (P2.S3).
Synthesizes operational health and anomaly detections into structured evidence,
contextual operational state, deterministic root-cause hypotheses, and explicit
risk interpretations.

Architecture:
    HealthAssessment (P2.S1) ──┐
                               ├──> DiagnosticService ──> DiagnosticResult
    AnomalyDetectionResult (P2.S2) ┘

Pure domain service. No external ML / LLM. Fully deterministic.
"""
from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from domain.intelligence import (
    AnomalyDetectionResult,
    AnomalySeverity,
    AnomalyStatus,
    DiagnosticContext,
    DiagnosticEvidence,
    DiagnosticHypothesis,
    DiagnosticResult,
    DiagnosticStatus,
    HealthAssessment,
    HypothesisCategory,
    OperationalState,
    SensorSignal,
    SignalEvidence,
    TrendDirection,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DiagnosticConfig:
    """Tunable parameters for deterministic diagnostic rule evaluation."""
    min_confidence_threshold: float = 0.40
    single_sensor_isolated_sigma: float = 2.5
    subsystem_correlation_min_sensors: int = 2
    high_persistence_cycles: int = 5
    transient_max_persistence: int = 2


class DiagnosticService:
    """
    Application service that computes explainable diagnostic hypotheses and operational risk.
    Usage:
        service = DiagnosticService()
        result = service.diagnose(health_assessment, anomaly_result)
    """

    def __init__(self, config: DiagnosticConfig | None = None) -> None:
        self._config = config or DiagnosticConfig()

    def diagnose(
        self,
        health: HealthAssessment,
        anomaly: AnomalyDetectionResult,
    ) -> DiagnosticResult:
        """
        Perform deterministic diagnostic evaluation by binding health assessment
        and anomaly detection snapshots into explainable hypotheses.
        """
        # Step 1: Check for insufficient data / unknown upstream conditions
        if (
            health.operational_state == OperationalState.UNKNOWN
            or anomaly.status == AnomalyStatus.UNKNOWN
            or health.confidence < self._config.min_confidence_threshold
            or anomaly.confidence < self._config.min_confidence_threshold
        ):
            return self._insufficient_evidence_result(health, anomaly)

        # Step 2: Extract structured DiagnosticContext
        context = self._build_context(health, anomaly)

        # Step 3: Extract structured DiagnosticEvidence
        evidence_list = self._extract_evidence(health, anomaly)

        # Step 4: If upstream status is nominal, produce NOMINAL diagnostic result
        if (
            health.operational_state == OperationalState.NORMAL
            and anomaly.status == AnomalyStatus.NOMINAL
        ):
            return self._nominal_result(health, anomaly, context, evidence_list)

        # Step 5: Evaluate deterministic hypotheses
        hypotheses = self._evaluate_hypotheses(evidence_list, context)

        # Step 6: Determine overall diagnostic status, risk, and primary finding
        status, risk, primary_hyp, finding, diagnostic_conf = self._synthesize_diagnosis(
            hypotheses=hypotheses,
            context=context,
            evidence_list=evidence_list,
            health_conf=health.confidence,
            anomaly_conf=anomaly.confidence,
        )

        return DiagnosticResult(
            asset_id=health.asset_id,
            device_id=health.device_id,
            status=status,
            overall_risk=risk,
            context=context,
            evidence=tuple(evidence_list),
            hypotheses=tuple(hypotheses),
            primary_hypothesis=primary_hyp,
            confidence=round(diagnostic_conf, 4),
            primary_finding=finding,
            limitations="Deterministic statistical hypothesis based on telemetry residuals; physical root cause is not tear-down confirmed.",
            evaluated_at=datetime.now(UTC),
            diagnostic_method="Deterministic-Rule-Engine-v1",
            metadata={
                "health_score": health.health_score,
                "anomaly_score": anomaly.anomaly_score,
                "hypotheses_count": len(hypotheses),
            },
        )

    def _build_context(
        self,
        health: HealthAssessment,
        anomaly: AnomalyDetectionResult,
    ) -> DiagnosticContext:
        """Build operational circumstances context snapshot."""
        total_sensors = len(health.sensor_signals)
        deviating_count = sum(1 for e in anomaly.evidence_list if e.deviation_sigma >= 1.5)
        max_persistence = max((e.persistence_count for e in anomaly.evidence_list), default=0)

        return DiagnosticContext(
            operational_state=health.operational_state,
            health_score=health.health_score,
            health_confidence=health.confidence,
            anomaly_status=anomaly.status,
            anomaly_score=anomaly.anomaly_score,
            anomaly_severity=anomaly.severity,
            total_sensors=total_sensors,
            affected_sensors=deviating_count,
            dominant_trend=health.trend,
            max_persistence=max_persistence,
        )

    def _extract_evidence(
        self,
        health: HealthAssessment,
        anomaly: AnomalyDetectionResult,
    ) -> list[DiagnosticEvidence]:
        """Merge SensorSignal and SignalEvidence into structured DiagnosticEvidence objects."""
        health_by_sensor: dict[str, SensorSignal] = {s.sensor_id: s for s in health.sensor_signals}
        anomaly_by_sensor: dict[str, SignalEvidence] = {e.sensor_id: e for e in anomaly.evidence_list}

        evidence_list: list[DiagnosticEvidence] = []
        all_sensor_ids = sorted(set(health_by_sensor.keys()) | set(anomaly_by_sensor.keys()))

        for sid in all_sensor_ids:
            h_sig = health_by_sensor.get(sid)
            a_sig = anomaly_by_sensor.get(sid)

            measurement_type = h_sig.measurement_type if h_sig else (a_sig.measurement_type if a_sig else "unknown")
            dev_sigma = a_sig.deviation_sigma if a_sig else (h_sig.deviation_score if h_sig else 0.0)
            trend = a_sig.trend if a_sig else (h_sig.trend if h_sig else TrendDirection.UNKNOWN)
            persistence = a_sig.persistence_count if a_sig else 0
            quality = h_sig.data_quality if h_sig else 1.0
            contrib = a_sig.contribution_score if a_sig else 0.0
            reason = a_sig.reason if a_sig else (f"Nominal ({dev_sigma:.2f}σ)" if dev_sigma < 1.5 else f"Deviated ({dev_sigma:.2f}σ)")

            observation_desc = (
                f"{sid} ({measurement_type}): {dev_sigma:.2f}σ deviation, "
                f"trend {trend.value}, persistence {persistence} cycles"
            )

            evidence_list.append(
                DiagnosticEvidence(
                    sensor_id=sid,
                    measurement_type=measurement_type,
                    observation=observation_desc,
                    deviation_sigma=round(dev_sigma, 2),
                    trend=trend,
                    persistence_count=persistence,
                    data_quality=round(quality, 4),
                    contribution_score=round(contrib, 4),
                    reason=reason,
                )
            )
        return evidence_list

    def _evaluate_hypotheses(
        self,
        evidence_list: list[DiagnosticEvidence],
        context: DiagnosticContext,
    ) -> list[DiagnosticHypothesis]:
        """Evaluate deterministic diagnostic rules over structured evidence."""
        hypotheses: list[DiagnosticHypothesis] = []

        by_subsystem = self._group_by_subsystem(evidence_list)
        deviated_evidence = [e for e in evidence_list if e.deviation_sigma >= 1.5]
        severe_evidence = [e for e in evidence_list if e.deviation_sigma >= 3.0]

        # 1. Systemic / Multi-Subsystem Degradation Rule
        active_subsystems = sum(1 for sub, evs in by_subsystem.items() if sub != "general" and any(e.deviation_sigma >= 1.5 for e in evs))
        if active_subsystems >= 2 and len(deviated_evidence) >= 3:
            conf = 0.85 + min(0.12, 0.02 * len(deviated_evidence))
            sup = [f"{e.sensor_id} ({e.measurement_type}): {e.deviation_sigma}σ" for e in deviated_evidence[:6]]
            hypotheses.append(
                DiagnosticHypothesis(
                    category=HypothesisCategory.SYSTEMIC_MULTI_SUBSYSTEM,
                    description="Systemic multi-subsystem degradation across correlated physical domains.",
                    confidence=round(conf, 2),
                    supporting_evidence=tuple(sup),
                    contradicting_evidence=(),
                    severity=AnomalySeverity.CRITICAL if len(severe_evidence) >= 2 else AnomalySeverity.HIGH,
                )
            )

        # 2. Transient Disturbance Rule
        if (
            len(deviated_evidence) >= 1
            and context.max_persistence <= self._config.transient_max_persistence
            and context.dominant_trend == TrendDirection.STABLE
        ):
            sup = [f"{e.sensor_id} shows brief deviation of {e.deviation_sigma}σ (persistence <= {context.max_persistence} cycles)" for e in deviated_evidence]
            con = ["Dominant operational trend remains stable", "No persistent degradation observed"]
            hypotheses.append(
                DiagnosticHypothesis(
                    category=HypothesisCategory.TRANSIENT_DISTURBANCE,
                    description="Transient telemetry disturbance or temporary operational load fluctuation.",
                    confidence=0.55,
                    supporting_evidence=tuple(sup),
                    contradicting_evidence=tuple(con),
                    severity=AnomalySeverity.LOW,
                )
            )

        # 3. Localized / Isolated Sensor Anomaly Rule
        if len(deviated_evidence) == 1 and len(evidence_list) >= 2:
            target = deviated_evidence[0]
            nominal_companions = [e for e in evidence_list if e.sensor_id != target.sensor_id and e.deviation_sigma < 1.0]
            if len(nominal_companions) >= 1:
                sup = [f"Isolated deviation on {target.sensor_id} ({target.deviation_sigma}σ)", target.reason]
                con = [f"Companion sensor {c.sensor_id} is nominal ({c.deviation_sigma}σ)" for c in nominal_companions[:3]]
                hyp = DiagnosticHypothesis(
                    category=HypothesisCategory.LOCALIZED_SENSOR_ANOMALY,
                    description=f"Isolated sensor anomaly or localized fault on {target.sensor_id}.",
                    confidence=0.70,
                    supporting_evidence=tuple(sup),
                    contradicting_evidence=tuple(con),
                    severity=AnomalySeverity.LOW if target.deviation_sigma < 3.0 else AnomalySeverity.MEDIUM,
                )
                hypotheses.append(hyp)

        # 4. Subsystem-Level Rules (Thermal, Mechanical, Pressure/Flow)
        # Thermal Subsystem
        thermal_devs = [e for e in by_subsystem.get("thermal", []) if e.deviation_sigma >= 1.5]
        if len(thermal_devs) >= self._config.subsystem_correlation_min_sensors or (
            len(thermal_devs) >= 1 and any(e.trend == TrendDirection.INCREASING for e in thermal_devs) and context.max_persistence >= 4
        ):
            conf = 0.65 + min(0.20, 0.05 * len(thermal_devs))
            sup = [f"{e.sensor_id} elevated ({e.deviation_sigma}σ, trend: {e.trend.value})" for e in thermal_devs]
            con = []
            nominal_mech = [e for e in by_subsystem.get("mechanical", []) if e.deviation_sigma < 1.0]
            if nominal_mech:
                con.extend([f"Mechanical sensor {m.sensor_id} remains nominal ({m.deviation_sigma}σ)" for m in nominal_mech[:2]])
            hypotheses.append(
                DiagnosticHypothesis(
                    category=HypothesisCategory.THERMAL_DEGRADATION,
                    description="Thermal subsystem degradation with progressive heat accumulation.",
                    confidence=round(conf, 2),
                    supporting_evidence=tuple(sup),
                    contradicting_evidence=tuple(con),
                    severity=AnomalySeverity.HIGH if any(e.deviation_sigma >= 3.0 for e in thermal_devs) else AnomalySeverity.MEDIUM,
                )
            )

        # Mechanical Subsystem (Vibration, Speed, RPM)
        mech_devs = [e for e in by_subsystem.get("mechanical", []) if e.deviation_sigma >= 1.5]
        if len(mech_devs) >= self._config.subsystem_correlation_min_sensors or (
            len(mech_devs) >= 1 and any(e.trend != TrendDirection.STABLE for e in mech_devs) and context.max_persistence >= 4
        ):
            conf = 0.65 + min(0.20, 0.05 * len(mech_devs))
            sup = [f"{e.sensor_id} elevated ({e.deviation_sigma}σ, trend: {e.trend.value})" for e in mech_devs]
            con = []
            hypotheses.append(
                DiagnosticHypothesis(
                    category=HypothesisCategory.MECHANICAL_DEGRADATION,
                    description="Mechanical subsystem degradation (bearing wear, dynamic imbalance, or friction).",
                    confidence=round(conf, 2),
                    supporting_evidence=tuple(sup),
                    contradicting_evidence=tuple(con),
                    severity=AnomalySeverity.HIGH if any(e.deviation_sigma >= 3.0 for e in mech_devs) else AnomalySeverity.MEDIUM,
                )
            )

        # Pressure/Flow Subsystem
        press_devs = [e for e in by_subsystem.get("pressure_flow", []) if e.deviation_sigma >= 1.5]
        if len(press_devs) >= self._config.subsystem_correlation_min_sensors or (
            len(press_devs) >= 1 and context.max_persistence >= 4
        ):
            conf = 0.65 + min(0.20, 0.05 * len(press_devs))
            sup = [f"{e.sensor_id} deviated ({e.deviation_sigma}σ, trend: {e.trend.value})" for e in press_devs]
            con = []
            hypotheses.append(
                DiagnosticHypothesis(
                    category=HypothesisCategory.PRESSURE_FLOW_DEGRADATION,
                    description="Pressure or fluid flow subsystem disturbance (leakage, resistance, or restriction).",
                    confidence=round(conf, 2),
                    supporting_evidence=tuple(sup),
                    contradicting_evidence=tuple(con),
                    severity=AnomalySeverity.HIGH if any(e.deviation_sigma >= 3.0 for e in press_devs) else AnomalySeverity.MEDIUM,
                )
            )

        # Fallback if anomalies exist but no specialized hypothesis matched
        if not hypotheses and deviated_evidence:
            sup = [f"{e.sensor_id}: {e.deviation_sigma}σ ({e.reason})" for e in deviated_evidence]
            hypotheses.append(
                DiagnosticHypothesis(
                    category=HypothesisCategory.UNKNOWN,
                    description="Unclassified multi-sensor anomaly pattern.",
                    confidence=0.50,
                    supporting_evidence=tuple(sup),
                    contradicting_evidence=(),
                    severity=context.anomaly_severity,
                )
            )

        hypotheses.sort(key=lambda h: h.confidence, reverse=True)
        return hypotheses

    def _group_by_subsystem(
        self,
        evidence_list: list[DiagnosticEvidence],
    ) -> dict[str, list[DiagnosticEvidence]]:
        """Heuristically group sensors into physical subsystems based on name / measurement tokens."""
        groups: dict[str, list[DiagnosticEvidence]] = defaultdict(list)
        for e in evidence_list:
            text = f"{e.sensor_id} {e.measurement_type}".lower()
            if any(k in text for k in ("temp", "t1", "t2", "t3", "t4", "t5", "t24", "t30", "t50", "egt", "heat", "thermal")):
                groups["thermal"].append(e)
            elif any(k in text for k in ("vib", "rpm", "speed", "acc", "velocity", "current", "bearing", "n1", "n2", "mech")):
                groups["mechanical"].append(e)
            elif any(k in text for k in ("press", "flow", "p1", "p2", "p3", "p30", "p50", "psi", "bar", "hydraulic", "fuel")):
                groups["pressure_flow"].append(e)
            else:
                groups["general"].append(e)
        return groups

    def _synthesize_diagnosis(
        self,
        hypotheses: list[DiagnosticHypothesis],
        context: DiagnosticContext,
        evidence_list: list[DiagnosticEvidence],
        health_conf: float,
        anomaly_conf: float,
    ) -> tuple[DiagnosticStatus, AnomalySeverity, DiagnosticHypothesis | None, str, float]:
        """Aggregate hypotheses and context into overall diagnostic status, risk, and finding."""
        if not hypotheses:
            return (
                DiagnosticStatus.NOMINAL,
                AnomalySeverity.NONE,
                None,
                "All signals within normal statistical limits.",
                0.95,
            )

        primary_hyp = hypotheses[0]

        # Calculate evidentiary diagnostic confidence anchored on upstream certainty
        upstream_conf = max(0.40, min(health_conf, anomaly_conf))
        base_confidence = primary_hyp.confidence * upstream_conf
        if primary_hyp.contradicting_evidence:
            base_confidence *= 0.85

        diagnostic_conf = max(0.10, min(0.99, base_confidence))

        # Determine Diagnostic Status
        if primary_hyp.category == HypothesisCategory.SYSTEMIC_MULTI_SUBSYSTEM:
            status = DiagnosticStatus.LIKELY_DEGRADATION
        elif (
            len(hypotheses) > 1
            and abs(hypotheses[0].confidence - hypotheses[1].confidence) <= 0.05
            and primary_hyp.category != HypothesisCategory.NOMINAL
        ):
            status = DiagnosticStatus.MULTIPLE_POSSIBLE_CAUSES
        elif context.operational_state == OperationalState.CRITICAL or primary_hyp.severity in (AnomalySeverity.HIGH, AnomalySeverity.CRITICAL):
            status = DiagnosticStatus.LIKELY_DEGRADATION
        elif context.operational_state == OperationalState.DEGRADING or context.anomaly_status == AnomalyStatus.DEGRADATION_DETECTED:
            status = DiagnosticStatus.LIKELY_DEGRADATION
        else:
            status = DiagnosticStatus.INVESTIGATING

        # Overall Risk matches the primary hypothesis / context severity
        risk = max(
            [context.anomaly_severity, primary_hyp.severity],
            key=lambda s: ["NONE", "LOW", "MEDIUM", "HIGH", "CRITICAL"].index(s.value),
        )

        finding = f"Primary finding: {primary_hyp.description} (Risk: {risk.value}, Confidence: {diagnostic_conf*100:.0f}%)"

        return status, risk, primary_hyp, finding, diagnostic_conf

    def _nominal_result(
        self,
        health: HealthAssessment,
        anomaly: AnomalyDetectionResult,
        context: DiagnosticContext,
        evidence_list: list[DiagnosticEvidence],
    ) -> DiagnosticResult:
        """Produce clean NOMINAL result when all upstream signals are healthy."""
        nom_hyp = DiagnosticHypothesis(
            category=HypothesisCategory.NOMINAL,
            description="Asset operating within normal nominal parameters.",
            confidence=0.95,
            supporting_evidence=("All monitored sensors within nominal baseline bounds.",),
            contradicting_evidence=(),
            severity=AnomalySeverity.NONE,
        )
        return DiagnosticResult(
            asset_id=health.asset_id,
            device_id=health.device_id,
            status=DiagnosticStatus.NOMINAL,
            overall_risk=AnomalySeverity.NONE,
            context=context,
            evidence=tuple(evidence_list),
            hypotheses=(nom_hyp,),
            primary_hypothesis=nom_hyp,
            confidence=0.95,
            primary_finding="Asset operating within normal nominal parameters.",
            limitations="Nominal assessment applies only to monitored signals within the evaluated time window.",
            evaluated_at=datetime.now(UTC),
            diagnostic_method="Deterministic-Rule-Engine-v1",
            metadata={"nominal": True},
        )

    def _insufficient_evidence_result(
        self,
        health: HealthAssessment,
        anomaly: AnomalyDetectionResult,
    ) -> DiagnosticResult:
        """Produce safe INSUFFICIENT_EVIDENCE result when upstream confidence is low."""
        empty_context = DiagnosticContext(
            operational_state=health.operational_state,
            health_score=health.health_score,
            health_confidence=health.confidence,
            anomaly_status=anomaly.status,
            anomaly_score=anomaly.anomaly_score,
            anomaly_severity=anomaly.severity,
            total_sensors=len(health.sensor_signals),
            affected_sensors=0,
            dominant_trend=health.trend,
            max_persistence=0,
        )
        return DiagnosticResult(
            asset_id=health.asset_id,
            device_id=health.device_id,
            status=DiagnosticStatus.INSUFFICIENT_EVIDENCE,
            overall_risk=AnomalySeverity.NONE,
            context=empty_context,
            evidence=(),
            hypotheses=(),
            primary_hypothesis=None,
            confidence=0.0,
            primary_finding="Insufficient evidence to formulate a reliable diagnostic assessment.",
            limitations="Sparse or corrupted telemetry prevents statistical hypothesis formulation.",
            evaluated_at=datetime.now(UTC),
            diagnostic_method="Deterministic-Rule-Engine-v1",
            metadata={"reason": "Low upstream confidence or missing telemetry"},
        )
