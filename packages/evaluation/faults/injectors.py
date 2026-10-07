"""
P3.S2 — Controlled Fault Injectors

Test-only transformation utilities simulating imperfect telemetry.
These functions NEVER modify production intelligence code.
"""

import random
import uuid
from datetime import timedelta

from domain.entities import Observation, QualityFlag


def copy_observation(obs: Observation, **overrides) -> Observation:
    """Create a shallow copy of an Observation with selective field overrides."""
    return Observation(
        observation_id=overrides.get("observation_id", str(uuid.uuid4())),
        device_id=overrides.get("device_id", obs.device_id),
        sensor_id=overrides.get("sensor_id", obs.sensor_id),
        timestamp=overrides.get("timestamp", obs.timestamp),
        value=overrides.get("value", obs.value),
        unit=overrides.get("unit", obs.unit),
        quality=overrides.get("quality", obs.quality),
        metadata=overrides.get("metadata", dict(obs.metadata)),
    )


def inject_noise(
    observations: list[Observation],
    scale: float = 0.02,
    seed: int = 42,
) -> list[Observation]:
    """Add zero-mean Gaussian noise to observation values."""
    rng = random.Random(seed)
    noisy_obs: list[Observation] = []
    for obs in observations:
        noise = rng.gauss(0.0, max(abs(obs.value) * scale, 0.01))
        noisy_obs.append(copy_observation(obs, value=obs.value + noise))
    return noisy_obs


def inject_missing(
    observations: list[Observation],
    drop_ratio: float = 0.3,
    seed: int = 42,
) -> list[Observation]:
    """Randomly drop a percentage of observations to simulate packet loss."""
    rng = random.Random(seed)
    retained: list[Observation] = []
    for obs in observations:
        if rng.random() >= drop_ratio:
            retained.append(copy_observation(obs))
    return retained


def inject_quality_degradation(
    observations: list[Observation],
    quality_flag: QualityFlag = QualityFlag.BAD,
    ratio: float = 0.5,
    seed: int = 42,
) -> list[Observation]:
    """Set the quality flag to BAD or UNCERTAIN on a subset of observations."""
    rng = random.Random(seed)
    degraded: list[Observation] = []
    for obs in observations:
        if rng.random() < ratio:
            degraded.append(copy_observation(obs, quality=quality_flag))
        else:
            degraded.append(copy_observation(obs))
    return degraded


def inject_transient_spike(
    observations: list[Observation],
    target_sensor_name: str | None = None,
    cycle_index: int = 20,
    multiplier: float = 3.0,
) -> list[Observation]:
    """Inject a short single-cycle spike at cycle_index."""
    spiked: list[Observation] = []
    for obs in observations:
        obs_cycle = obs.metadata.get("cycle", 0)
        s_name = obs.metadata.get("sensor_name", "")

        is_target_sensor = (target_sensor_name is None) or (target_sensor_name in s_name)
        if obs_cycle == cycle_index and is_target_sensor:
            spiked.append(copy_observation(obs, value=obs.value * multiplier))
        else:
            spiked.append(copy_observation(obs))
    return spiked


def inject_recovery(
    nominal_baseline: list[Observation],
    degraded_observations: list[Observation],
    recovery_cycles: int = 30,
) -> list[Observation]:
    """Create a trajectory exhibiting Degradation followed by Recovery."""
    result: list[Observation] = [copy_observation(o) for o in degraded_observations]
    if not result or not nominal_baseline:
        return result

    last_cycle = max(o.metadata.get("cycle", 0) for o in result)
    last_timestamp = max(o.timestamp for o in result)

    nom_cycles = sorted(list({o.metadata.get("cycle", 0) for o in nominal_baseline}))
    sample_cycles = nom_cycles[:recovery_cycles]

    for offset, c in enumerate(sample_cycles, start=1):
        c_obs = [o for o in nominal_baseline if o.metadata.get("cycle", 0) == c]
        new_cycle = last_cycle + offset
        new_ts = last_timestamp + timedelta(hours=offset)
        for o in c_obs:
            new_meta = dict(o.metadata)
            new_meta["cycle"] = new_cycle
            result.append(
                copy_observation(
                    o,
                    timestamp=new_ts,
                    metadata=new_meta,
                    quality=QualityFlag.GOOD,
                )
            )

    return result
