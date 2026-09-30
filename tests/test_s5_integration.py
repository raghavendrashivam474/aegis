"""
P1.S5 End-to-End Integration Tests.

Verifies:
- FR-S5-07: Real MQTT broker integration (Mosquitto)
- FR-S5-01: PostgreSQL persistent telemetry storage
- FR-S5-04: End-to-end telemetry pipeline validation
- FR-S5-08: Graceful fallback and handling

NOTE: These tests run if a live Docker infrastructure is detected on localhost.
Otherwise, they skip gracefully, ensuring the standard CI pipeline stays green.
"""

from __future__ import annotations

import json
import os
import time
from datetime import UTC, datetime

import paho.mqtt.client as mqtt
import pytest
from contracts import CURRENT_SCHEMA_VERSION, ObservationPayload, TelemetryEnvelope
from domain import Device, Sensor

from apps.backend.migrations import run_migrations
from apps.backend.postgres_adapter import PostgresDeviceRegistry, PostgresTelemetryRepository
from apps.ingestion import IngestionConfig, MqttTelemetryConsumer, TelemetryIngestionPipeline

DB_URL = os.getenv(
    "AEGIS_DATABASE_URL",
    "postgresql://aegis_admin:aegis_password@localhost:5434/aegis_db",
)
MQTT_HOST = os.getenv("AEGIS_MQTT_HOST", "localhost")
MQTT_PORT = int(os.getenv("AEGIS_MQTT_PORT", "1883"))

# Establish if integration dependencies are present
pytestmark = pytest.mark.integration


def is_infra_available() -> bool:
    """Check if Postgres and Mosquitto are alive and reachable on localhost."""
    try:
        # Test PostgreSQL connection
        import psycopg

        conn = psycopg.connect(DB_URL, connect_timeout=1)
        conn.close()

        # Test Mosquitto broker socket connection
        import socket

        s = socket.create_connection((MQTT_HOST, MQTT_PORT), timeout=1)
        s.close()
        return True
    except Exception:
        return False


INFRA_AVAILABLE = is_infra_available()


@pytest.fixture(scope="module")
def setup_integration_db():
    """Ensure schema migrations are cleanly applied on the integration database."""
    if not INFRA_AVAILABLE:
        pytest.skip("Docker integration infrastructure is offline.")

    run_migrations(DB_URL)
    yield
    # Truncate tables cleanly after running integration scenarios
    import psycopg

    with psycopg.connect(DB_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("TRUNCATE TABLE aegis_telemetry_observations CASCADE;")
            cur.execute("TRUNCATE TABLE aegis_sensors CASCADE;")
            cur.execute("TRUNCATE TABLE aegis_devices CASCADE;")
        conn.commit()


def test_tc_s5_27_end_to_end_mqtt_to_postgres_delivery(setup_integration_db):
    """
    Scenario S1: Publisher -> Mosquitto -> Ingestion Pipeline -> Postgres.

    Verifies that a fully integrated transport + persistence pipeline executes successfully.
    """
    # 1. Register test device & sensors in Postgres
    registry = PostgresDeviceRegistry(DB_URL)
    repo = PostgresTelemetryRepository(DB_URL)

    test_device = Device(
        device_id="device-esp32-99",
        name="E2E Integration Test Node",
        asset_id="asset-test-99",
        sensors=[
            Sensor(
                sensor_id="sensor-temp-device-esp32-99",
                name="Thermal Ingestion Core",
                measurement_type="temperature",
                unit="celsius",
                device_id="device-esp32-99",
            )
        ],
    )
    registry.register_device(test_device)

    # 2. Spin up Ingestion Pipeline & consumer on background thread
    pipeline = TelemetryIngestionPipeline(registry=registry, repository=repo)
    config = IngestionConfig(
        broker_host=MQTT_HOST,
        broker_port=MQTT_PORT,
        topic="aegis/telemetry/device-esp32-99",
        client_id="aegis-e2e-consumer",
    )
    consumer = MqttTelemetryConsumer(config=config, pipeline=pipeline)
    consumer.start(blocking=False)

    # Wait for consumer background thread to establish connection
    time.sleep(0.5)

    try:
        # 3. Connect a mock client and publish a telemetry envelope
        pub_client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id="e2e-test-publisher",
        )
        pub_client.connect(MQTT_HOST, MQTT_PORT, 60)

        now_iso = datetime.now(UTC).isoformat()
        envelope = TelemetryEnvelope(
            schema_version=CURRENT_SCHEMA_VERSION,
            source_device_id="device-esp32-99",
            sent_at_iso=now_iso,
            observations=[
                ObservationPayload(
                    observation_id="obs-e2e-100",
                    sensor_id="sensor-temp-device-esp32-99",
                    timestamp_iso=now_iso,
                    value=34.8,
                    unit="celsius",
                )
            ],
            metadata={"transport": "mqtt"},
        )

        pub_client.publish("aegis/telemetry/device-esp32-99", json.dumps(envelope.to_dict()))
        pub_client.disconnect()

        # Allow network processing roundtrip
        time.sleep(1.0)

        # 4. Query PostgreSQL and verify correct persistence
        records = repo.get_observations(device_id="device-esp32-99")
        assert len(records) == 1
        assert records[0].observation_id == "obs-e2e-100"
        assert records[0].value == 34.8
        assert records[0].unit == "celsius"

    finally:
        consumer.stop()


def test_tc_s5_21_unknown_device_mqtt_rejected_and_not_persisted(setup_integration_db):
    """Verify that an unregistered device publishing via MQTT is rejected and not persisted."""
    registry = PostgresDeviceRegistry(DB_URL)
    repo = PostgresTelemetryRepository(DB_URL)

    # Confirm device is not registered
    if registry.is_registered("device-unknown-99"):
        import psycopg

        with psycopg.connect(DB_URL) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM aegis_devices WHERE device_id = %s;", ("device-unknown-99",)
                )

    pipeline = TelemetryIngestionPipeline(registry=registry, repository=repo)
    config = IngestionConfig(
        broker_host=MQTT_HOST,
        broker_port=MQTT_PORT,
        topic="aegis/telemetry/device-unknown-99",
        client_id="aegis-e2e-consumer-unknown",
    )
    consumer = MqttTelemetryConsumer(config=config, pipeline=pipeline)
    consumer.start(blocking=False)

    time.sleep(0.5)

    try:
        pub_client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id="e2e-test-pub-unknown",
        )
        pub_client.connect(MQTT_HOST, MQTT_PORT, 60)

        now_iso = datetime.now(UTC).isoformat()
        envelope = TelemetryEnvelope(
            schema_version=CURRENT_SCHEMA_VERSION,
            source_device_id="device-unknown-99",
            sent_at_iso=now_iso,
            observations=[
                ObservationPayload(
                    observation_id="obs-unknown-e2e",
                    sensor_id="sensor-temp-device-esp32-99",
                    timestamp_iso=now_iso,
                    value=45.0,
                    unit="celsius",
                )
            ],
        )

        pub_client.publish("aegis/telemetry/device-unknown-99", json.dumps(envelope.to_dict()))
        pub_client.disconnect()

        time.sleep(1.0)

        # Query database: should NOT contain records
        records = repo.get_observations(device_id="device-unknown-99")
        assert len(records) == 0

    finally:
        consumer.stop()
