"""
Tests for Aegis Ingestion Reliability, Retry Buffering, and Dead-Letter Semantics (P1.S7).
"""

from datetime import UTC, datetime
from unittest.mock import MagicMock

from contracts import ObservationPayload, TelemetryEnvelope
from domain import (
    Device,
    DeviceRegistry,
    EntityStatus,
    Observation,
    QualityFlag,
    Sensor,
    TelemetryRepository,
)

from apps.ingestion.buffer import (
    OverflowPolicy,
    PersistenceRetryBuffer,
)
from apps.ingestion.pipeline import TelemetryIngestionPipeline


def _build_test_envelope(device_id: str = "dev-01", sensor_id: str = "sen-01") -> TelemetryEnvelope:
    return TelemetryEnvelope(
        schema_version="v1",
        source_device_id=device_id,
        sent_at_iso=datetime.now(UTC).isoformat(),
        observations=[
            ObservationPayload(
                observation_id="obs-001",
                sensor_id=sensor_id,
                timestamp_iso=datetime.now(UTC).isoformat(),
                value=42.0,
                unit="celsius",
                quality="GOOD",
            )
        ],
    )


def test_buffer_push_and_drain_success():
    """Verify items are stored on DB failure and persisted when DB recovers."""
    buffer = PersistenceRetryBuffer(max_size=10, retry_limit=3)
    envelope = _build_test_envelope()
    obs = [
        Observation(
            observation_id="obs-001",
            device_id="dev-01",
            sensor_id="sen-01",
            timestamp=datetime.now(UTC),
            value=42.0,
            unit="celsius",
            quality=QualityFlag.GOOD,
        )
    ]

    assert buffer.push(envelope, obs, error_msg="DB down") is True
    assert buffer.size == 1
    assert buffer.dead_letter_count == 0

    # Mock DB recovery
    mock_repo = MagicMock(spec=TelemetryRepository)
    mock_registry = MagicMock(spec=DeviceRegistry)

    pipeline = TelemetryIngestionPipeline(
        registry=mock_registry,
        repository=mock_repo,
        retry_buffer=buffer,
    )

    report = pipeline.drain_buffer()
    assert report.attempted_count == 1
    assert report.persisted_count == 1
    assert report.remaining_buffer_size == 0
    mock_repo.save_batch.assert_called_once_with(obs)


def test_buffer_dead_letter_on_retry_limit_exhausted():
    """Verify item is moved to dead-letter quarantine after exceeding retry limit."""
    buffer = PersistenceRetryBuffer(max_size=10, retry_limit=2)
    envelope = _build_test_envelope()
    obs = []

    buffer.push(envelope, obs, "First failure")
    item = buffer.get_pending()[0]

    # Attempt 2 (limit reached)
    dl = buffer.record_retry_failure(item, "Second failure")
    assert dl is not None
    assert buffer.size == 0
    assert buffer.dead_letter_count == 1
    assert "Exhausted 2 retry attempts" in dl.reason
    assert dl.envelope.source_device_id == "dev-01"


def test_buffer_overflow_drop_oldest():
    """Verify buffer drops oldest envelope when max_size reached under DROP_OLDEST policy."""
    buffer = PersistenceRetryBuffer(
        max_size=2, retry_limit=3, overflow_policy=OverflowPolicy.DROP_OLDEST
    )

    env1 = _build_test_envelope("dev-1")
    env2 = _build_test_envelope("dev-2")
    env3 = _build_test_envelope("dev-3")

    assert buffer.push(env1, [], "err1") is True
    assert buffer.push(env2, [], "err2") is True
    assert buffer.push(env3, [], "err3") is True

    assert buffer.size == 2
    assert buffer.dropped_overflow_count == 1
    remaining_device_ids = [item.envelope.source_device_id for item in buffer.get_pending()]
    assert remaining_device_ids == ["dev-2", "dev-3"]


