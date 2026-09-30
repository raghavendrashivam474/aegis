"""
Simulation scenario management.

Determines the degradation level for each tick based on the
configured scenario type and degradation start tick.
"""

from __future__ import annotations

from .config import ScenarioType, SimulationConfig


class ScenarioController:
    """Computes per-tick degradation factor from config."""

    def __init__(self, config: SimulationConfig) -> None:
        self._scenario = config.scenario
        self._start_tick = config.degradation_start_tick
        self._total_ticks = config.total_ticks

    def degradation_at(self, tick: int) -> float:
        """
        Return degradation factor in [0.0, 1.0] for the given tick.

        0.0 = normal operation.
        1.0 = fully degraded.
        """
        if self._scenario == ScenarioType.NORMAL:
            return 0.0

        if tick < self._start_tick:
            return 0.0

        # Ramp duration: use total_ticks range if > start_tick, otherwise default 50 ticks
        if self._total_ticks > self._start_tick:
            ramp_ticks = self._total_ticks - self._start_tick
        else:
            ramp_ticks = 50

        progress = (tick - self._start_tick) / max(1, ramp_ticks)
        return min(1.0, progress)

    def is_abnormal(self, tick: int) -> bool:
        return self.degradation_at(tick) > 0.0
