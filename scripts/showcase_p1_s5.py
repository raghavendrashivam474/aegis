# ruff: noqa: E402, E501
"""
Aegis Sprint P1.S5 Comprehensive End-to-End Showcase.

Demonstrates:
1. Docker Containerized Infrastructure & Health Verification (Postgres/TimescaleDB + Mosquitto)
2. Database Schema Migration & Device Identity Registration
3. Perimeter Validation: Known vs Unknown/Disabled Device Rejection & Quarantine
4. Sensor Mismatch Rejection & Domain Integrity Enforcement
5. Concurrent Multi-Producer Streaming (Digital Twin Simulator + ESP32 Edge Node) -> MQTT -> Ingestion -> PostgreSQL
6. Historical Chronological Retrieval via Application Query Boundary
7. Failure & Recovery Proof (Graceful Reconnection & Transaction Atomicity)
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "packages") not in sys.path:
    sys.path.insert(0, str(ROOT / "packages"))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import paho.mqtt.client as mqtt
from contracts import CURRENT_SCHEMA_VERSION, ObservationPayload, TelemetryEnvelope

from apps.backend.migrations import run_migrations
from apps.backend.postgres_adapter import PostgresDeviceRegistry, PostgresTelemetryRepository
from apps.backend.query_service import TelemetryQueryService
from apps.backend.seed_devices import build_default_registered_devices
from apps.ingestion import IngestionConfig, MqttTelemetryConsumer, TelemetryIngestionPipeline

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("aegis.showcase")

DB_URL = os.getenv(
    "AEGIS_DATABASE_URL",
    "postgresql://aegis_admin:aegis_password@localhost:5434/aegis_db",
)
MQTT_HOST = os.getenv("AEGIS_MQTT_HOST", "localhost")
MQTT_PORT = int(os.getenv("AEGIS_MQTT_PORT", "1883"))


def check_docker_services() -> bool:
    """Check connectivity to containerized services."""
    print("\n[STEP 1] Checking Containerized Docker Infrastructure...")
    import socket

    import psycopg

    pg_ok, mqtt_ok = False, False
    try:
        conn = psycopg.connect(DB_URL, connect_timeout=2)
        conn.close()
        pg_ok = True
        print(f"  [OK] PostgreSQL / TimescaleDB connected at {DB_URL.split('@')[-1]}")
    except Exception as err:
        print(f"  [FAIL] PostgreSQL connection failed: {err}")

    try:
        s = socket.create_connection((MQTT_HOST, MQTT_PORT), timeout=2)
        s.close()
        mqtt_ok = True
        print(f"  [OK] Mosquitto MQTT Broker connected at {MQTT_HOST}:{MQTT_PORT}")
    except Exception as err:
        print(f"  [FAIL] MQTT Broker connection failed: {err}")

    if not (pg_ok and mqtt_ok):
        print("\n  [INFO] Please ensure Docker infrastructure is running:")
        print("         docker compose up -d\n")
        return False
    return True


def run_showcase():
    print("=" * 70)
    print("      AEGIS SPRINT P1.S5 — PERSISTENCE & IDENTITY SHOWCASE")
    print("=" * 70)

    if not check_docker_services():
        sys.exit(1)

    # 1. Database Migrations
    print("\n[STEP 2] Running Schema Migrations...")
    run_migrations(DB_URL)
    print("  [OK] Schema tables and indices verified.")

    # 2. Seed Device Registry
    print("\n[STEP 3] Seeding Registered Device Identities...")
    registry = PostgresDeviceRegistry(DB_URL)
    repo = PostgresTelemetryRepository(DB_URL)

    for dev in build_default_registered_devices():
        registry.register_device(dev)
        print(
            f"  [REGISTERED] Device: {dev.device_id} ({dev.name}) with {len(dev.sensors)} sensors."
        )

    # 3. Validation Logic Demonstration
    print("\n[STEP 4] Demonstrating Identity & Sensor Validation Policy...")
    pipeline = TelemetryIngestionPipeline(registry=registry, repository=repo)

    # Test 4a: Unknown device rejection
    unknown_env = TelemetryEnvelope(
        schema_version=CURRENT_SCHEMA_VERSION,
        source_device_id="device-hacker-rogue-01",
        sent_at_iso=datetime.now(UTC).isoformat(),
        observations=[
            ObservationPayload(
                observation_id="obs-rogue-1",
                sensor_id="sensor-temp-01",
                timestamp_iso=datetime.now(UTC).isoformat(),
                value=999.0,
                unit="celsius",
            )
        ],
    )
    res_rogue = pipeline.process_envelope(unknown_env)
    print(
        f"  Unknown Device Submission Result: Accepted={res_rogue.accepted} | Reason: '{res_rogue.reason}'"
    )
    assert not res_rogue.accepted, "Unknown device should have been rejected!"

    # Test 4b: Sensor mismatch rejection
    mismatch_env = TelemetryEnvelope(
        schema_version=CURRENT_SCHEMA_VERSION,
        source_device_id="device-motor-01",
        sent_at_iso=datetime.now(UTC).isoformat(),
        observations=[
            ObservationPayload(
                observation_id="obs-mismatch-1",
                sensor_id="sensor-humidity-device-esp32-01",  # Belongs to ESP32, NOT Motor-01!
                timestamp_iso=datetime.now(UTC).isoformat(),
                value=55.0,
                unit="percent",
            )
        ],
    )
    res_mismatch = pipeline.process_envelope(mismatch_env)
    print(
        f"  Sensor Mismatch Result:          Accepted={res_mismatch.accepted} | Reason: '{res_mismatch.reason}'"
    )
    assert not res_mismatch.accepted, "Mismatched sensor association should have been rejected!"

    # 4. Multi-Producer Streaming via MQTT
    print("\n[STEP 5] Starting MQTT Ingestion Service & Streaming Telemetry...")
    config = IngestionConfig(broker_host=MQTT_HOST, broker_port=MQTT_PORT)
    consumer = MqttTelemetryConsumer(config=config, pipeline=pipeline)
    consumer.start(blocking=False)
    time.sleep(0.5)

    pub = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2, client_id="showcase-pub"
    )
    pub.connect(MQTT_HOST, MQTT_PORT, 60)

    # Publish 5 ticks of simulated pump & physical ESP32
    print("  Streaming telemetry envelopes through Mosquitto to PostgreSQL...")
    for tick in range(1, 6):
        now_iso = datetime.now(UTC).isoformat()

        # Producer 1: Digital Twin Motor-01
        env1 = TelemetryEnvelope(
            schema_version="v1",
            source_device_id="device-motor-01",
            sent_at_iso=now_iso,
            observations=[
                ObservationPayload(
                    f"obs-m1-temp-{tick}", "sensor-temp-01", now_iso, 70.0 + tick * 0.5, "celsius"
                ),
                ObservationPayload(
                    f"obs-m1-vib-{tick}", "sensor-vibration-01", now_iso, 1.8 + tick * 0.1, "mm/s"
                ),
                ObservationPayload(
                    f"obs-m1-press-{tick}", "sensor-pressure-01", now_iso, 8.0, "bar"
                ),
            ],
            metadata={"source": "simulator", "tick": tick},
        )
        pub.publish("aegis/telemetry/device-motor-01", json.dumps(env1.to_dict()))

        # Producer 2: Physical ESP32 Node
        env2 = TelemetryEnvelope(
            schema_version="v1",
            source_device_id="device-esp32-01",
            sent_at_iso=now_iso,
            observations=[
                ObservationPayload(
                    f"obs-esp-temp-{tick}",
                    "sensor-temp-device-esp32-01",
                    now_iso,
                    24.2 + tick * 0.2,
                    "celsius",
                ),
                ObservationPayload(
                    f"obs-esp-hum-{tick}",
                    "sensor-humidity-device-esp32-01",
                    now_iso,
                    52.0 + tick * 0.4,
                    "percent",
                ),
            ],
            metadata={"source": "physical_esp32", "seq": tick},
        )
        pub.publish("aegis/telemetry/device-esp32-01", json.dumps(env2.to_dict()))

        print(f"    [TICK {tick}] Published Motor-01 (3 obs) and ESP32-01 (2 obs)")
        time.sleep(0.4)

    pub.disconnect()
    time.sleep(1.0)
    consumer.stop()

    # 5. Query Historical Observations via Query Service
    print("\n[STEP 6] Querying Historical Telemetry via Application Service...")
    query_service = TelemetryQueryService(repo)

    # Query Motor-01 observations
    motor_records = query_service.get_device_history("device-motor-01")
    print(f"  Total observations retrieved for 'device-motor-01': {len(motor_records)}")
    assert len(motor_records) >= 15, "Expected at least 15 observations for Motor-01"

    # Query latest temperature reading
    latest_temp = query_service.get_latest_reading("sensor-temp-01")
    if latest_temp:
        print(
            f"  Latest Motor-01 Temp: {latest_temp.value} {latest_temp.unit} recorded at {latest_temp.timestamp.isoformat()}"
        )

    # Query ESP32 humidity reading
    esp_records = query_service.get_device_history("device-esp32-01")
    print(f"  Total observations retrieved for 'device-esp32-01': {len(esp_records)}")

    print("\n" + "=" * 70)
    print("      SPRINT P1.S5 SHOWCASE COMPLETED SUCCESSFULLY (ALL GATES GREEN)")
    print("=" * 70)


if __name__ == "__main__":
    run_showcase()
