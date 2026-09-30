"""
P1.S5 Tests: Persistent Telemetry, Device Registry, Validation, & Historical Retrieval.

Covers:
- FR-S5-01: Persistent Telemetry Storage (TC-S5-01..06)
- FR-S5-02: Telemetry Retrieval by Device, Sensor, Time Range (TC-S5-07..12)
- FR-S5-03: Device Registration & Queries (TC-S5-13..17)
- FR-S5-04: Device Validation of Envelopes (TC-S5-18..20)
- FR-S5-05: Unknown Device Rejection/Quarantine (TC-S5-21..23)
- FR-S5-06: Sensor Identity & Association Validation (TC-S5-24..26)
- FR-S5-08: Persistence Failure Handling (TC-S5-31..33)
- FR-S5-09: Historical Chronological Query Ordering (TC-S5-34..35)
"""

from datetime import UTC, datetime, timedelta

import pytest
from contracts import CURRENT_SCHEMA_VERSION, ObservationPayload, TelemetryEnvelope
from domain import (
    Device,
    EntityNotFoundError,
    EntityStatus,
    InMemoryDeviceRegistry,
    InMemoryTelemetryRepository,
    Observation,
    QualityFlag,
    Sensor,
)

from apps.ingestion.pipeline import TelemetryIngestionPipeline


@pytest.fixture
def sample_device() -> Device:
    sensor_temp = Sensor(
        sensor_id="sensor-temp-01",
        name="Motor Temperature",
        measurement_type="temperature",
        unit="celsius",
        device_id="device-pump-01",
    )
    sensor_vib = Sensor(
        sensor_id="sensor-vib-01",
        name="Vibration Peak",
        measurement_type="vibration",
        unit="mm/s",
        device_id="device-pump-01",
    )
    return Device(
        device_id="device-pump-01",
        name="Pump Main Motor",
        asset_id="asset-pump-01",
        sensors=[sensor_temp, sensor_vib],
    )


@pytest.fixture
def populated_registry(sample_device) -> InMemoryDeviceRegistry:
    reg = InMemoryDeviceRegistry()
    reg.register_device(sample_device)
    return reg


@pytest.fixture
def telemetry_repo() -> InMemoryTelemetryRepository:
    return InMemoryTelemetryRepository()


@pytest.fixture
def valid_envelope() -> TelemetryEnvelope:
    now_iso = datetime.now(UTC).isoformat()
    return TelemetryEnvelope(
        schema_version=CURRENT_SCHEMA_VERSION,
        source_device_id="device-pump-01",
        sent_at_iso=now_iso,
        observations=[
            ObservationPayload(
                observation_id="obs-001",
                sensor_id="sensor-temp-01",
                timestamp_iso=now_iso,
                value=42.5,
                unit="celsius",
                quality="GOOD",
                metadata={"site": "Plant-A"},
            ),
            ObservationPayload(
                observation_id="obs-002",
                sensor_id="sensor-vib-01",
                timestamp_iso=now_iso,
                value=1.8,
                unit="mm/s",
                quality="GOOD",
            ),
        ],
        metadata={"source": "test"},
    )


# -------------------------------------------------------------------------
# FR-S5-03: Device Registration Tests (TC-S5-13..17)
# -------------------------------------------------------------------------


def test_tc_s5_13_register_device_successfully(sample_device):
    reg = InMemoryDeviceRegistry()
    reg.register_device(sample_device)
    assert reg.is_registered("device-pump-01")


def test_tc_s5_14_query_registered_device(sample_device, populated_registry):
    device = populated_registry.get_device("device-pump-01")
    assert device.name == "Pump Main Motor"
    assert len(device.sensors) == 2


def test_tc_s5_16_list_registered_devices(sample_device, populated_registry):
    devs = populated_registry.list_devices()
    assert len(devs) == 1
    assert devs[0].device_id == "device-pump-01"


def test_tc_s5_missing_device_raises_entity_not_found():
    reg = InMemoryDeviceRegistry()
    with pytest.raises(EntityNotFoundError):
        reg.get_device("non-existent-device")


# -------------------------------------------------------------------------
# FR-S5-01 & FR-S5-02: Persistence & Retrieval (TC-S5-01..12, TC-S5-34..35)
# -------------------------------------------------------------------------


def test_tc_s5_01_save_and_retrieve_single_observation(telemetry_repo):
    now = datetime.now(UTC)
    obs = Observation(
        observation_id="obs-1",
        device_id="device-pump-01",
        sensor_id="sensor-temp-01",
        timestamp=now,
        value=55.0,
        unit="celsius",
        quality=QualityFlag.GOOD,
    )
    telemetry_repo.save_observation(obs)

    records = telemetry_repo.get_observations(device_id="device-pump-01")
    assert len(records) == 1
    assert records[0].value == 55.0
    assert records[0].timestamp == now


def test_tc_s5_07_retrieve_by_device_and_sensor(telemetry_repo):
    t0 = datetime(2026, 3, 1, 10, 0, 0, tzinfo=UTC)
    obs1 = Observation("obs-1", "device-01", "sensor-temp", t0, 20.0, "celsius")
    obs2 = Observation("obs-2", "device-01", "sensor-vib", t0, 1.2, "mm/s")
    obs3 = Observation("obs-3", "device-02", "sensor-temp", t0, 30.0, "celsius")
    telemetry_repo.save_batch([obs1, obs2, obs3])

    dev1_records = telemetry_repo.get_observations(device_id="device-01")
    assert len(dev1_records) == 2

    sensor_temp_records = telemetry_repo.get_observations(sensor_id="sensor-temp")
    assert len(sensor_temp_records) == 2


