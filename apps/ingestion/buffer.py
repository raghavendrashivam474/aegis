"""
Aegis Telemetry Persistence Retry Buffer & Dead-Letter Quarantine.

Provides bounded in-memory buffering for transient database downtime,
retry attempt tracking, and dead-letter quarantine for exhausted payloads.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from contracts import TelemetryEnvelope
from domain import Observation

logger = logging.getLogger(__name__)


class OverflowPolicy(StrEnum):
    """Action to take when retry buffer reaches maximum capacity."""

    DROP_OLDEST = "DROP_OLDEST"
    REJECT_NEWEST = "REJECT_NEWEST"


@dataclass
class BufferedTelemetry:
    """Envelope and mapped domain observations awaiting database persistence."""

    envelope: TelemetryEnvelope
    observations: list[Observation]
    attempts: int = 0
    first_attempt_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    last_attempt_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    last_error: str = ""


@dataclass(frozen=True)
class DeadLetterRecord:
    """Quarantined telemetry record that exhausted its maximum retry budget."""

    envelope: TelemetryEnvelope
    observations: list[Observation]
    attempts: int
    reason: str
    quarantined_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        return {
            "device_id": self.envelope.source_device_id,
            "observations_count": len(self.observations),
            "attempts": self.attempts,
            "reason": self.reason,
            "quarantined_at_iso": self.quarantined_at.isoformat(),
            "envelope": self.envelope.to_dict(),
        }


class PersistenceRetryBuffer:
    """
    Thread-safe, bounded buffer for retrying failed database persistence operations.
    """

    def __init__(
        self,
        max_size: int = 1000,
        retry_limit: int = 3,
        overflow_policy: OverflowPolicy = OverflowPolicy.DROP_OLDEST,
    ) -> None:
        self.max_size = max_size
        self.retry_limit = retry_limit
        self.overflow_policy = overflow_policy

        self._lock = threading.Lock()
        self._buffer: list[BufferedTelemetry] = []
        self._dead_letters: list[DeadLetterRecord] = []
        self._dropped_overflow_count: int = 0

    def push(
        self,
        envelope: TelemetryEnvelope,
        observations: list[Observation],
        error_msg: str = "",
    ) -> bool:
        """
        Push a transiently failed observation batch into the retry buffer.

        Returns True if accepted into buffer, False if rejected by overflow policy.
        """
        with self._lock:
            # Check capacity
            if len(self._buffer) >= self.max_size:
                if self.overflow_policy == OverflowPolicy.DROP_OLDEST:
                    dropped = self._buffer.pop(0)
                    self._dropped_overflow_count += 1
                    logger.warning(
                        "BUFFER_OVERFLOW: Dropped oldest envelope for device '%s' (cap=%d)",
                        dropped.envelope.source_device_id,
                        self.max_size,
                    )
                else:
                    self._dropped_overflow_count += 1
                    logger.warning(
                        "BUFFER_OVERFLOW: Rejected newest envelope for device '%s' (cap=%d)",
                        envelope.source_device_id,
                        self.max_size,
                    )
                    return False

            item = BufferedTelemetry(
                envelope=envelope,
                observations=observations,
                attempts=1,
                last_attempt_at=datetime.now(UTC),
                last_error=error_msg,
            )
            self._buffer.append(item)
            logger.info(
                "BUFFERED: Device '%s' (%d observations). Buffer size: %d/%d",
                envelope.source_device_id,
                len(observations),
                len(self._buffer),
                self.max_size,
            )
            return True

    def get_pending(self) -> list[BufferedTelemetry]:
        """Return a snapshot list of all buffered items."""
        with self._lock:
            return list(self._buffer)

    def record_retry_failure(
        self,
        item: BufferedTelemetry,
        error_msg: str,
    ) -> DeadLetterRecord | None:
        """
        Increment attempt count for an item. If retry limit exceeded,
        move item to dead-letter quarantine.
        """
        with self._lock:
            if item not in self._buffer:
                return None

            item.attempts += 1
            item.last_attempt_at = datetime.now(UTC)
            item.last_error = error_msg

            if item.attempts >= self.retry_limit:
                self._buffer.remove(item)
                dl_record = DeadLetterRecord(
                    envelope=item.envelope,
                    observations=item.observations,
                    attempts=item.attempts,
                    reason=f"Exhausted {item.attempts} retry attempts. Last error: {error_msg}",
                )
                self._dead_letters.append(dl_record)
                logger.error(
                    "DEAD_LETTERED: Device '%s' exceeded retry limit (%d). Quarantined.",
                    item.envelope.source_device_id,
                    self.retry_limit,
                )
                return dl_record
            else:
                logger.warning(
                    "RETRY_SCHEDULED: Device '%s' attempt %d/%d failed: %s",
                    item.envelope.source_device_id,
                    item.attempts,
                    self.retry_limit,
                    error_msg,
                )
                return None

    def remove(self, item: BufferedTelemetry) -> None:
        """Remove a successfully persisted item from buffer."""
        with self._lock:
            if item in self._buffer:
                self._buffer.remove(item)

    def clear(self) -> None:
        """Clear all buffer and dead-letter entries."""
        with self._lock:
            self._buffer.clear()
            self._dead_letters.clear()
            self._dropped_overflow_count = 0

    @property
    def size(self) -> int:
        with self._lock:
            return len(self._buffer)

    @property
    def dead_letter_count(self) -> int:
        with self._lock:
            return len(self._dead_letters)

    @property
    def dead_letters(self) -> list[DeadLetterRecord]:
        with self._lock:
            return list(self._dead_letters)

    @property
    def dropped_overflow_count(self) -> int:
        with self._lock:
            return self._dropped_overflow_count
