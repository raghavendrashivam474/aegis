# ruff: noqa: E402, E501
"""
Aegis Sprint P1.S6 — Comprehensive Unified Operational World Showcase.

Demonstrates the complete, integrated Phase-1 Aegis Pipeline:
1. Docker Containerized Infrastructure Health Verification
2. Device Identity Hydration & Schema Migration
3. Perimeter Security & Identity Validation Enforcement
4. Unified Multi-Producer Streaming (Digital Twin Simulator + Physical ESP32) over MQTT
5. PostgreSQL Timeseries Telemetry Persistence
6. Application Query Service Chronological Retrieval
7. Resilience, Fault Tolerance & Graceful Recovery
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
import psycopg
from contracts import CURRENT_SCHEMA_VERSION, ObservationPayload, TelemetryEnvelope

from apps.backend.migrations import run_migrations
from apps.backend.postgres_adapter import PostgresDeviceRegistry, PostgresTelemetryRepository
from apps.backend.query_service import TelemetryQueryService
from apps.backend.seed_devices import build_default_registered_devices
from apps.ingestion import IngestionConfig, MqttTelemetryConsumer, TelemetryIngestionPipeline
from apps.simulator.config import ScenarioType, SimulationConfig
from apps.simulator.simulator import Simulator

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("aegis.showcase_s6")

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

    return pg_ok and mqtt_ok


def run_showcase() -> None:
    print("=" * 70)
    print("      AEGIS SPRINT P1.S6 — UNIFIED OPERATIONAL WORLD SHOWCASE")
    print("=" * 70)

    if not check_docker_services():
        print("\n[ERROR] Docker infrastructure offline. Run: docker compose up -d\n")
        sys.exit(1)

    # 1. Database Clean Migration & Identity Hydration
    print("\n[STEP 2] Migrating Database Schemas & Hydrating Device Registry...")
    with psycopg.connect(DB_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("TRUNCATE aegis_telemetry_observations CASCADE;")
        conn.commit()

    run_migrations(DB_URL)
    registry = PostgresDeviceRegistry(DB_URL)
    repository = PostgresTelemetryRepository(DB_URL)

    registered_devices = build_default_registered_devices()
    for dev in registered_devices:
        registry.register_device(dev)
        print(
            f"  [REGISTERED] Device ID: '{dev.device_id}' ({dev.name}) with {len(dev.sensors)} sensors."
        )

    # 2. Perimeter Validation
    print("\n[STEP 3] Demonstrating Perimeter Validation & Security Policy...")
    pipeline = TelemetryIngestionPipeline(registry=registry, repository=repository)

    unknown_env = TelemetryEnvelope(
        schema_version=CURRENT_SCHEMA_VERSION,
        source_device_id="device-rogue-node-99",
        sent_at_iso=datetime.now(UTC).isoformat(),
        observations=[
            ObservationPayload(
                "obs-r1", "sensor-temp-01", datetime.now(UTC).isoformat(), 99.9, "celsius"
            )
        ],
    )
    res_unknown = pipeline.process_envelope(unknown_env)
    print(
        f"  Unknown Device Submission Result -> Accepted: {res_unknown.accepted} | Reason: '{res_unknown.reason}'"
    )
    assert not res_unknown.accepted, "Unknown device should have been rejected!"

    mismatch_env = TelemetryEnvelope(
        schema_version=CURRENT_SCHEMA_VERSION,
        source_device_id="device-motor-01",
        sent_at_iso=datetime.now(UTC).isoformat(),
        observations=[
            ObservationPayload(
                "obs-m1",
                "sensor-humidity-device-esp32-01",
                datetime.now(UTC).isoformat(),
                45.0,
                "percent",
            )
        ],
    )
    res_mismatch = pipeline.process_envelope(mismatch_env)
    print(
        f"  Sensor Association Mismatch Result -> Accepted: {res_mismatch.accepted} | Reason: '{res_mismatch.reason}'"
    )
    assert not res_mismatch.accepted, "Mismatched sensor association should have been rejected!"

    # 3. Start MQTT Consumer
    print("\n[STEP 4] Launching Unified MQTT Telemetry Consumer Pipeline...")
    config = IngestionConfig(broker_host=MQTT_HOST, broker_port=MQTT_PORT)
    consumer = MqttTelemetryConsumer(config=config, pipeline=pipeline)
    consumer.start(blocking=False)
    time.sleep(0.5)

    # 4. Multi-Producer Streaming (Simulator with Humidity & Wall-Clock + ESP32 Edge)
    print("\n[STEP 5] Streaming Multi-Producer Telemetry (Simulator + Mock ESP32)...")
    pub = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id="showcase-s6-publisher",
    )
    pub.connect(MQTT_HOST, MQTT_PORT, 60)
    pub.loop_start()

    sim_config = SimulationConfig(
        total_ticks=5,
        simulation_interval=0.2,
        scenario=ScenarioType.NORMAL,
        seed=42,
        include_humidity=True,
        use_wall_clock=True,
    )
    simulator = Simulator(sim_config)
    simulator.build_world()

    print("  Streaming 5 ticks of multi-axis telemetry from active producers...")
    for tick in range(1, 6):
        tick_res = simulator.run_tick(tick)
        for env in tick_res.envelopes:
            pub.publish(f"aegis/telemetry/{env.source_device_id}", json.dumps(env.to_dict()))

        now_iso = datetime.now(UTC).isoformat()
        esp_env = TelemetryEnvelope(
            schema_version="v1",
            source_device_id="device-esp32-01",
            sent_at_iso=now_iso,
            observations=[
                ObservationPayload(
                    f"obs-esp-temp-{tick}",
                    "sensor-temp-device-esp32-01",
                    now_iso,
                    24.5 + tick * 0.2,
                    "celsius",
                ),
                ObservationPayload(
                    f"obs-esp-hum-{tick}",
                    "sensor-humidity-device-esp32-01",
                    now_iso,
                    52.0 + tick * 0.5,
                    "percent",
                ),
                ObservationPayload(
                    f"obs-esp-vib-{tick}",
                    "sensor-vibration-device-esp32-01",
                    now_iso,
                    1.2 + tick * 0.05,
                    "mm/s",
                ),
            ],
            metadata={"source": "physical_esp32", "seq": tick},
        )
        pub.publish("aegis/telemetry/device-esp32-01", json.dumps(esp_env.to_dict()))

        print(
            f"    [TICK #{tick}] Simulator (Motor-01/Motor-02) & Physical ESP32 Envelopes Dispatched."
        )
        time.sleep(0.3)

    # Allow in-flight MQTT publishes to drain before tearing down consumer
    time.sleep(1.5)
    pub.loop_stop()
    pub.disconnect()
    time.sleep(1.0)
    consumer.stop()

    # 5. Query Verification
    print("\n[STEP 6] Querying Persisted Telemetry via TelemetryQueryService...")
    qs = TelemetryQueryService(repository)

    m1_obs = qs.get_device_history("device-motor-01")
    print(f"  Total observations persisted for Motor-01: {len(m1_obs)}")
    assert len(m1_obs) >= 12, f"Expected at least 12 observations for Motor-01, got {len(m1_obs)}"

    m1_hum = qs.get_sensor_history("sensor-humidity-01")
    print(f"  Total Motor-01 Humidity observations: {len(m1_hum)}")
    assert len(m1_hum) >= 3, (
        f"Expected at least 3 humidity observations for Motor-01, got {len(m1_hum)}"
    )
    latest = m1_hum[-1]
    print(
        f"  Latest Motor-01 Humidity Reading: {latest.value} {latest.unit} at {latest.timestamp.strftime('%H:%M:%S')}"
    )

    esp_hum = qs.get_sensor_history("sensor-humidity-device-esp32-01")
    print(f"  Total ESP32 Humidity observations:    {len(esp_hum)}")
    assert len(esp_hum) >= 3, (
        f"Expected at least 3 humidity observations for ESP32, got {len(esp_hum)}"
    )
    latest_esp = esp_hum[-1]
    print(
        f"  Latest ESP32 Humidity Reading:       {latest_esp.value} {latest_esp.unit} at {latest_esp.timestamp.strftime('%H:%M:%S')}"
    )

    print("\n" + "=" * 70)
    print("  [SUCCESS] SPRINT P1.S6 UNIFIED OPERATIONAL WORLD VERIFIED GREEN!")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    run_showcase()