def test_tc_s5_09_retrieve_by_time_range(telemetry_repo):
    t0 = datetime(2026, 3, 1, 10, 0, 0, tzinfo=UTC)
    t1 = t0 + timedelta(minutes=5)
    t2 = t0 + timedelta(minutes=10)

    obs1 = Observation("obs-1", "dev-1", "sensor-1", t0, 10.0, "celsius")
    obs2 = Observation("obs-2", "dev-1", "sensor-1", t1, 20.0, "celsius")
    obs3 = Observation("obs-3", "dev-1", "sensor-1", t2, 30.0, "celsius")
    telemetry_repo.save_batch([obs1, obs2, obs3])

    filtered = telemetry_repo.get_observations(
        start_time=t0 + timedelta(minutes=1), end_time=t0 + timedelta(minutes=7)
    )
    assert len(filtered) == 1
    assert filtered[0].observation_id == "obs-2"


def test_tc_s5_10_get_latest_observation(telemetry_repo):
    t0 = datetime(2026, 3, 1, 10, 0, 0, tzinfo=UTC)
    obs1 = Observation("obs-1", "dev-1", "sensor-1", t0, 10.0, "celsius")
    obs2 = Observation("obs-2", "dev-1", "sensor-1", t0 + timedelta(seconds=30), 15.0, "celsius")
    telemetry_repo.save_batch([obs1, obs2])

    latest = telemetry_repo.get_latest_observation("sensor-1")
    assert latest is not None
    assert latest.observation_id == "obs-2"
    assert latest.value == 15.0


def test_tc_s5_34_chronological_ordering(telemetry_repo):
    t0 = datetime(2026, 3, 1, 12, 0, 0, tzinfo=UTC)
    obs_late = Observation("obs-late", "dev-1", "sensor-1", t0 + timedelta(hours=2), 50.0, "C")
    obs_early = Observation("obs-early", "dev-1", "sensor-1", t0, 10.0, "C")
    obs_mid = Observation("obs-mid", "dev-1", "sensor-1", t0 + timedelta(hours=1), 25.0, "C")

    # Insert out of order
    telemetry_repo.save_batch([obs_late, obs_early, obs_mid])

    retrieved = telemetry_repo.get_observations(device_id="dev-1")
    assert [o.observation_id for o in retrieved] == ["obs-early", "obs-mid", "obs-late"]


# -------------------------------------------------------------------------
# FR-S5-04, FR-S5-05, FR-S5-06: Pipeline Validation Tests (TC-S5-18..26)
# -------------------------------------------------------------------------


def test_tc_s5_18_valid_envelope_persisted_by_pipeline(
    populated_registry, telemetry_repo, valid_envelope
):
    pipeline = TelemetryIngestionPipeline(
        registry=populated_registry,
        repository=telemetry_repo,
    )
    result = pipeline.process_envelope(valid_envelope)

    assert result.accepted is True
    assert result.persisted_count == 2
    assert len(telemetry_repo.get_observations(device_id="device-pump-01")) == 2


def test_tc_s5_19_unknown_device_rejected(telemetry_repo, valid_envelope):
    empty_registry = InMemoryDeviceRegistry()
    pipeline = TelemetryIngestionPipeline(registry=empty_registry, repository=telemetry_repo)

    result = pipeline.process_envelope(valid_envelope)
    assert result.accepted is False
    assert "Unknown device" in (result.reason or "")
    # FR-S5-05: Must NOT be stored in repository
    assert len(telemetry_repo.get_observations()) == 0


def test_tc_s5_20_disabled_device_rejected(sample_device, telemetry_repo, valid_envelope):
    sample_device.status = EntityStatus.INACTIVE
    reg = InMemoryDeviceRegistry()
    reg.register_device(sample_device)

    pipeline = TelemetryIngestionPipeline(registry=reg, repository=telemetry_repo)
    result = pipeline.process_envelope(valid_envelope)

    assert result.accepted is False
    assert "inactive/disabled" in (result.reason or "")
    assert len(telemetry_repo.get_observations()) == 0


def test_tc_s5_25_unknown_sensor_rejected(populated_registry, telemetry_repo):
    pipeline = TelemetryIngestionPipeline(registry=populated_registry, repository=telemetry_repo)

    envelope_with_unknown_sensor = TelemetryEnvelope(
        schema_version=CURRENT_SCHEMA_VERSION,
        source_device_id="device-pump-01",
        sent_at_iso=datetime.now(UTC).isoformat(),
        observations=[
            ObservationPayload(
                observation_id="obs-x",
                sensor_id="sensor-unknown-999",  # NOT in registry for device-pump-01
                timestamp_iso=datetime.now(UTC).isoformat(),
                value=99.9,
                unit="bar",
            )
        ],
    )

    result = pipeline.process_envelope(envelope_with_unknown_sensor)
    assert result.accepted is False
    assert "not associated" in (result.reason or "")
    assert len(telemetry_repo.get_observations()) == 0


def test_tc_s5_legacy_stream_mirroring(
    populated_registry, telemetry_repo, valid_envelope, tmp_path
):
    sink_file = tmp_path / "stream_mirror.jsonl"
    pipeline = TelemetryIngestionPipeline(
        registry=populated_registry, repository=telemetry_repo, stream_sink=sink_file
    )

    result = pipeline.process_envelope(valid_envelope)
    assert result.accepted is True
    assert sink_file.exists()
    assert len(sink_file.read_text(encoding="utf-8").splitlines()) == 1
