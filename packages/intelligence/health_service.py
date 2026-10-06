"""
Aegis Intelligence — Health Assessment Service (P2.S1).
Computes operational state and health from historical telemetry.

Architecture:
    TelemetryRepository (port)
          ↓
    HealthAssessmentService
          ↓
    HealthAssessment (frozen value object)

No SQL. No direct database access. No side effects beyond computation.
"""
from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from domain.entities import Observation, QualityFlag
from domain.intelligence import (
    HealthAssessment,
    OperationalState,
    SensorSignal,
    TrendDirection,
)
from domain.repository import TelemetryRepository

from .statistics import (
    compute_deviation_score,
    compute_mean,
    compute_sensor_health,
    compute_std,
    compute_trend,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class HealthConfig:
    """Tunable parameters for health assessment computation."""
    baseline_window: int = 50       # Number of early observations for baseline
    current_window: int = 20        # Number of recent observations for current state
    min_baseline_samples: int = 10  # Minimum GOOD observations for valid baseline
    deviation_weight: float = 15.0  # Score penalty per sigma of deviation
    trend_slope_threshold: float = 0.001  # Relative slope threshold for trend
    observation_limit: int = 5000   # Max observations to retrieve per device


class HealthAssessmentService:
    """
    Application service that computes asset health from telemetry history.

    Usage:
        service = HealthAssessmentService(repository)
        assessment = service.assess(device_id="engine-001", asset_id="fleet-01")
    """

    def __init__(
        self,
        repository: TelemetryRepository,
        config: HealthConfig | None = None,
    ) -> None:
        self._repo = repository
        self._config = config or HealthConfig()

    def assess(
        self,
        device_id: str,
        asset_id: str = "unknown",
    ) -> HealthAssessment:
        """
        Compute a full health assessment for a device.

        Steps:
            1. Retrieve all observations for the device
            2. Group by sensor_id
            3. Compute per-sensor baseline + current signals
            4. Aggregate to asset-level health, confidence, state, trend
        """
        cfg = self._config

        # Step 1: Retrieve observations through the repository port
        observations = self._repo.get_observations(
            device_id=device_id,
            limit=cfg.observation_limit,
        )

        if not observations:
            return self._empty_assessment(device_id, asset_id, "No observations available")

        # Step 2: Group by sensor
        by_sensor: dict[str, list[Observation]] = defaultdict(list)
        for obs in observations:
            by_sensor[obs.sensor_id].append(obs)

        # Step 3: Compute per-sensor signals
        signals: list[SensorSignal] = []
        for sensor_id, obs_list in sorted(by_sensor.items()):
            obs_list.sort(key=lambda o: o.timestamp)
            signal = self._compute_sensor_signal(sensor_id, obs_list)
            signals.append(signal)

        # Step 4: Aggregate
        return self._aggregate(device_id, asset_id, signals)

    def _compute_sensor_signal(
        self,
        sensor_id: str,
        observations: list[Observation],
    ) -> SensorSignal:
        """Compute a single sensor's contribution to health."""
        cfg = self._config

        # Separate GOOD observations for baseline computation
        good_obs = [o for o in observations if o.quality == QualityFlag.GOOD]

        # Determine measurement type from metadata or sensor_id
        measurement_type = "unknown"
        if observations and observations[0].metadata.get("sensor_name"):
            measurement_type = observations[0].metadata["sensor_name"]
        elif "-" in sensor_id:
            measurement_type = sensor_id.split("-")[1] if len(sensor_id.split("-")) > 1 else "unknown"

        # Check for insufficient baseline data
        if len(good_obs) < cfg.min_baseline_samples:
            return SensorSignal(
                sensor_id=sensor_id,
                measurement_type=measurement_type,
                baseline_mean=0.0,
                baseline_std=0.0,
                current_mean=0.0,
                deviation_score=0.0,
                trend=TrendDirection.UNKNOWN,
                data_quality=len(good_obs) / max(len(observations), 1),
                sample_count=len(observations),
                insufficient_data=True,
            )

        # Baseline: first N good observations
        baseline_obs = good_obs[: cfg.baseline_window]
        baseline_values = [o.value for o in baseline_obs]
        baseline_mean = compute_mean(baseline_values)
        baseline_std = compute_std(baseline_values, baseline_mean)

        # Effective standard deviation: avoid zero-division on flat sensors
                # Effective standard deviation: use empirical std if variance exists,
        # otherwise use a sensible physical noise floor (1% of mean or min 0.1)
        if baseline_std > 1e-4:
            effective_std = baseline_std
        else:
            effective_std = max(0.01 * abs(baseline_mean), 0.1)

        # Current window: evaluate recent valid observations (GOOD + UNCERTAIN)
        current_obs = observations[-cfg.current_window :]
        current_valid = [o for o in current_obs if o.quality in (QualityFlag.GOOD, QualityFlag.UNCERTAIN)]
        current_valid_values = [o.value for o in current_valid]

        if not current_valid_values:
            current_mean = baseline_mean
        else:
            current_mean = compute_mean(current_valid_values)

        # Deviation and trend
        deviation = compute_deviation_score(current_mean, baseline_mean, effective_std)
        trend = compute_trend(current_valid_values, cfg.trend_slope_threshold)

        current_good = [o for o in current_obs if o.quality == QualityFlag.GOOD]
        data_quality = len(current_good) / max(len(current_obs), 1)

        return SensorSignal(
            sensor_id=sensor_id,
            measurement_type=measurement_type,
            baseline_mean=round(baseline_mean, 4),
            baseline_std=round(baseline_std, 4),
            current_mean=round(current_mean, 4),
            deviation_score=round(deviation, 4),
            trend=trend,
            data_quality=round(data_quality, 4),
            sample_count=len(observations),
            insufficient_data=False,
        )

    def _aggregate(
        self,
        device_id: str,
        asset_id: str,
        signals: list[SensorSignal],
    ) -> HealthAssessment:
        """Aggregate per-sensor signals into an asset-level assessment."""
        cfg = self._config

        valid_signals = [s for s in signals if not s.insufficient_data]
        insufficient_count = len(signals) - len(valid_signals)

        if not valid_signals:
            return self._empty_assessment(
                device_id,
                asset_id,
                f"All {len(signals)} sensors have insufficient data",
                sensor_signals=signals,
            )

        # Per-sensor health scores
        sensor_healths = [
            compute_sensor_health(s.deviation_score, cfg.deviation_weight)
            for s in valid_signals
        ]
        mean_health = sum(sensor_healths) / len(sensor_healths)
        min_health = min(sensor_healths)

        # Composite health score: 70% fleet average + 30% worst subsystem
        health_score = (0.7 * mean_health) + (0.3 * min_health)

        # Count significant deviating sensors (> 1.5 sigma)
        deviating_sensors = [s for s in valid_signals if s.deviation_score > 1.5]
        severe_sensors = [s for s in valid_signals if s.deviation_score > 2.5]

        # Confidence computation
        confidence = 1.0
        confidence -= 0.1 * insufficient_count
        avg_quality = sum(s.data_quality for s in valid_signals) / len(valid_signals)
        if avg_quality < 0.7:
            confidence -= 0.2
        if len(valid_signals) < 3:
            confidence -= 0.15
        confidence = max(0.0, min(1.0, confidence))

        # Overall trend: majority vote among valid sensors
        trend_votes: dict[TrendDirection, int] = defaultdict(int)
        for s in valid_signals:
            if s.trend != TrendDirection.UNKNOWN:
                trend_votes[s.trend] += 1
        if trend_votes:
            overall_trend = max(trend_votes, key=trend_votes.get)  # type: ignore[arg-type]
        else:
            overall_trend = TrendDirection.UNKNOWN

        # Operational state derivation
        operational_state = self._derive_state(
            health_score=health_score,
            trend=overall_trend,
            confidence=confidence,
            deviating_count=len(deviating_sensors),
            severe_count=len(severe_sensors),
        )

        # Evidence summary
        if deviating_sensors:
            summary = (
                f"{len(deviating_sensors)} sensor(s) showing significant deviation: "
                f"{', '.join(s.sensor_id for s in deviating_sensors[:3])}"
                + ("..." if len(deviating_sensors) > 3 else "")
            )
        else:
            summary = f"All {len(valid_signals)} sensors within normal operating range"

        return HealthAssessment(
            asset_id=asset_id,
            device_id=device_id,
            operational_state=operational_state,
            health_score=round(health_score, 2),
            confidence=round(confidence, 4),
            trend=overall_trend,
            sensor_signals=tuple(signals),
            evaluated_at=datetime.now(UTC),
            evidence_summary=summary,
            metadata={
                "valid_sensors": len(valid_signals),
                "insufficient_sensors": insufficient_count,
                "avg_data_quality": round(avg_quality, 4),
                "deviating_sensors_count": len(deviating_sensors),
                "severe_sensors_count": len(severe_sensors),
            },
        )

    @staticmethod
    def _derive_state(
        health_score: float,
        trend: TrendDirection,
        confidence: float,
        deviating_count: int = 0,
        severe_count: int = 0,
    ) -> OperationalState:
        """Derive operational state from health, trend, confidence, and deviation counts."""
        if confidence < 0.4:
            return OperationalState.UNKNOWN
        if health_score < 50 or severe_count >= 3:
            return OperationalState.CRITICAL
        if (
            health_score < 75
            or deviating_count >= 2
            or trend in (TrendDirection.INCREASING, TrendDirection.DECREASING)
        ):
            return OperationalState.DEGRADING
        return OperationalState.NORMAL

    def _empty_assessment(
        self,
        device_id: str,
        asset_id: str,
        reason: str,
        sensor_signals: list[SensorSignal] | None = None,
    ) -> HealthAssessment:
        """Produce a safe default assessment when no data is available."""
        return HealthAssessment(
            asset_id=asset_id,
            device_id=device_id,
            operational_state=OperationalState.UNKNOWN,
            health_score=0.0,
            confidence=0.0,
            trend=TrendDirection.UNKNOWN,
            sensor_signals=tuple(sensor_signals) if sensor_signals else (),
            evaluated_at=datetime.now(UTC),
            evidence_summary=reason,
            metadata={"reason": reason},
        )


