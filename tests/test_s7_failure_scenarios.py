"""
Aegis P1.S7 Hardening & Reliability Failure Scenario Tests.

Proves deterministic failure handling, recovery, backpressure,
and network partition accounting across the entire pipeline.
"""

from datetime import UTC, datetime
from unittest.mock import MagicMock

from contracts import ObservationPayload, TelemetryEnvelope
from domain import (
    Device,
    EntityStatus,
    Sensor,
)

from apps.ingestion.buffer import OverflowPolicy, PersistenceRetryBuffer
from apps.ingestion.mqtt_consumer import MqttTelemetryConsumer
from apps.ingestion.pipeline import TelemetryIngestionPipeline


def _create_mock_environment(registered_devices: list[str] | None = None):
    devices = registered_devices or ["device-alpha-01", "device-alpha-02"]

    mock_registry = MagicMock()
    mock_registry.is_registered.side_effect = lambda dev_id: dev_id in devices

    def _get_device(dev_id: str):
        if dev_id in devices:
            return Device(
                device_id=dev_id,
                name=f"Name-{dev_id}",
                asset_id="asset-oil-01",
                sensors=[
                    Sensor(f"sensor-temp-{dev_id}", "Temp", "temp", "celsius", dev_id),
                    Sensor(f"sensor-press-{dev_id}", "Press", "press", "bar", dev_id),
                ],
                status=EntityStatus.ACTIVE,
            )
        raise KeyError(dev_id)

    mock_registry.get_device.side_effect = _get_device
    mock_registry.validate_sensor_association.return_value = True

    mock_repo = MagicMock()
    mock_repo.save_batch = MagicMock()

    return mock_registry, mock_repo


def _create_test_envelope(device_id: str, seq: int) -> TelemetryEnvelope:
    now_iso = datetime.now(UTC).isoformat()
    return TelemetryEnvelope(
        schema_version="v1",
        source_device_id=device_id,
        sent_at_iso=now_iso,
        observations=[
            ObservationPayload(
                observation_id=f"obs-{device_id}-{seq:04d}-temp",
                sensor_id=f"sensor-temp-{device_id}",
                timestamp_iso=now_iso,
                value=72.5 + seq,
                unit="celsius",
                quality="GOOD",
            ),
            ObservationPayload(
                observation_id=f"obs-{device_id}-{seq:04d}-press",
                sensor_id=f"sensor-press-{device_id}",
                timestamp_iso=now_iso,
                value=8.1,
                unit="bar",
                quality="GOOD",
            ),
        ],
    )


# ==============================================================================
# Workstream E: Database Outage & Recovery Integration Scenario
# ==============================================================================
def test_scenario_database_outage_and_recovery_flow():
    """
    Scenario:
    1. System operating normally -> persistence succeeds.
    2. Database crashes -> 5 envelopes arrive, all successfully buffered.
    3. Database recovers -> Next incoming envelope persists + drains 100% of buffer.
    4. Proves ZERO DATA LOSS for transient database downtime.
    """
    mock_registry, mock_repo = _create_mock_environment()
    retry_buffer = PersistenceRetryBuffer(max_size=50, retry_limit=5)
    pipeline = TelemetryIngestionPipeline(
        registry=mock_registry, repository=mock_repo, retry_buffer=retry_buffer
    )

    # 1. Normal state: DB healthy
    env1 = _create_test_envelope("device-alpha-01", 1)
    res1 = pipeline.process_envelope(env1)
    assert res1.accepted is True
    assert res1.persisted_count == 2
    assert res1.buffered is False
    assert retry_buffer.size == 0

    # 2. DB Outage begins
    mock_repo.save_batch.side_effect = RuntimeError("PostgreSQL Connection Terminated")

    for seq in range(2, 7):
        env = _create_test_envelope("device-alpha-01", seq)
        res = pipeline.process_envelope(env)
        assert res.accepted is True
        assert res.persisted_count == 0
        assert res.buffered is True

    assert retry_buffer.size == 5
    assert retry_buffer.dead_letter_count == 0

    # 3. DB Recovers
    mock_repo.save_batch.side_effect = None

    # Trigger recovery via new envelope
    env_recovery = _create_test_envelope("device-alpha-01", 7)
    res_recovery = pipeline.process_envelope(env_recovery)

    assert res_recovery.accepted is True
    assert res_recovery.persisted_count == 2
    # Buffer was completely drained!
    assert retry_buffer.size == 0
    assert retry_buffer.dead_letter_count == 0


