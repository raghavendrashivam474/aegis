# ruff: noqa: E402, E501
"""
P1.S6 Integration Tests — Unified Operational World.

Verifies end-to-end integration across simulator, MQTT transport,
perimeter validation, PostgreSQL persistence, and query service retrieval.
"""

import json
import os
import time
from datetime import UTC, datetime

import paho.mqtt.client as mqtt
import pytest
from contracts import CURRENT_SCHEMA_VERSION, ObservationPayload, TelemetryEnvelope

from apps.backend.migrations import run_migrations
from apps.backend.postgres_adapter import PostgresDeviceRegistry, PostgresTelemetryRepository
from apps.backend.query_service import TelemetryQueryService
from apps.backend.seed_devices import build_default_registered_devices
from apps.ingestion import IngestionConfig, MqttTelemetryConsumer, TelemetryIngestionPipeline
from apps.simulator.config import ScenarioType, SimulationConfig
from apps.simulator.simulator import Simulator

DB_URL = os.getenv(
    "AEGIS_DATABASE_URL",
    "postgresql://aegis_admin:aegis_password@localhost:5434/aegis_db",
)
MQTT_HOST = os.getenv("AEGIS_MQTT_HOST", "localhost")
MQTT_PORT = int(os.getenv("AEGIS_MQTT_PORT", "1883"))


def _is_docker_online() -> bool:
    import socket

    import psycopg

    try:
        conn = psycopg.connect(DB_URL, connect_timeout=1)
        conn.close()
        s = socket.create_connection((MQTT_HOST, MQTT_PORT), timeout=1)
        s.close()
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _is_docker_online(),
    reason="Docker infrastructure (PostgreSQL:5434 / Mosquitto:1883) offline.",
)


@pytest.fixture(autouse=True)
def setup_database_and_registry():
    """Ensure database migrations run and registry is seeded before each S6 integration test."""
    run_migrations(DB_URL)
    registry = PostgresDeviceRegistry(DB_URL)
    for dev in build_default_registered_devices():
        registry.register_device(dev)


def test_fr_s6_01_unified_producer_flow():
    """FR-S6-01 & FR-S6-05 — Multi-producer telemetry flows through MQTT and persists to PostgreSQL."""
    registry = PostgresDeviceRegistry(DB_URL)
    repository = PostgresTelemetryRepository(DB_URL)
    pipeline = TelemetryIngestionPipeline(registry=registry, repository=repository)

    consumer = MqttTelemetryConsumer(
        config=IngestionConfig(broker_host=MQTT_HOST, broker_port=MQTT_PORT), pipeline=pipeline
    )
    consumer.start(blocking=False)
    time.sleep(0.3)

    pub = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2, client_id="test-s6-publisher"
    )
    pub.connect(MQTT_HOST, MQTT_PORT, 60)

    # 1. Digital Twin Simulator emission (with humidity enabled)
    sim_config = SimulationConfig(
        total_ticks=2,
        simulation_interval=0.1,
        scenario=ScenarioType.NORMAL,
        seed=123,
        include_humidity=True,
    )
    simulator = Simulator(sim_config)
    simulator.build_world()
    tick_res = simulator.run_tick(1)

    for env in tick_res.envelopes:
        pub.publish(f"aegis/telemetry/{env.source_device_id}", json.dumps(env.to_dict()))

    # 2. Physical ESP32 Node emission
    now_iso = datetime.now(UTC).isoformat()
    esp_env = TelemetryEnvelope(
        schema_version="v1",
        source_device_id="device-esp32-01",
        sent_at_iso=now_iso,
        observations=[
            ObservationPayload(
                "obs-test-esp-temp", "sensor-temp-device-esp32-01", now_iso, 26.5, "celsius"
            ),
            ObservationPayload(
                "obs-test-esp-hum", "sensor-humidity-device-esp32-01", now_iso, 58.2, "percent"
            ),
        ],
    )
    pub.publish("aegis/telemetry/device-esp32-01", json.dumps(esp_env.to_dict()))

    pub.disconnect()
    time.sleep(1.0)
    consumer.stop()

    # Verify query service retrieval
    qs = TelemetryQueryService(repository)
    motor_records = qs.get_device_history("device-motor-01")
    esp_records = qs.get_device_history("device-esp32-01")

    assert len(motor_records) >= 4  # temp, pressure, vibration, humidity
    assert len(esp_records) >= 2


def test_fr_s6_02_identity_integrity():
    """FR-S6-02 — Perimeter rejects unregistered devices and mismatched sensor ownership."""
    registry = PostgresDeviceRegistry(DB_URL)
    repository = PostgresTelemetryRepository(DB_URL)
    pipeline = TelemetryIngestionPipeline(registry=registry, repository=repository)

    # Unknown device
    unknown_env = TelemetryEnvelope(
        schema_version=CURRENT_SCHEMA_VERSION,
        source_device_id="device-unauthorized-01",
        sent_at_iso=datetime.now(UTC).isoformat(),
        observations=[
            ObservationPayload(
                "obs-1", "sensor-temp-01", datetime.now(UTC).isoformat(), 50.0, "celsius"
            )
        ],
    )
    res_unknown = pipeline.process_envelope(unknown_env)
    assert not res_unknown.accepted

    # Sensor association mismatch
    mismatch_env = TelemetryEnvelope(
        schema_version=CURRENT_SCHEMA_VERSION,
        source_device_id="device-motor-01",
        sent_at_iso=datetime.now(UTC).isoformat(),
        observations=[
            ObservationPayload(
                "obs-2",
                "sensor-temp-device-esp32-01",
                datetime.now(UTC).isoformat(),
                50.0,
                "celsius",
            )
        ],
    )
    res_mismatch = pipeline.process_envelope(mismatch_env)
    assert not res_mismatch.accepted
