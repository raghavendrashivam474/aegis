# ruff: noqa: E402
"""
Aegis Digital Asset Simulator — orchestration layer.

Coordinates world creation, entity population, observation
generation, repository persistence, and telemetry mapping.
"""

from __future__ import annotations

import random
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path

# Ensure packages/ is importable regardless of how the script is invoked
_PACKAGES = str(Path(__file__).resolve().parents[2] / "packages")
if _PACKAGES not in sys.path:
    sys.path.insert(0, _PACKAGES)

from contracts import (
    CURRENT_SCHEMA_VERSION,
    ObservationMapper,
    TelemetryEnvelope,
)
from domain import (
    Asset,
    Device,
    Observation,
    QualityFlag,
    Sensor,
    World,
    WorldModel,
)
from domain.repository import InMemoryWorldRepository

from .config import SimulationConfig
from .generator import SensorGenerator
from .scenario import ScenarioController


@dataclass
class TickResult:
    """Output of a single simulation tick."""

    tick: int
    timestamp: datetime
    observations: list[Observation] = field(default_factory=list)
    envelopes: list[TelemetryEnvelope] = field(default_factory=list)


class Simulator:
    """Top-level simulation orchestrator."""

    def __init__(self, config: SimulationConfig | None = None) -> None:
        self.config = config or SimulationConfig()
        self._rng = random.Random(self.config.seed)
        self._scenario = ScenarioController(self.config)
        self._repo = InMemoryWorldRepository()
        self._generators: dict[str, SensorGenerator] = {}
        self._world_model: WorldModel | None = None
        self._base_time = datetime(2026, 1, 1, 8, 0, 0, tzinfo=UTC)

        # Flat lookup: sensor_id → (asset_name, device_id)
        self._sensor_context: dict[str, tuple[str, str]] = {}

    # ------------------------------------------------------------------
    # World bootstrap
    # ------------------------------------------------------------------

    def build_world(self) -> WorldModel:
        """Create and persist the simulated world from config."""
        world = World(
            world_id=self.config.world_id,
            name=self.config.world_name,
        )
        model = WorldModel(world)

        for asset_prof in self.config.assets:
            asset = Asset(
                asset_id=asset_prof.asset_id,
                name=asset_prof.name,
                asset_type=asset_prof.asset_type,
                world_id=self.config.world_id,
            )
            model.add_asset(asset)

            for dev_prof in asset_prof.devices:
                sensors_domain: list[Sensor] = []
                for sen_prof in dev_prof.sensors:
                    sensor = Sensor(
                        sensor_id=sen_prof.sensor_id,
                        name=sen_prof.name,
                        measurement_type=sen_prof.measurement_type,
                        unit=sen_prof.unit,
                        device_id=dev_prof.device_id,
                    )
                    sensors_domain.append(sensor)

                    # Build generator
                    self._generators[sen_prof.sensor_id] = SensorGenerator(
                        profile=sen_prof, rng=self._rng
                    )
                    self._sensor_context[sen_prof.sensor_id] = (
                        asset_prof.name,
                        dev_prof.device_id,
                    )

                device = Device(
                    device_id=dev_prof.device_id,
                    name=dev_prof.name,
                    asset_id=asset_prof.asset_id,
                    sensors=sensors_domain,
                )
                model.add_device(device)

        self._world_model = model
        self._repo.save(model)
        return model

    # ------------------------------------------------------------------
    # Simulation ticks
    # ------------------------------------------------------------------

    def run_tick(self, tick: int) -> TickResult:
        """Execute one simulation tick and return observations + envelopes."""
        if self._world_model is None:
            raise RuntimeError("Call build_world() before run_tick().")

        ts = self._base_time + timedelta(seconds=tick * self.config.simulation_interval)
        degradation = self._scenario.degradation_at(tick)
        result = TickResult(tick=tick, timestamp=ts)

        # Group observations by device for envelope creation
        device_observations: dict[str, list[Observation]] = {}

        for sensor_id, gen in self._generators.items():
            value = gen.next_value(degradation=degradation)
            asset_name, device_id = self._sensor_context[sensor_id]

            quality = QualityFlag.GOOD
            if degradation > 0.7:
                quality = QualityFlag.UNCERTAIN

            obs = Observation(
                observation_id=f"obs-{sensor_id}-{tick:04d}",
                device_id=device_id,
                sensor_id=sensor_id,
                timestamp=ts,
                value=value,
                unit=gen.unit,
                quality=quality,
                metadata={"asset": asset_name, "tick": str(tick)},
            )

            # Validate against world model invariants
            self._world_model.validate_observation(obs)

            result.observations.append(obs)
            device_observations.setdefault(device_id, []).append(obs)

        # Map to telemetry envelopes (one per device per tick)
        for device_id, obs_list in device_observations.items():
            payloads = [ObservationMapper.to_contract(o) for o in obs_list]
            envelope = TelemetryEnvelope(
                schema_version=CURRENT_SCHEMA_VERSION,
                source_device_id=device_id,
                sent_at_iso=ts.isoformat(),
                observations=payloads,
            )
            result.envelopes.append(envelope)

        return result

    def run(self) -> list[TickResult]:
        """Run the full simulation and return all tick results."""
        if self._world_model is None:
            self.build_world()

        results: list[TickResult] = []
        for tick in range(1, self.config.total_ticks + 1):
            results.append(self.run_tick(tick))
        return results

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------

    @property
    def repository(self) -> InMemoryWorldRepository:
        return self._repo

    @property
    def world_model(self) -> WorldModel | None:
        return self._world_model
