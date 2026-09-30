"""Seeds default registered devices into Aegis Device Registry."""

from __future__ import annotations

import logging
import os

from domain import Device, Sensor

from apps.backend.migrations import run_migrations
from apps.backend.postgres_adapter import PostgresDeviceRegistry

logger = logging.getLogger(__name__)


def build_default_registered_devices() -> list[Device]:
    """Return default devices matching simulator and physical ESP32 contracts."""
    devices = []

    # 1. Simulator Motor-01
    devices.append(
        Device(
            device_id="device-motor-01",
            name="Motor-01",
            asset_id="asset-pump-01",
            sensors=[
                Sensor(
                    "sensor-temp-01", "Motor Temp 01", "temperature", "celsius", "device-motor-01"
                ),
                Sensor(
                    "sensor-pressure-01", "Pump Pressure 01", "pressure", "bar", "device-motor-01"
                ),
                Sensor(
                    "sensor-vibration-01",
                    "Motor Vibration 01",
                    "vibration",
                    "mm/s",
                    "device-motor-01",
                ),
            ],
        )
    )

    # 2. Simulator Motor-02
    devices.append(
        Device(
            device_id="device-motor-02",
            name="Motor-02",
            asset_id="asset-pump-02",
            sensors=[
                Sensor(
                    "sensor-temp-02", "Motor Temp 02", "temperature", "celsius", "device-motor-02"
                ),
                Sensor(
                    "sensor-pressure-02", "Pump Pressure 02", "pressure", "bar", "device-motor-02"
                ),
                Sensor(
                    "sensor-vibration-02",
                    "Motor Vibration 02",
                    "vibration",
                    "mm/s",
                    "device-motor-02",
                ),
            ],
        )
    )

    # 3. Physical ESP32 Node
    devices.append(
        Device(
            device_id="device-esp32-01",
            name="Physical ESP32 Edge Node 01",
            asset_id="asset-pump-01",
            sensors=[
                Sensor(
                    "sensor-temp-device-esp32-01",
                    "ESP32 Temp",
                    "temperature",
                    "celsius",
                    "device-esp32-01",
                ),
                Sensor(
                    "sensor-humidity-device-esp32-01",
                    "ESP32 Humidity",
                    "humidity",
                    "percent",
                    "device-esp32-01",
                ),
                Sensor(
                    "sensor-vibration-device-esp32-01",
                    "ESP32 Vibration",
                    "vibration",
                    "mm/s",
                    "device-esp32-01",
                ),
            ],
        )
    )

    # 4. Ingestion Test Device
    devices.append(
        Device(
            device_id="device-esp32-99",
            name="Ingestion Test Node 99",
            asset_id="asset-test-99",
            sensors=[
                Sensor(
                    "sensor-temp-device-esp32-99",
                    "Test Temp",
                    "temperature",
                    "celsius",
                    "device-esp32-99",
                ),
            ],
        )
    )

    return devices


def seed_devices(database_url: str | None = None) -> None:
    db_url = database_url or os.getenv(
        "AEGIS_DATABASE_URL",
        "postgresql://aegis_admin:aegis_password@localhost:5434/aegis_db",
    )
    run_migrations(db_url)
    registry = PostgresDeviceRegistry(db_url)

    devices = build_default_registered_devices()
    for dev in devices:
        registry.register_device(dev)
        logger.info("Registered device '%s' with %d sensors.", dev.device_id, len(dev.sensors))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    seed_devices()
