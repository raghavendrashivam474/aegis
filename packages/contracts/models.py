"""
Aegis Data Contracts (Schema Version: v1).

These contracts govern data interchange between external edge nodes/simulators
and the Aegis core boundary.
"""

import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any

CURRENT_SCHEMA_VERSION = "v1"


@dataclass(frozen=True)
class DeviceIdentity:
    """Identity contract for physical edge nodes or virtual simulators."""

    device_id: str
    device_type: str  # e.g., 'esp32_wroom', 'virtual_pump_sim'
    firmware_version: str = "1.0.0"
    hardware_revision: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DeviceIdentity":
        return cls(
            device_id=str(data["device_id"]),
            device_type=str(data["device_type"]),
            firmware_version=str(data.get("firmware_version", "1.0.0")),
            hardware_revision=data.get("hardware_revision"),
        )


@dataclass(frozen=True)
class SensorIdentity:
    """Identity contract for a sensor attached to a device."""

    sensor_id: str
    measurement_type: str  # e.g., 'temperature', 'vibration_rms'
    unit: str  # e.g., 'celsius', 'mm_s', 'bar'

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SensorIdentity":
        return cls(
            sensor_id=str(data["sensor_id"]),
            measurement_type=str(data["measurement_type"]),
            unit=str(data["unit"]),
        )


@dataclass(frozen=True)
class ObservationPayload:
    """Contract representing a single recorded measurement."""

    observation_id: str
    sensor_id: str
    timestamp_iso: str  # ISO 8601 UTC timestamp string
    value: float
    unit: str
    quality: str = "GOOD"  # GOOD, UNCERTAIN, BAD, CALIBRATION
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ObservationPayload":
        return cls(
            observation_id=str(data.get("observation_id", uuid.uuid4().hex)),
            sensor_id=str(data["sensor_id"]),
            timestamp_iso=str(data["timestamp_iso"]),
            value=float(data["value"]),
            unit=str(data["unit"]),
            quality=str(data.get("quality", "GOOD")),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass(frozen=True)
class TelemetryEnvelope:
    """
    Standard transport envelope for passing batch telemetry into Aegis.

    Independent of whether delivery was MQTT, HTTP, or direct memory IPC.
    """

    schema_version: str
    source_device_id: str
    sent_at_iso: str
    observations: list[ObservationPayload]
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "source_device_id": self.source_device_id,
            "sent_at_iso": self.sent_at_iso,
            "observations": [obs.to_dict() for obs in self.observations],
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TelemetryEnvelope":
        observations = [ObservationPayload.from_dict(obs) for obs in data.get("observations", [])]
        return cls(
            schema_version=str(data.get("schema_version", CURRENT_SCHEMA_VERSION)),
            source_device_id=str(data["source_device_id"]),
            sent_at_iso=str(data.get("sent_at_iso", datetime.now(UTC).isoformat())),
            observations=observations,
            metadata=dict(data.get("metadata", {})),
        )