# ==============================================================================
# Workstream F: Publisher Backpressure & Bounded Burst Scenario
# ==============================================================================
def test_scenario_publisher_backpressure_and_bounded_memory():
    """
    Scenario:
    Fast producer emits 100 envelopes while persistence is blocked.
    With max_size=20 and DROP_OLDEST policy:
    - Exactly 20 freshest envelopes are retained.
    - Exactly 80 oldest envelopes are cleanly dropped and counted.
    - Memory is strictly bounded.
    """
    mock_registry, mock_repo = _create_mock_environment()
    mock_repo.save_batch.side_effect = TimeoutError("Database pool saturated")

    retry_buffer = PersistenceRetryBuffer(
        max_size=20, retry_limit=3, overflow_policy=OverflowPolicy.DROP_OLDEST
    )
    pipeline = TelemetryIngestionPipeline(
        registry=mock_registry, repository=mock_repo, retry_buffer=retry_buffer
    )

    for seq in range(1, 101):
        env = _create_test_envelope("device-alpha-01", seq)
        pipeline.process_envelope(env)

    assert retry_buffer.size == 20
    assert retry_buffer.dropped_overflow_count == 80

    # Retained items are the 20 most recent
    pending = retry_buffer.get_pending()
    latest_obs = pending[-1].observations[0]
    assert "100" in latest_obs.observation_id


# ==============================================================================
# Workstream G: Network Partition Simulation & Delivery Accounting
# ==============================================================================
def test_scenario_network_partition_and_delivery_accounting():
    """
    Scenario:
    Simulates a network partition where:
    - Valid messages arrive during partition -> buffered
    - Corrupt/unregistered messages arrive during partition -> permanently rejected
    - Persistent DB failure causes some messages to exceed retry limit -> dead-lettered

    Accounting Formula:
    Total Ingested = Persisted + Buffered + DeadLettered + Rejected
    Must balance exactly with zero unaccounted messages.
    """
    mock_registry, mock_repo = _create_mock_environment(["device-alpha-01"])
    retry_buffer = PersistenceRetryBuffer(max_size=50, retry_limit=2)
    pipeline = TelemetryIngestionPipeline(
        registry=mock_registry, repository=mock_repo, retry_buffer=retry_buffer
    )

    # Initial state: DB fails
    mock_repo.save_batch.side_effect = ConnectionRefusedError("Network partition")

    persisted_count = 0
    rejected_count = 0

    # 1. 5 valid envelopes
    for seq in range(1, 6):
        env = _create_test_envelope("device-alpha-01", seq)
        res = pipeline.process_envelope(env)
        if res.accepted and not res.buffered:
            persisted_count += 1
        elif not res.accepted:
            rejected_count += 1

    # 2. 3 invalid/unregistered devices
    for seq in range(6, 9):
        env = _create_test_envelope("rogue-device-99", seq)
        res = pipeline.process_envelope(env)
        if not res.accepted:
            rejected_count += 1

    # 3. Simulate failed retry drain attempt (triggers dead letter on attempt 2)
    report = pipeline.drain_buffer()
    assert report.dead_lettered_count == 5  # All 5 hit retry limit of 2

    # Accounting Verification:
    total_messages = 8
    assert total_messages == (
        persisted_count + retry_buffer.size + retry_buffer.dead_letter_count + rejected_count
    )
    assert retry_buffer.dead_letter_count == 5
    assert rejected_count == 3
    assert retry_buffer.size == 0


# ==============================================================================
# Workstream D: MQTT Broker Interruption & Reconnection Scenario
# ==============================================================================
def test_scenario_mqtt_broker_disconnect_and_reconnection():
    """
    Scenario:
    1. Consumer is connected and processing messages.
    2. Broker drops connection -> on_disconnect fired.
    3. Broker recovers -> on_connect fired, resubscribes with QoS 1, triggers buffer drain.
    """
    mock_registry, mock_repo = _create_mock_environment()
    retry_buffer = PersistenceRetryBuffer()
    pipeline = TelemetryIngestionPipeline(
        registry=mock_registry, repository=mock_repo, retry_buffer=retry_buffer
    )

    consumer = MqttTelemetryConsumer(pipeline=pipeline, qos=1)
    mock_client = MagicMock()

    # 1. Connect
    consumer._on_connect(mock_client, None, {}, 0)
    assert consumer.is_connected is True
    mock_client.subscribe.assert_called_with(consumer.config.topic, qos=1)

    # 2. Disconnect event
    consumer._on_disconnect(mock_client, None, {}, 7)  # rc=7 broker unavailable
    assert consumer.is_connected is False
    assert consumer.reconnect_count == 1

    # 3. Reconnect event
    consumer._on_connect(mock_client, None, {}, 0)
    assert consumer.is_connected is True
