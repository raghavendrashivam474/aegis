"""Tests validating interchange contracts serialization and schema versions."""

import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "packages"))

from contracts import (
    CURRENT_SCHEMA_VERSION,
    DeviceIdentity,
    ObservationPayload,
    TelemetryEnvelope,
)


def test_schema_version_is_current():
    assert CURRENT_SCHEMA_VERSION == "v1"


def test_device_identity_serialization():
    identity = DeviceIdentity(
        device_id="esp32-alpha",
        device_type="esp32_wroom",
        firmware_version="1.2.0",
        hardware_revision="v2.1",
    )
    d = identity.to_dict()
    assert d["device_id"] == "esp32-alpha"
    reconstructed = DeviceIdentity.from_dict(d)
    assert reconstructed == identity


def test_telemetry_envelope_roundtrip():
    now_iso = datetime.now(UTC).isoformat()
    obs1 = ObservationPayload(
        observation_id="obs-1",
        sensor_id="temp-01",
        timestamp_iso=now_iso,
        value=85.2,
        unit="celsius",
    )
    obs2 = ObservationPayload(
        observation_id="obs-2",
        sensor_id="press-01",
        timestamp_iso=now_iso,
        value=3.4,
        unit="bar",
    )
    envelope = TelemetryEnvelope(
        schema_version="v1",
        source_device_id="esp32-alpha",
        sent_at_iso=now_iso,
        observations=[obs1, obs2],
        metadata={"site": "Plant-A"},
    )

    payload_dict = envelope.to_dict()
    assert payload_dict["schema_version"] == "v1"
    assert len(payload_dict["observations"]) == 2

    restored = TelemetryEnvelope.from_dict(payload_dict)
    assert restored.source_device_id == "esp32-alpha"
    assert len(restored.observations) == 2
    assert restored.observations[0].value == 85.2
    assert restored.observations[1].unit == "bar"
