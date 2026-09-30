"""
Multi-dimensional synthetic sensor-value generators.

Combines mean-reversion, multi-frequency harmonics, cyclic load profiles,
cross-sensor coupling, and bidirectional degradation dynamics so readings
move in multiple dimensions rather than a single upward ramp.
"""

from __future__ import annotations

import math
import random

from .config import SensorProfile


class SensorGenerator:
    """Produces multi-dimensional, temporally coherent sensor readings."""

    def __init__(
        self,
        profile: SensorProfile,
        rng: random.Random,
    ) -> None:
        self._profile = profile
        self._rng = rng
        self._nominal: float = (profile.normal_min + profile.normal_max) / 2.0
        self._current: float = self._nominal
        self._tick: int = 0
        self._phase: float = rng.uniform(0.0, 2.0 * math.pi)
        self._phase2: float = rng.uniform(0.0, 2.0 * math.pi)
        self._phase3: float = rng.uniform(0.0, 2.0 * math.pi)
        # Slow secondary state for load cycles
        self._load_state: float = 0.0
        self._spike_cooldown: int = 0

    @property
    def sensor_id(self) -> str:
        return self._profile.sensor_id

    @property
    def unit(self) -> str:
        return self._profile.unit

    def next_value(self, degradation: float = 0.0) -> float:
        """
        Generate the next multi-dimensional reading.

        Dynamics include:
        - Mean reversion toward a moving target
        - Multi-frequency rotational harmonics
        - Slow cyclic load wander (bidirectional)
        - Occasional transient spikes with recovery
        - Degradation-amplified turbulence (not just upward bias)
        """
        self._tick += 1
        span = max(0.1, self._profile.normal_max - self._profile.normal_min)
        mtype = self._profile.measurement_type.lower()

        # --- 1. Slow bidirectional load cycle (period ~40 ticks) ---
        self._load_state = 0.55 * math.sin(self._tick * 0.15 + self._phase)
        self._load_state += 0.30 * math.sin(self._tick * 0.07 + self._phase2)
        self._load_state += 0.15 * math.sin(self._tick * 0.03 + self._phase3)

        # --- 2. Base operating target (moves both up AND down) ---
        load_offset = self._load_state * span * 0.35
        deg_offset = degradation * (self._profile.abnormal_max - self._nominal) * 0.55
        # Degradation also injects bidirectional turbulence, not only upward push
        deg_wobble = degradation * span * 0.25 * math.sin(self._tick * 0.22 + self._phase2)
        effective_target = self._nominal + load_offset + deg_offset + deg_wobble

        # --- 3. Sensor-specific multi-frequency parameters ---
        if "temp" in mtype:
            theta = 0.12  # thermal inertia (slow)
            jitter = span * (0.025 + 0.04 * degradation)
            h1, f1 = span * 0.04, 0.18
            h2, f2 = span * 0.02, 0.41
            h3, f3 = span * 0.01, 0.09
        elif "vib" in mtype:
            theta = 0.40  # mechanical (fast)
            jitter = span * (0.06 + 0.18 * degradation)
            h1, f1 = span * (0.08 + 0.12 * degradation), 0.85
            h2, f2 = span * (0.05 + 0.08 * degradation), 1.70
            h3, f3 = span * 0.03, 0.33
        elif "press" in mtype:
            theta = 0.22  # hydraulic (medium)
            jitter = span * (0.03 + 0.05 * degradation)
            h1, f1 = span * 0.05, 0.28
            h2, f2 = span * 0.03, 0.55
            h3, f3 = span * 0.02, 0.12
        else:
            theta = 0.20
            jitter = span * 0.04
            h1, f1 = span * 0.03, 0.25
            h2, f2 = span * 0.02, 0.50
            h3, f3 = span * 0.01, 0.10

        # --- 4. Multi-frequency harmonic stack (3 sinusoids) ---
        oscillation = (
            h1 * math.sin(self._tick * f1 + self._phase)
            + h2 * math.sin(self._tick * f2 + self._phase2)
            + h3 * math.sin(self._tick * f3 + self._phase3)
        )

        # --- 5. Occasional bidirectional transient spikes ---
        spike = 0.0
        if self._spike_cooldown > 0:
            self._spike_cooldown -= 1
        elif self._rng.random() < 0.04 + 0.06 * degradation:
            # Spike can go UP or DOWN
            direction = 1.0 if self._rng.random() > 0.35 else -1.0
            magnitude = span * self._rng.uniform(0.15, 0.40) * (1.0 + degradation)
            spike = direction * magnitude
            self._spike_cooldown = self._rng.randint(3, 8)

        # --- 6. Mean-reversion drift + noise ---
        drift = theta * (effective_target - self._current)
        noise = self._rng.uniform(-jitter, jitter)

        # --- 7. Integrate full multi-dimensional state ---
        self._current += drift + oscillation + noise + spike

        # Soft physical bounds (wide enough to allow multi-axis motion)
        floor = self._profile.normal_min - span * 0.15
        ceiling = self._profile.abnormal_max + span * 0.10
        self._current = max(floor, min(ceiling, self._current))

        return round(self._current, 1)
