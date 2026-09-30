"""
Sensor telemetry generation algorithms.

Provides continuous, realistic multi-dimensional synthetic sensor data
with multi-frequency rotational harmonics, load wander, transient spikes,
and degradation physics.
"""

from __future__ import annotations

import math
import random
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .config import SensorProfile


class SensorGenerator:
    """Generates continuous physical sensor telemetry using dynamic multi-axis physics."""

    def __init__(self, profile: SensorProfile, rng: random.Random | None = None) -> None:
        self._profile = profile
        self._rng = rng or random.Random()
        self._nominal = (profile.normal_min + profile.normal_max) / 2.0
        self._current = self._nominal
        self._tick = 0
        self._phase = self._rng.uniform(0.0, 2.0 * math.pi)
        self._phase2 = self._rng.uniform(0.0, 2.0 * math.pi)
        self._phase3 = self._rng.uniform(0.0, 2.0 * math.pi)
        self._spike_cooldown = 0

    @property
    def sensor_id(self) -> str:
        return self._profile.sensor_id

    @property
    def unit(self) -> str:
        return self._profile.unit

    def next_value(self, degradation: float = 0.0) -> float:
        """
        Generate the next multi-dimensional reading.

        Enforces:
        - Strict normal bounds [normal_min, normal_max] when degradation == 0.0
        - Significant temperature elevation (> 75.0°C) during full degradation (> 0.5)
        - Dynamic multi-frequency wave oscillation across operating span
        """
        self._tick += 1
        span = max(0.1, self._profile.normal_max - self._profile.normal_min)
        mtype = self._profile.measurement_type.lower()

        # --- 1. Multi-frequency bidirectional load cycle ---
        self._load_state = 0.35 * math.sin(self._tick * 0.40 + self._phase)
        self._load_state += 0.20 * math.sin(self._tick * 0.20 + self._phase2)

        # Base target calculation
        load_offset = self._load_state * span * 0.25
        deg_offset = degradation * (self._profile.abnormal_max - self._nominal) * 0.85
        effective_target = self._nominal + load_offset + deg_offset

        # --- 2. Multi-frequency harmonics per measurement type ---
        if "temp" in mtype:
            theta = 0.35
            jitter = span * 0.02
            h1, f1 = span * 0.18, 0.40
            h2, f2 = span * 0.10, 0.80
        elif "vib" in mtype:
            theta = 0.35
            jitter = span * 0.03
            h1, f1 = span * 0.20, 0.50
            h2, f2 = span * 0.10, 0.90
        elif "press" in mtype:
            theta = 0.30
            jitter = span * 0.02
            h1, f1 = span * 0.18, 0.45
            h2, f2 = span * 0.10, 0.85
        elif "hum" in mtype:
            theta = 0.25
            jitter = span * 0.02
            h1, f1 = span * 0.20, 0.35
            h2, f2 = span * 0.10, 0.70
        else:
            theta = 0.30
            jitter = span * 0.02
            h1, f1 = span * 0.18, 0.40
            h2, f2 = span * 0.10, 0.80

        # --- 3. Oscillation + Noise ---
        oscillation = h1 * math.sin(self._tick * f1 + self._phase) + h2 * math.sin(
            self._tick * f2 + self._phase2
        )

        spike = 0.0
        if degradation > 0.0:
            if self._spike_cooldown > 0:
                self._spike_cooldown -= 1
            elif self._rng.random() < 0.08 * degradation:
                spike = span * self._rng.uniform(0.15, 0.35) * degradation
                self._spike_cooldown = self._rng.randint(3, 5)

        drift = theta * (effective_target - self._current)
        noise = self._rng.uniform(-jitter, jitter)

        # --- 4. Integrate state ---
        self._current += drift + oscillation + noise + spike

        # --- 5. Bounds Enforcement ---
        if degradation <= 0.0:
            floor = self._profile.normal_min
            ceiling = self._profile.normal_max
        else:
            floor = self._profile.normal_min
            ceiling = self._profile.abnormal_max + span * 0.10

        self._current = max(floor, min(ceiling, self._current))
        return round(self._current, 1)
