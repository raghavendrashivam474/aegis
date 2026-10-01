"""
Aegis Telemetry Ingestion Pipeline.

Bridges incoming TelemetryEnvelope contracts with Device Registry validation,
historical persistence ports, and bounded transient retry buffering.
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

from .buffer import PersistenceRetryBuffer

logger = logging.getLogger(__name__)


class TelemetryValidationError(Exception):
    """Raised when an incoming envelope fails device identity or sensor validation."""


@dataclass
class IngestionResult:
    """Outcome of processing an individual TelemetryEnvelope."""

    accepted: bool
    persisted_count: int
    buffered: bool = False
    dead_lettered: bool = False
    reason: str | None = None


@dataclass
class DrainReport:
    """Summary of draining buffered telemetry items upon recovery."""

    attempted_count: int
    persisted_count: int
    dead_lettered_count: int
    remaining_buffer_size: int


class TelemetryIngestionPipeline:
    """
    Validates device registration, verifies sensor associations,
    and coordinates persistence and transient recovery for TelemetryEnvelopes.
    """

    def __init__(
        self,
        registry: DeviceRegistry,
        repository: TelemetryRepository,
        stream_sink: Path | None = None,
        retry_buffer: PersistenceRetryBuffer | None = None,
        enable_buffer: bool = True,
    ) -> None:
        self.registry = registry
        self.repository = repository
        self.stream_sink = stream_sink
        self.retry_buffer = retry_buffer or (PersistenceRetryBuffer() if enable_buffer else None)

    def process_envelope(self, envelope: TelemetryEnvelope) -> IngestionResult:
        """
        Execute validation and persistence for an incoming envelope.

        Enforces:
        1. Device existence in DeviceRegistry (FR-S5-04, FR-S5-05) — PERMANENT REJECTION IF MISSING
        2. Device operational status == ACTIVE (FR-S5-04) — PERMANENT REJECTION IF INACTIVE
        3. Sensor ownership validation (FR-S5-06) — PERMANENT REJECTION IF MISMATCH
        4. Atomic persistence through TelemetryRepository (FR-S5-01) with fallback buffering
        5. Optional legacy JSONL stream mirror for backward compatibility (FR-S5-10)
        """
        device_id = envelope.source_device_id

        # 1. Validate device registration (Permanent Failure: Never buffered)
        if not self.registry.is_registered(device_id):
            msg = f"Unknown device '{device_id}' rejected. Telemetry quarantined."
            logger.warning(msg)
            return IngestionResult(accepted=False, persisted_count=0, buffered=False, reason=msg)

        # 2. Validate device status (Permanent Failure: Never buffered)
        device = self.registry.get_device(device_id)
        if device.status != EntityStatus.ACTIVE:
            msg = f"Device '{device_id}' is inactive/disabled. Telemetry rejected."
            logger.warning(msg)
            return IngestionResult(accepted=False, persisted_count=0, buffered=False, reason=msg)

        # 3. Validate sensor ownership (Permanent Failure: Never buffered)
        domain_observations: list[Observation] = []
        for payload in envelope.observations:
            if not self.registry.validate_sensor_association(device_id, payload.sensor_id):
                msg = (
                    f"Sensor '{payload.sensor_id}' is not associated with device '{device_id}'. "
                    "Envelope rejected."
                )
                logger.warning(msg)
                return IngestionResult(
                    accepted=False, persisted_count=0, buffered=False, reason=msg
                )

            # Map to domain Observation entity
            domain_obs = ObservationMapper.to_domain(payload, device_id=device_id)
            domain_observations.append(domain_obs)

        # 4. Persistence attempt (Transient Failures: Buffered if buffer enabled)
        try:
            self.repository.save_batch(domain_observations)
        except Exception as err:
            msg = f"Persistence failure: {err}"
            logger.warning("PERSISTENCE_FAILED: %s", msg)

            if self.retry_buffer is not None:
                buffered = self.retry_buffer.push(
                    envelope=envelope,
                    observations=domain_observations,
                    error_msg=str(err),
                )
                return IngestionResult(
                    accepted=True,
                    persisted_count=0,
                    buffered=buffered,
                    reason=f"Buffered due to persistence failure: {err}",
                )
            else:
                return IngestionResult(
                    accepted=False,
                    persisted_count=0,
                    buffered=False,
                    reason=msg,
                )

        # If persistence succeeded, opportunistically drain any previously buffered items
        if self.retry_buffer and self.retry_buffer.size > 0:
            self.drain_buffer()

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
            buffered=False,
        )

    def drain_buffer(self) -> DrainReport:
        """
        Attempt to persist all buffered telemetry backlog.
        Called on database recovery or opportunistically after successful writes.
        """
        if not self.retry_buffer or self.retry_buffer.size == 0:
            return DrainReport(0, 0, 0, 0)

        pending_items = self.retry_buffer.get_pending()
        attempted = len(pending_items)
        persisted = 0
        dead_lettered = 0

        for item in pending_items:
            try:
                self.repository.save_batch(item.observations)
                self.retry_buffer.remove(item)
                persisted += 1
                logger.info(
                    "BUFFER_DRAINED: Successfully recovered %d observations for device '%s'",
                    len(item.observations),
                    item.envelope.source_device_id,
                )
            except Exception as err:
                dl = self.retry_buffer.record_retry_failure(item, str(err))
                if dl:
                    dead_lettered += 1

        return DrainReport(
            attempted_count=attempted,
            persisted_count=persisted,
            dead_lettered_count=dead_lettered,
            remaining_buffer_size=self.retry_buffer.size,
        )
