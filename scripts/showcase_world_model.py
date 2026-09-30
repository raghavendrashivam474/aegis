"""
P1.S2 World Model Showcase Demonstration.

Constructs, validates, queries, and displays a complete multi-asset
hierarchical industrial world model with active telemetry observations.
Demonstrates both valid tree operations and catchable invariant violations.
"""

import sys
from datetime import UTC, datetime
from pathlib import Path

# Insert packages directory into sys.path to find domain and contracts
sys.path.insert(0, str(Path(__file__).parent.parent / "packages"))

from domain import (
    Asset,
    Device,
    DuplicateEntityError,
    InMemoryWorldRepository,
    InvariantViolationError,
    Observation,
    Sensor,
    World,
    WorldModel,
)


def run_showcase() -> None:
    print("=" * 80)
    print("                     AEGIS P1.S2 WORLD MODEL SHOWCASE")
    print("=" * 80)

    # 1. World Construction
    print("\n[1] Constructing new World operational environment...")
    world = World(
        world_id="world-oilfield-alpha",
        name="Oil Field Alpha",
        description="Offshore Extraction Platform Delta-7",
    )
    model = WorldModel(world)
    print(f" -> Created World: '{world.name}' [{world.world_id}] (Status: {world.status})")

    # 2. Add Assets
    print("\n[2] Adding Assets to World...")
    pump = Asset(
        asset_id="asset-pump-101",
        name="Centrifugal Pump P-101",
        asset_type="pump",
        world_id="world-oilfield-alpha",
    )
    compressor = Asset(
        asset_id="asset-compressor-201",
        name="Gas Compressor C-201",
        asset_type="compressor",
        world_id="world-oilfield-alpha",
    )
    model.add_asset(pump)
    model.add_asset(compressor)
    print(f" -> Added Asset: '{pump.name}' (Type: {pump.asset_type})")
    print(f" -> Added Asset: '{compressor.name}' (Type: {compressor.asset_type})")

    # 3. Attach Devices
    print("\n[3] Attaching Edge Devices to Assets...")
    esp32 = Device(
        device_id="device-esp32-001",
        name="ESP32 telemetry Node-A",
        asset_id="asset-pump-101",
    )
    gateway = Device(
        device_id="device-gateway-001",
        name="Modbus TCP Gateway-A",
        asset_id="asset-compressor-201",
    )
    model.add_device(esp32)
    model.add_device(gateway)
    print(f" -> Attached Device: '{esp32.name}' to '{pump.name}'")
    print(f" -> Attached Device: '{gateway.name}' to '{compressor.name}'")

    # 4. Add Sensors
    print("\n[4] Attaching Sensors to Devices...")
    temp_sensor = Sensor(
        sensor_id="sensor-temp-01",
        name="Bearing Temperature",
        measurement_type="temperature",
        unit="°C",
        device_id="device-esp32-001",
    )
    vib_sensor = Sensor(
        sensor_id="sensor-vib-01",
        name="Casing Vibration",
        measurement_type="vibration",
        unit="mm/s",
        device_id="device-esp32-001",
    )
    press_sensor = Sensor(
        sensor_id="sensor-press-01",
        name="Discharge Pressure",
        measurement_type="pressure",
        unit="bar",
        device_id="device-gateway-001",
    )
    model.add_sensor(temp_sensor)
    model.add_sensor(vib_sensor)
    model.add_sensor(press_sensor)
    print(f" -> Attached Sensors: '{temp_sensor.name}', '{vib_sensor.name}' to '{esp32.name}'")
    print(f" -> Attached Sensor: '{press_sensor.name}' to '{gateway.name}'")

    # 5. Formulate Telemetry Observations & Validate Invariants
    print("\n[5] Simulating Real-Time Observations...")
    now = datetime.now(UTC)

    obs_temp = Observation(
        observation_id="obs-001",
        device_id="device-esp32-001",
        sensor_id="sensor-temp-01",
        timestamp=now,
        value=71.4,
        unit="°C",
    )
    obs_vib = Observation(
        observation_id="obs-002",
        device_id="device-esp32-001",
        sensor_id="sensor-vib-01",
        timestamp=now,
        value=2.3,
        unit="mm/s",
    )
    obs_press = Observation(
        observation_id="obs-003",
        device_id="device-gateway-001",
        sensor_id="sensor-press-01",
        timestamp=now,
        value=14.2,
        unit="bar",
    )

    model.validate_observation(obs_temp)
    model.validate_observation(obs_vib)
    model.validate_observation(obs_press)
    print(" -> All telemetry observations successfully validated.")

    observations_by_sensor = {
        "sensor-temp-01": obs_temp,
        "sensor-vib-01": obs_vib,
        "sensor-press-01": obs_press,
    }

    # 6. Demonstrate Invariant Violations (Error Safety Check)
    print("\n[6] DEMONSTRATING DOMAIN INVARIANT REJECTIONS (Error Safety Check)...")

    # 6a. Attempt duplicate registration
    try:
        duplicate_pump = Asset(
            asset_id="asset-pump-101",
            name="Cloned Centrifugal Pump",
            asset_type="pump",
            world_id="world-oilfield-alpha",
        )
        print(" -> Attempting to add duplicate asset ID 'asset-pump-101'...")
        model.add_asset(duplicate_pump)
    except DuplicateEntityError as err:
        print(f" [PASS REJECTION] Successfully rejected duplicate registration: {err}")

    # 6b. Attempt to validate observation with mismatched device ID
    try:
        malicious_obs = Observation(
            observation_id="obs-malicious",
            device_id="device-maligned-099",
            sensor_id="sensor-temp-01",
            timestamp=now,
            value=195.3,
            unit="°C",
        )
        print(" -> Attempting to validate observation with mismatched Device ID...")
        model.validate_observation(malicious_obs)
    except InvariantViolationError as err:
        print(f" [PASS REJECTION] Successfully blocked mismatched observation: {err}")

    # 7. Persistence Demonstration
    print("\n[7] Persisting World Model state through Abstract Repository Port...")
    repo = InMemoryWorldRepository()
    repo.save(model)
    assert repo.exists("world-oilfield-alpha")

    retrieved_model = repo.get("world-oilfield-alpha")
    total_stored = len(repo.list_all())
    print(f" -> Successfully saved and retrieved World Model. Active count: {total_stored}")

    # 8. Render Hierarchical Representation
    print("\n" + "=" * 80)
    print("                  RENDERED DIGITAL WORLD REPRESENTATION")
    print("=" * 80)

    r_world = retrieved_model.world
    print(f"Aegis World: {r_world.name} (ID: {r_world.world_id}, Status: {r_world.status})")

    for asset in r_world.assets:
        print(f"└── Asset: {asset.name} (ID: {asset.asset_id}, Status: {asset.status})")
        for device in asset.devices:
            print(
                f"    └── Device: {device.name} (ID: {device.device_id}, Status: {device.status})"
            )
            for sensor in device.sensors:
                obs = observations_by_sensor.get(sensor.sensor_id)
                obs_str = f"{obs.value} {obs.unit}" if obs else "No active telemetry"
                quality_str = f"[{obs.quality.value}]" if obs else ""
                s_id = sensor.sensor_id
                print(f"        ├── Sensor: {sensor.name} (ID: {s_id}, Status: {sensor.status})")
                print(f"        │   └── Observation: {obs_str} {quality_str}")

    print("=" * 80)
    print("Showcase run completed successfully.")


if __name__ == "__main__":
    run_showcase()
