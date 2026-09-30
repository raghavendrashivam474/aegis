"""
Aegis Contract Mappers.

Provides formal bi-directional translation between domain entities
and technology-neutral serialization contracts.
"""

from datetime import UTC, datetime

from domain.entities import Observation, QualityFlag

from .models import ObservationPayload


class ObservationMapper:
    """Translates between domain.Observation and contracts.ObservationPayload."""

    @staticmethod
    def to_contract(observation: Observation) -> ObservationPayload:
        """Map a pure domain Observation to a serializable ObservationPayload contract."""
        # Ensure timestamp is formatted to ISO-8601 UTC string
        ts = observation.timestamp
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=UTC)
        timestamp_iso = ts.isoformat()

        # Metadata can carry device_id context if needed
        metadata = dict(observation.metadata)
        if observation.device_id:
            metadata["device_id"] = observation.device_id

        return ObservationPayload(
            observation_id=observation.observation_id,
            sensor_id=observation.sensor_id,
            timestamp_iso=timestamp_iso,
            value=observation.value,
            unit=observation.unit,
            quality=observation.quality.value,
            metadata=metadata,
        )

    @staticmethod
    def to_domain(payload: ObservationPayload, device_id: str | None = None) -> Observation:
        """
        Map an incoming ObservationPayload contract into a domain Observation entity.

        Extracts device_id from payload metadata or explicit argument.
        """
        effective_device_id = device_id or payload.metadata.get("device_id", "")
        # Parse ISO timestamp
        try:
            timestamp = datetime.fromisoformat(payload.timestamp_iso)
        except (ValueError, TypeError):
            timestamp = datetime.now(UTC)

        # Parse QualityFlag safely with fallback to GOOD
        try:
            quality = QualityFlag(payload.quality.upper())
        except (ValueError, KeyError, AttributeError):
            quality = QualityFlag.GOOD

        # Clean metadata if device_id was injected
        clean_metadata = {k: v for k, v in payload.metadata.items() if k != "device_id"}

        return Observation(
            observation_id=payload.observation_id,
            device_id=effective_device_id,
            sensor_id=payload.sensor_id,
            timestamp=timestamp,
            value=payload.value,
            unit=payload.unit,
            quality=quality,
            metadata=clean_metadata,
        )
