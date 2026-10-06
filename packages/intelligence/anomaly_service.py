"""
Aegis Intelligence — Anomaly & Degradation Detection Service (P2.S2).
Detects multi-sensor statistical anomalies and progressive degradation
with persistence tracking, severity scoring, and inspectable evidence.

Architecture:
    TelemetryRepository (port)
          ↓
    AnomalyDetectionService
          ↓
    AnomalyDetectionResult (frozen value object)

Pure domain service. No SQL. Fully deterministic.
"""
from __future__ import annotations

import logging
import math
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from domain.entities import Observation, QualityFlag
from domain.intelligence import (
    AnomalyDetectionResult,
    AnomalySeverity,
    AnomalyStatus,
    SignalEvidence,
    TrendDirection,
)
from domain.repository import TelemetryRepository

from .statistics import (
    compute_deviation_score,
    compute_mean,
    compute_std,
    compute_trend,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AnomalyDetectorConfig:
    """Tunable parameters for anomaly and degradation detection."""
    baseline_window: int = 50          # Number of early observations to define nominal baseline
    eval_window: int = 20              # Number of recent observations for evaluation
    min_baseline_samples: int = 10     # Minimum GOOD observations needed for valid baseline
    deviation_threshold_sigma: float = 2.0  # Sigma threshold for confirmed deviation
    early_drift_threshold_sigma: float = 1.2  # Sigma threshold for trending early drift
    severe_threshold_sigma: float = 3.5     # Sigma threshold for severe deviation
    persistence_threshold: int = 5     # Minimum consecutive cycles deviating to confirm persistent degradation
    trend_slope_threshold: float = 0.001
    observation_limit: int = 5000


class AnomalyDetectionService:
    """
    Application service that performs explainable anomaly & degradation detection.

    Usage:
        service = AnomalyDetectionService(repository)
        result = service.detect(device_id="engine-001", asset_id="turbofan-fleet")
    """

    def __init__(
        self,
        repository: TelemetryRepository,
        config: AnomalyDetectorConfig | None = None,
    ) -> None:
        self._repo = repository
        self._config = config or AnomalyDetectorConfig()

    def detect(
        self,
        device_id: str,
        asset_id: str = "unknown",
    ) -> AnomalyDetectionResult:
        """
        Evaluate device telemetry for abnormal behavior or degradation.
        """
        cfg = self._config

        observations = self._repo.get_observations(
            device_id=device_id,
            limit=cfg.observation_limit,
        )

        if not observations:
            return self._empty_result(device_id, asset_id, "No telemetry observations available.")

        # Group by sensor_id
        by_sensor: dict[str, list[Observation]] = defaultdict(list)
        for obs in observations:
            by_sensor[obs.sensor_id].append(obs)

        # Analyze each sensor individually
        evidence_list: list[SignalEvidence] = []
        valid_sensor_count = 0
        insufficient_sensor_count = 0
        total_good_obs = 0
        total_obs = len(observations)

        for sensor_id, obs_list in sorted(by_sensor.items()):
            obs_list.sort(key=lambda o: o.timestamp)
            evidence = self._analyze_sensor(sensor_id, obs_list)
            if evidence is not None:
                valid_sensor_count += 1
                evidence_list.append(evidence)
            else:
                insufficient_sensor_count += 1

            total_good_obs += sum(1 for o in obs_list if o.quality == QualityFlag.GOOD)

        # Insufficient data condition
        if valid_sensor_count == 0:
            return self._empty_result(
                device_id,
                asset_id,
                f"All {len(by_sensor)} sensors have insufficient baseline observations.",
            )

        # Calculate overall confidence
        data_quality = total_good_obs / max(total_obs, 1)
        confidence = 1.0
        confidence -= 0.1 * insufficient_sensor_count
        if data_quality < 0.7:
            confidence -= 0.2
        if valid_sensor_count < 3:
            confidence -= 0.15
        confidence = max(0.0, min(1.0, confidence))

        if confidence < 0.4:
            return AnomalyDetectionResult(
                asset_id=asset_id,
                device_id=device_id,
                status=AnomalyStatus.UNKNOWN,
                anomaly_score=0.0,
                confidence=round(confidence, 4),
                severity=AnomalySeverity.NONE,
                evidence_list=tuple(evidence_list),
                evaluated_at=datetime.now(UTC),
                detection_method="Multivariate-Statistical-Residuals-v1",
                metadata={"reason": "Confidence below operational threshold (<0.40)"},
            )

        # Classify and score anomalies
        return self._classify_and_aggregate(
            device_id=device_id,
            asset_id=asset_id,
            evidence_list=evidence_list,
            confidence=confidence,
            total_sensors=valid_sensor_count,
            data_quality=data_quality,
        )

    def _analyze_sensor(
        self,
        sensor_id: str,
        observations: list[Observation],
    ) -> SignalEvidence | None:
        """Analyze time-series for a single sensor. Returns SignalEvidence."""
        cfg = self._config

        good_obs = [o for o in observations if o.quality == QualityFlag.GOOD]
        if len(good_obs) < cfg.min_baseline_samples:
            return None

        # Determine measurement name
        measurement_type = "unknown"
        if observations and observations[0].metadata.get("sensor_name"):
            measurement_type = observations[0].metadata["sensor_name"]
        elif "-" in sensor_id:
            measurement_type = sensor_id.split("-")[1] if len(sensor_id.split("-")) > 1 else "unknown"

        # Baseline: first N good observations
        baseline_obs = good_obs[: cfg.baseline_window]
        baseline_vals = [o.value for o in baseline_obs]
        b_mean = compute_mean(baseline_vals)
        b_std = compute_std(baseline_vals, b_mean)

        if b_std > 1e-4:
            effective_std = b_std
        else:
            effective_std = max(0.01 * abs(b_mean), 0.1)

        # Current window: recent valid observations (GOOD + UNCERTAIN)
        current_obs = observations[-cfg.eval_window :]
        current_valid = [o for o in current_obs if o.quality in (QualityFlag.GOOD, QualityFlag.UNCERTAIN)]
        current_vals = [o.value for o in current_valid]

        if not current_vals:
            c_mean = b_mean
        else:
            c_mean = compute_mean(current_vals)

        dev_sigma = compute_deviation_score(c_mean, b_mean, effective_std)
        trend = compute_trend(current_vals, cfg.trend_slope_threshold)

        # Persistence: count consecutive recent observations deviating > 1.5 sigma from baseline
        persistence_count = 0
        for obs in reversed(current_valid):
            obs_dev = abs(obs.value - b_mean) / effective_std
            if obs_dev >= 1.5:
                persistence_count += 1
            else:
                break

        # Base contribution score (sigmoid curve)
        base_contrib = 1.0 / (1.0 + math.exp(-1.2 * (dev_sigma - 2.5)))
        
        # Boost for early active monotonic trends (emerging drift)
        if trend in (TrendDirection.INCREASING, TrendDirection.DECREASING) and dev_sigma >= cfg.early_drift_threshold_sigma:
            trend_contrib = 0.30 + 0.20 * min(1.0, (dev_sigma - cfg.early_drift_threshold_sigma))
            contribution_score = max(base_contrib, trend_contrib)
        else:
            contribution_score = base_contrib

        # Explainable reasoning string
        if dev_sigma >= cfg.severe_threshold_sigma:
            reason = f"Severe deviation of {dev_sigma:.2f}σ from baseline (persisted {persistence_count} cycles)"
        elif dev_sigma >= cfg.deviation_threshold_sigma:
            reason = f"Confirmed deviation of {dev_sigma:.2f}σ from baseline (trend: {trend.value})"
        elif dev_sigma >= cfg.early_drift_threshold_sigma and trend in (TrendDirection.INCREASING, TrendDirection.DECREASING):
            reason = f"Early trending drift of {dev_sigma:.2f}σ with active {trend.value} trend"
        else:
            reason = f"Nominal behavior ({dev_sigma:.2f}σ deviation)"

        return SignalEvidence(
            sensor_id=sensor_id,
            measurement_type=measurement_type,
            deviation_sigma=round(dev_sigma, 2),
            trend=trend,
            persistence_count=persistence_count,
            contribution_score=round(contribution_score, 4),
            reason=reason,
        )

    def _classify_and_aggregate(
        self,
        device_id: str,
        asset_id: str,
        evidence_list: list[SignalEvidence],
        confidence: float,
        total_sensors: int,
        data_quality: float,
    ) -> AnomalyDetectionResult:
        """Aggregate evidence into overall detection status, score, and severity."""
        cfg = self._config

        # Identify deviating, trending early drift, and severe signals
        confirmed_deviating = [e for e in evidence_list if e.deviation_sigma >= cfg.deviation_threshold_sigma]
        early_drifting = [
            e for e in evidence_list
            if e.trend in (TrendDirection.INCREASING, TrendDirection.DECREASING)
            and e.deviation_sigma >= cfg.early_drift_threshold_sigma
        ]
        all_abnormal = list({e.sensor_id: e for e in (confirmed_deviating + early_drifting)}.values())
        
        severe = [e for e in evidence_list if e.deviation_sigma >= cfg.severe_threshold_sigma]
        persistent_degrading = [
            e for e in confirmed_deviating
            if e.persistence_count >= cfg.persistence_threshold
            or e.trend in (TrendDirection.INCREASING, TrendDirection.DECREASING)
        ]

        # Calculate multi-signal anomaly score emphasizing the most distressed components
        if evidence_list:
            top_contributions = sorted([e.contribution_score for e in evidence_list], reverse=True)
            top_1 = top_contributions[0]
            top_3_mean = sum(top_contributions[:3]) / min(3, len(top_contributions))
            all_mean = sum(top_contributions) / len(top_contributions)
            # 60% worst component + 30% top-3 mean + 10% fleet mean
            anomaly_score = (0.60 * top_1) + (0.30 * top_3_mean) + (0.10 * all_mean)
        else:
            anomaly_score = 0.0

        anomaly_score = max(0.0, min(1.0, anomaly_score))

        # Determine Anomaly Status
        if len(all_abnormal) == 0:
            status = AnomalyStatus.NOMINAL
            severity = AnomalySeverity.NONE
        elif len(persistent_degrading) >= 2 or len(severe) >= 2:
            status = AnomalyStatus.DEGRADATION_DETECTED
        elif len(all_abnormal) >= 1:
            status = AnomalyStatus.ANOMALY_DETECTED
        else:
            status = AnomalyStatus.NOMINAL

        # Determine Severity
        if status == AnomalyStatus.NOMINAL:
            severity = AnomalySeverity.NONE
        elif anomaly_score >= 0.85 or len(severe) >= 3:
            severity = AnomalySeverity.CRITICAL
        elif anomaly_score >= 0.65 or len(confirmed_deviating) >= 4:
            severity = AnomalySeverity.HIGH
        elif anomaly_score >= 0.40 or len(confirmed_deviating) >= 2:
            severity = AnomalySeverity.MEDIUM
        else:
            severity = AnomalySeverity.LOW

        # Rough Lead Cycles Estimate
        lead_cycles = None
        if status == AnomalyStatus.DEGRADATION_DETECTED and persistent_degrading:
            mean_pers = sum(e.persistence_count for e in persistent_degrading) / len(persistent_degrading)
            lead_cycles = max(5, int(50 - mean_pers))

        return AnomalyDetectionResult(
            asset_id=asset_id,
            device_id=device_id,
            status=status,
            anomaly_score=round(anomaly_score, 4),
            confidence=round(confidence, 4),
            severity=severity,
            evidence_list=tuple(evidence_list),
            evaluated_at=datetime.now(UTC),
            detection_method="Multivariate-Statistical-Residuals-v1",
            lead_cycles_estimate=lead_cycles,
            metadata={
                "total_sensors": total_sensors,
                "confirmed_deviating_count": len(confirmed_deviating),
                "early_drifting_count": len(early_drifting),
                "severe_sensor_count": len(severe),
                "persistent_degrading_count": len(persistent_degrading),
                "avg_data_quality": round(data_quality, 4),
            },
        )

    def _empty_result(
        self,
        device_id: str,
        asset_id: str,
        reason: str,
    ) -> AnomalyDetectionResult:
        """Safe default result when telemetry is missing or insufficient."""
        return AnomalyDetectionResult(
            asset_id=asset_id,
            device_id=device_id,
            status=AnomalyStatus.UNKNOWN,
            anomaly_score=0.0,
            confidence=0.0,
            severity=AnomalySeverity.NONE,
            evidence_list=(),
            evaluated_at=datetime.now(UTC),
            detection_method="Multivariate-Statistical-Residuals-v1",
            metadata={"reason": reason},
        )

