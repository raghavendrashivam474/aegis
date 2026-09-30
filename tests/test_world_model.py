"""Tests for Aegis World Model aggregate, relationships, lifecycle, and invariants."""

import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "packages"))

from domain import (
    Asset,
    Device,
    DuplicateEntityError,
    EntityNotFoundError,
    EntityStatus,
    InvariantViolationError,
    Observation,
    QualityFlag,
    Sensor,
    World,
    WorldModel,
)


def create_sample_world() -> WorldModel:
    """Helper to build a valid WorldModel instance."""
    world = World(
        world_id="world-alpha",
        name="Oil Field Alpha",
        description="Primary Extraction Facility",
    )
    model = WorldModel(world)

    asset = Asset(
        asset_id="asset-pump-101",
        name="Pump P-101",
        asset_type="pump",
        world_id="world-alpha",
    )
    model.add_asset(asset)

    device = Device(
        device_id="dev-esp32-001",
        name="ESP32 Gateway Node",
        asset_id="asset-pump-101",
    )
    model.add_device(device)

    sensor_temp = Sensor(
        sensor_id="sen-temp-01",
        name="Bearing Temperature",
        measurement_type="temperature",
        unit="celsius",
        device_id="dev-esp32-001",
    )
    sensor_vib = Sensor(
        sensor_id="sen-vib-01",
        name="Vibration Transducer",
        measurement_type="vibration",
        unit="mm/s",
        device_id="dev-esp32-001",
    )
    model.add_sensor(sensor_temp)
    model.add_sensor(sensor_vib)

    return model


def test_world_model_hierarchy_and_lookups():
    """Verify entities are correctly indexed and queryable."""
    model = create_sample_world()

    assert model.world.name == "Oil Field Alpha"
    assert model.get_asset("asset-pump-101").name == "Pump P-101"
    assert model.get_device("dev-esp32-001").name == "ESP32 Gateway Node"
    assert model.get_sensor("sen-temp-01").measurement_type == "temperature"

    # Test reverse tree traversal: Sensor -> Asset
    parent_asset = model.find_sensor_parent_asset("sen-temp-01")
    assert parent_asset.asset_id == "asset-pump-101"


def test_duplicate_asset_rejection():
    """World Model must reject duplicate asset IDs."""
    model = create_sample_world()
    dup_asset = Asset(
        asset_id="asset-pump-101",
        name="Duplicate Pump",
        asset_type="pump",
        world_id="world-alpha",
    )
    with pytest.raises(DuplicateEntityError):
        model.add_asset(dup_asset)


def test_duplicate_device_and_sensor_rejection():
    """World Model must reject duplicate device and sensor IDs."""
    model = create_sample_world()
    dup_device = Device(
        device_id="dev-esp32-001",
        name="Duplicate Node",
        asset_id="asset-pump-101",
    )
    with pytest.raises(DuplicateEntityError):
        model.add_device(dup_device)

    dup_sensor = Sensor(
        sensor_id="sen-temp-01",
        name="Duplicate Temp Sensor",
        measurement_type="temperature",
        unit="celsius",
        device_id="dev-esp32-001",
    )
    with pytest.raises(DuplicateEntityError):
        model.add_sensor(dup_sensor)


def test_orphaned_attachment_rejection():
    """Entities referencing non-existent parents must be rejected."""
    model = create_sample_world()

    orphan_device = Device(
        device_id="dev-ghost",
        name="Ghost Device",
        asset_id="non-existent-asset",
    )
    with pytest.raises(EntityNotFoundError):
        model.add_device(orphan_device)

    orphan_sensor = Sensor(
        sensor_id="sen-ghost",
        name="Ghost Sensor",
        measurement_type="temperature",
        unit="celsius",
        device_id="non-existent-device",
    )
    with pytest.raises(EntityNotFoundError):
        model.add_sensor(orphan_sensor)


def test_cross_world_asset_rejection():
    """Asset belonging to a different world must be rejected."""
    model = create_sample_world()
    alien_asset = Asset(
        asset_id="asset-alien",
        name="Alien Asset",
        asset_type="turbine",
        world_id="world-beta",
    )
    with pytest.raises(InvariantViolationError):
        model.add_asset(alien_asset)


def test_entity_lifecycle_status_transitions():
    """Verify entity status can be updated across all hierarchy levels."""
    model = create_sample_world()

    # Initial states default to ACTIVE
    assert model.world.status == EntityStatus.ACTIVE
    assert model.get_asset("asset-pump-101").status == EntityStatus.ACTIVE
    assert model.get_device("dev-esp32-001").status == EntityStatus.ACTIVE
    assert model.get_sensor("sen-temp-01").status == EntityStatus.ACTIVE

    # Transition states to INACTIVE
    model.set_entity_status("asset-pump-101", EntityStatus.INACTIVE)
    assert model.get_asset("asset-pump-101").status == EntityStatus.INACTIVE

    model.set_entity_status("sen-temp-01", EntityStatus.INACTIVE)
    assert model.get_sensor("sen-temp-01").status == EntityStatus.INACTIVE

    # Unknown entity status update fails
    with pytest.raises(EntityNotFoundError):
        model.set_entity_status("unknown-entity-id", EntityStatus.ACTIVE)


def test_observation_validation():
    """Observations must be validated against registered sensors and devices."""
    model = create_sample_world()
    now = datetime.now(UTC)

    # Valid observation
    valid_obs = Observation(
        observation_id="obs-100",
        device_id="dev-esp32-001",
        sensor_id="sen-temp-01",
        timestamp=now,
        value=72.4,
        unit="celsius",
        quality=QualityFlag.GOOD,
    )
    model.validate_observation(valid_obs)  # Should not raise

    # Unknown sensor
    unknown_sensor_obs = Observation(
        observation_id="obs-101",
        device_id="dev-esp32-001",
        sensor_id="sen-unknown",
        timestamp=now,
        value=50.0,
        unit="celsius",
    )
    with pytest.raises(InvariantViolationError, match="unknown Sensor"):
        model.validate_observation(unknown_sensor_obs)

    # Mismatched device ID for a valid sensor
    mismatched_dev_obs = Observation(
        observation_id="obs-102",
        device_id="dev-wrong-002",
        sensor_id="sen-temp-01",
        timestamp=now,
        value=72.4,
        unit="celsius",
    )
    with pytest.raises(InvariantViolationError, match="does not match Sensor parent"):
        model.validate_observation(mismatched_dev_obs)
