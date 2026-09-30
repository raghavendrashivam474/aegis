# ruff: noqa: E402, S101, PLR2004
"""Tests for Aegis MQTT Ingestion Bridge."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# Ensure project root and packages/ are importable
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "packages") not in sys.path:
    sys.path.insert(0, str(ROOT / "packages"))

from contracts import CURRENT_SCHEMA_VERSION, TelemetryEnvelope

from apps.ingestion import (
    IngestionConfig,
    MqttTelemetryConsumer,
    TelemetryDecodeError,
    TelemetryDecoder,
)


@pytest.fixture
def valid_envelope_dict() -> dict:
    """Return a valid serialized TelemetryEnvelope dictionary."""
    return {
        "schema_version": CURRENT_SCHEMA_VERSION,
        "source_device_id": "device-esp32-99",
        "sent_at_iso": "2026-03-01T12:00:00+00:00",
        "observations": [
            {
                "observation_id": "obs-temp-01",
                "sensor_id": "sensor-temp-01",
                "timestamp_iso": "2026-03-01T12:00:00+00:00",
                "value": 24.5,
                "unit": "celsius",
                "quality": "GOOD",
                "metadata": {"test": "true"},
            }
        ],
        "metadata": {"source": "physical"},
    }


# ------------------------------------------------------------------
# TelemetryDecoder Tests
# ------------------------------------------------------------------


def test_decoder_valid_payload(valid_envelope_dict):
    """Verify that a valid dictionary or string decodes to a TelemetryEnvelope."""
    json_bytes = json.dumps(valid_envelope_dict).encode("utf-8")
    envelope = TelemetryDecoder.decode(json_bytes)

    assert envelope.schema_version == CURRENT_SCHEMA_VERSION
    assert envelope.source_device_id == "device-esp32-99"
    assert len(envelope.observations) == 1
    assert envelope.observations[0].value == 24.5
    assert envelope.observations[0].unit == "celsius"


def test_decoder_invalid_utf8():
    """Verify decoder rejects raw bytes that aren't valid UTF-8."""
    bad_bytes = b"\xff\xfe\xfd\xfc"
    with pytest.raises(TelemetryDecodeError, match="Payload is not valid UTF-8"):
        TelemetryDecoder.decode(bad_bytes)


@pytest.mark.parametrize(
    "empty_val",
    ["", "   ", None, b"", b"   "],
)
def test_decoder_empty_payload(empty_val):
    """Verify decoder rejects empty strings or empty byte arrays."""
    with pytest.raises(TelemetryDecodeError, match="Empty payload received"):
        TelemetryDecoder.decode(empty_val)


def test_decoder_malformed_json():
    """Verify decoder rejects syntax-invalid JSON."""
    bad_json = '{"schema_version": "v1", "source_device_id": }'  # Missing value
    with pytest.raises(TelemetryDecodeError, match="Invalid JSON string"):
        TelemetryDecoder.decode(bad_json)


def test_decoder_not_an_object():
    """Verify decoder rejects JSON lists or primitives instead of an object."""
    bad_json = '[{"schema_version": "v1"}]'
    with pytest.raises(TelemetryDecodeError, match="Payload root must be a JSON object"):
        TelemetryDecoder.decode(bad_json)


def test_decoder_invalid_contract_schema(valid_envelope_dict):
    """Verify decoder rejects JSON objects missing mandatory envelope fields."""
    invalid_dict = valid_envelope_dict.copy()
    del invalid_dict["source_device_id"]  # Mandatory contract field missing

    with pytest.raises(TelemetryDecodeError, match="Failed contract validation"):
        TelemetryDecoder.decode(json.dumps(invalid_dict))


# ------------------------------------------------------------------
# MqttTelemetryConsumer Pipeline Tests
# ------------------------------------------------------------------


def test_consumer_raw_message_success(tmp_path, valid_envelope_dict):
    """Verify consumer successfully decodes and processes valid payload."""
    sink_file = tmp_path / "stream.jsonl"
    config = IngestionConfig(stream_sink=sink_file)

    envelopes_captured = []

    def capture_envelope(env: TelemetryEnvelope):
        envelopes_captured.append(env)
        # Call default sink handler mock inside custom handler
        with sink_file.open("a", encoding="utf-8") as f:
            f.write(json.dumps(env.to_dict()) + "\n")

    consumer = MqttTelemetryConsumer(config=config, on_envelope=capture_envelope)

    payload = json.dumps(valid_envelope_dict)
    envelope = consumer.process_raw_message(payload, topic="aegis/telemetry/device-esp32-99")

    # Assert contract parsed
    assert envelope is not None
    assert consumer.received_count == 1
    assert consumer.invalid_count == 0
    assert len(envelopes_captured) == 1

    # Assert payload was persisted to file path successfully
    assert sink_file.exists()
    lines = sink_file.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    written_dict = json.loads(lines[0])
    assert written_dict["source_device_id"] == "device-esp32-99"


def test_consumer_raw_message_rejected(tmp_path):
    """Verify consumer gracefully drops invalid payload without crashing."""
    sink_file = tmp_path / "stream.jsonl"
    config = IngestionConfig(stream_sink=sink_file)

    consumer = MqttTelemetryConsumer(config=config)
    bad_payload = "{invalid-json}"

    envelope = consumer.process_raw_message(bad_payload, topic="aegis/telemetry/device-esp32-99")

    assert envelope is None
    assert consumer.received_count == 0
    assert consumer.invalid_count == 1
    assert not sink_file.exists()  # Nothing written


# ------------------------------------------------------------------
# Architecture Boundary Tests
# ------------------------------------------------------------------


def test_domain_boundary_has_no_mqtt_imports():
    """Verify packages/domain contains absolutely zero references to MQTT or paho."""
    domain_dir = Path(__file__).resolve().parents[1] / "packages" / "domain"
    assert domain_dir.exists()

    for py_file in domain_dir.glob("**/*.py"):
        content = py_file.read_text(encoding="utf-8")
        assert "paho" not in content.lower(), (
            f"Infrastructure leaking: 'paho' import found in domain file {py_file.name}"
        )
        assert "mqtt" not in content.lower(), (
            f"Infrastructure leaking: 'mqtt' import found in domain file {py_file.name}"
        )
