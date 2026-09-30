"""
Simulation configuration for the Aegis Digital Asset Simulator.

All simulation parameters are centralised here so that scenarios,
seeds, and world topology can be changed without touching logic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class ScenarioType(Enum):
    """Supported simulation scenarios."""

    NORMAL = "normal"
    DEGRADATION = "degradation"


@dataclass(frozen=True)
class SensorProfile:
    """Describes one simulated sensor's identity and normal operating range."""

    sensor_id: str
    name: str
    measurement_type: str
    unit: str
    normal_min: float
    normal_max: float
    abnormal_max: float  # ceiling during degradation


@dataclass(frozen=True)
class DeviceProfile:
    """Describes one simulated device and its attached sensors."""

    device_id: str
    name: str
    sensors: tuple[SensorProfile, ...]


@dataclass(frozen=True)
class AssetProfile:
    """Describes one simulated asset and its attached devices."""

    asset_id: str
    name: str
    asset_type: str
    devices: tuple[DeviceProfile, ...]


# ---------------------------------------------------------------------------
# Default world topology — Oil Field Alpha
# ---------------------------------------------------------------------------

_DEFAULT_SENSORS_PUMP: tuple[SensorProfile, ...] = (
    SensorProfile(
        sensor_id="sensor-temp-{idx}",
        name="Temperature",
        measurement_type="temperature",
        unit="celsius",
        normal_min=65.0,
        normal_max=75.0,
        abnormal_max=95.0,
    ),
    SensorProfile(
        sensor_id="sensor-pressure-{idx}",
        name="Pressure",
        measurement_type="pressure",
        unit="bar",
        normal_min=7.5,
        normal_max=8.5,
        abnormal_max=12.0,
    ),
    SensorProfile(
        sensor_id="sensor-vibration-{idx}",
        name="Vibration",
        measurement_type="vibration_rms",
        unit="mm/s",
        normal_min=1.5,
        normal_max=2.5,
        abnormal_max=6.0,
    ),
)


def _build_default_assets(count: int = 2) -> tuple[AssetProfile, ...]:
    """Build *count* pump assets with deterministic IDs."""
    assets: list[AssetProfile] = []
    for i in range(1, count + 1):
        sensors = tuple(
            SensorProfile(
                sensor_id=s.sensor_id.format(idx=f"{i:02d}"),
                name=s.name,
                measurement_type=s.measurement_type,
                unit=s.unit,
                normal_min=s.normal_min,
                normal_max=s.normal_max,
                abnormal_max=s.abnormal_max,
            )
            for s in _DEFAULT_SENSORS_PUMP
        )
        device = DeviceProfile(
            device_id=f"device-motor-{i:02d}",
            name=f"Motor-{i:02d}",
            sensors=sensors,
        )
        asset = AssetProfile(
            asset_id=f"asset-pump-{i:02d}",
            name=f"Pump-{i:02d}",
            asset_type="pump",
            devices=(device,),
        )
        assets.append(asset)
    return tuple(assets)


@dataclass(frozen=True)
class SimulationConfig:
    """Top-level configuration for a simulation run."""

    world_id: str = "world-alpha"
    world_name: str = "Oil Field Alpha"
    seed: int = 42
    simulation_interval: float = 1.0  # seconds between ticks
    total_ticks: int = 10
    scenario: ScenarioType = ScenarioType.NORMAL
    degradation_start_tick: int = 6  # tick at which degradation begins
    assets: tuple[AssetProfile, ...] = field(default_factory=_build_default_assets)
