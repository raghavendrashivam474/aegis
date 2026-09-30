"""
Aegis Telemetry Ingestion Pipeline.

Bridges incoming TelemetryEnvelope contracts with Device Registry validation
and historical persistence ports.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

from contracts import ObservationMapper, TelemetryEnvelope
from domain import (
    DeviceRegistry,
    EntityStatus,
    Observation,
    TelemetryRepository,
)

logger = logging.getLogger(__name__)


class TelemetryValidationError(Exception):
    """Raised when an incoming envelope fails device identity or sensor validation."""


@dataclass
class IngestionResult:
    """Outcome of processing an individual TelemetryEnvelope."""

    accepted: bool
    persisted_count: int
    reason: str | None = None


class TelemetryIngestionPipeline:
    """
    Validates device registration, verifies sensor associations,
    and coordinates persistence of incoming TelemetryEnvelope contracts.
    """

    def __init__(
        self,
        registry: DeviceRegistry,
        repository: TelemetryRepository,
        stream_sink: Path | None = None,
    ) -> None:
        self.registry = registry
        self.repository = repository
        self.stream_sink = stream_sink

    def process_envelope(self, envelope: TelemetryEnvelope) -> IngestionResult:
        """
        Execute validation and persistence for an incoming envelope.

        Enforces:
        1. Device existence in DeviceRegistry (FR-S5-04, FR-S5-05)
        2. Device operational status == ACTIVE (FR-S5-04)
        3. Sensor ownership validation for every observation (FR-S5-06)
        4. Atomic persistence through TelemetryRepository (FR-S5-01)
        5. Optional legacy JSONL stream mirror for backward compatibility (FR-S5-10)
        """
        device_id = envelope.source_device_id

        # 1. Validate device registration
        if not self.registry.is_registered(device_id):
            msg = f"Unknown device '{device_id}' rejected. Telemetry quarantined."
            logger.warning(msg)
            return IngestionResult(accepted=False, persisted_count=0, reason=msg)

        # 2. Validate device status (must be ACTIVE)
        device = self.registry.get_device(device_id)
        if device.status != EntityStatus.ACTIVE:
            msg = f"Device '{device_id}' is inactive/disabled. Telemetry rejected."
            logger.warning(msg)
            return IngestionResult(accepted=False, persisted_count=0, reason=msg)

        # 3. Validate sensor ownership for all observations
        domain_observations: list[Observation] = []
        for payload in envelope.observations:
            if not self.registry.validate_sensor_association(device_id, payload.sensor_id):
                msg = (
                    f"Sensor '{payload.sensor_id}' is not associated with device '{device_id}'. "
                    "Envelope rejected."
                )
                logger.warning(msg)
                return IngestionResult(accepted=False, persisted_count=0, reason=msg)

            # Map to domain Observation entity
            domain_obs = ObservationMapper.to_domain(payload, device_id=device_id)
            domain_observations.append(domain_obs)

        # 4. Atomic persistence
        try:
            self.repository.save_batch(domain_observations)
        except Exception as err:
            msg = f"Persistence failure: {err}"
            logger.error(msg)
            return IngestionResult(accepted=False, persisted_count=0, reason=msg)

        # 5. Mirror to legacy JSONL stream if sink configured
        if self.stream_sink:
            try:
                self.stream_sink.parent.mkdir(parents=True, exist_ok=True)
                with self.stream_sink.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(envelope.to_dict()) + "\n")
            except OSError as err:
                logger.warning("Failed to mirror to legacy stream sink: %s", err)

        return IngestionResult(
            accepted=True,
            persisted_count=len(domain_observations),
        )
