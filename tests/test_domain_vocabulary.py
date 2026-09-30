"""Tests validating Domain vocabulary and entity definitions."""

import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "packages"))

from domain import Asset, Device, Observation, QualityFlag, Sensor, World


def test_observation_instantiation():
    """Observation entities must hold measurement state and support immutability."""
    now = datetime.now(UTC)
    obs = Observation(
        observation_id="obs-001",
        device_id="dev-001",
        sensor_id="sen-001",
        timestamp=now,
        value=74.5,
        unit="celsius",
        quality=QualityFlag.GOOD,
    )
    assert obs.observation_id == "obs-001"
    assert obs.value == 74.5
    assert obs.quality == QualityFlag.GOOD

    with pytest.raises(Exception):
        obs.value = 80.0  # type: ignore


def test_sensor_and_device_association():
    """Sensors are linked to devices, and devices to assets."""
    sensor = Sensor(
        sensor_id="sen-vib-01",
        name="Vibration Sensor X",
        measurement_type="vibration",
        unit="mm/s",
        device_id="dev-esp32-01",
    )
    device = Device(
        device_id="dev-esp32-01",
        name="ESP32 Node A",
        asset_id="asset-pump-101",
        sensors=[sensor],
    )
    assert len(device.sensors) == 1
    assert device.sensors[0].sensor_id == "sen-vib-01"


def test_world_model_hierarchy():
    """World contains assets, which contain devices."""
    world = World(
        world_id="world-refinery-1",
        name="Refinery Unit 1",
        description="Main refinery floor",
    )
    asset = Asset(
        asset_id="asset-pump-101",
        name="Centrifugal Pump 101",
        asset_type="pump",
        world_id=world.world_id,
    )
    world.assets.append(asset)

    assert len(world.assets) == 1
    assert world.assets[0].name == "Centrifugal Pump 101"