def test_buffer_overflow_reject_newest():
    """Verify buffer rejects incoming envelope when max_size reached under REJECT_NEWEST policy."""
    buffer = PersistenceRetryBuffer(
        max_size=2, retry_limit=3, overflow_policy=OverflowPolicy.REJECT_NEWEST
    )

    env1 = _build_test_envelope("dev-1")
    env2 = _build_test_envelope("dev-2")
    env3 = _build_test_envelope("dev-3")

    assert buffer.push(env1, [], "err1") is True
    assert buffer.push(env2, [], "err2") is True
    assert buffer.push(env3, [], "err3") is False

    assert buffer.size == 2
    assert buffer.dropped_overflow_count == 1
    remaining_device_ids = [item.envelope.source_device_id for item in buffer.get_pending()]
    assert remaining_device_ids == ["dev-1", "dev-2"]


def test_pipeline_permanent_rejections_are_never_buffered():
    """Verify unknown devices and sensor mismatches are rejected immediately and NOT buffered."""
    mock_registry = MagicMock(spec=DeviceRegistry)
    mock_repo = MagicMock(spec=TelemetryRepository)
    buffer = PersistenceRetryBuffer()

    pipeline = TelemetryIngestionPipeline(
        registry=mock_registry,
        repository=mock_repo,
        retry_buffer=buffer,
    )

    # 1. Unknown device
    mock_registry.is_registered.return_value = False
    env_unknown = _build_test_envelope("unknown-dev")
    res1 = pipeline.process_envelope(env_unknown)
    assert res1.accepted is False
    assert res1.buffered is False
    assert buffer.size == 0

    # 2. Inactive device
    mock_registry.is_registered.return_value = True
    inactive_device = Device(
        device_id="inactive-dev",
        name="Inactive",
        asset_id="asset-1",
        status=EntityStatus.INACTIVE,
    )
    mock_registry.get_device.return_value = inactive_device
    env_inactive = _build_test_envelope("inactive-dev")
    res2 = pipeline.process_envelope(env_inactive)
    assert res2.accepted is False
    assert res2.buffered is False
    assert buffer.size == 0

    # 3. Sensor mismatch
    active_device = Device(
        device_id="active-dev",
        name="Active",
        asset_id="asset-1",
        sensors=[Sensor("sen-real", "Real", "temp", "celsius", "active-dev")],
        status=EntityStatus.ACTIVE,
    )
    mock_registry.get_device.return_value = active_device
    mock_registry.validate_sensor_association.return_value = False
    env_mismatch = _build_test_envelope("active-dev", "sen-fake")
    res3 = pipeline.process_envelope(env_mismatch)
    assert res3.accepted is False
    assert res3.buffered is False
    assert buffer.size == 0


def test_pipeline_opportunistic_drain_on_recovery():
    """Verify that when a write succeeds after a failure, any backlog is automatically drained."""
    mock_registry = MagicMock(spec=DeviceRegistry)
    mock_registry.is_registered.return_value = True
    mock_registry.get_device.return_value = Device(
        device_id="dev-01",
        name="Dev",
        asset_id="asset-1",
        status=EntityStatus.ACTIVE,
    )
    mock_registry.validate_sensor_association.return_value = True

    mock_repo = MagicMock(spec=TelemetryRepository)
    buffer = PersistenceRetryBuffer()
    pipeline = TelemetryIngestionPipeline(
        registry=mock_registry, repository=mock_repo, retry_buffer=buffer
    )

    # First write: DB fails -> item buffered
    mock_repo.save_batch.side_effect = RuntimeError("DB connection lost")
    env1 = _build_test_envelope("dev-01", "sen-01")
    res1 = pipeline.process_envelope(env1)
    assert res1.accepted is True
    assert res1.buffered is True
    assert buffer.size == 1

    # Second write: DB recovers -> saves current batch + opportunistically drains buffer
    mock_repo.save_batch.side_effect = None
    env2 = _build_test_envelope("dev-01", "sen-01")
    res2 = pipeline.process_envelope(env2)
    assert res2.accepted is True
    assert res2.buffered is False
    assert buffer.size == 0  # Buffered item was drained!
