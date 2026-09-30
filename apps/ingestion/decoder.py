# ruff: noqa: E402
"""Payload Decoder and Validator for Incoming Telemetry."""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import Any

# Ensure packages/ is importable
_PACKAGES = str(Path(__file__).resolve().parents[2] / "packages")
if _PACKAGES not in sys.path:
    sys.path.insert(0, _PACKAGES)

from contracts import TelemetryEnvelope

logger = logging.getLogger(__name__)


class TelemetryDecodeError(Exception):
    """Raised when an incoming raw payload fails parsing or contract validation."""


class TelemetryDecoder:
    """Decodes raw MQTT payloads into strongly-typed TelemetryEnvelope contracts."""

    @staticmethod
    def decode(raw_payload: str | bytes) -> TelemetryEnvelope:
        """
        Parse and validate raw JSON payload into a TelemetryEnvelope.

        Raises TelemetryDecodeError if payload is malformed or invalid contract.
        """
        if isinstance(raw_payload, bytes):
            try:
                raw_payload = raw_payload.decode("utf-8")
            except UnicodeDecodeError as err:
                raise TelemetryDecodeError(f"Payload is not valid UTF-8: {err}") from err

        if not raw_payload or not raw_payload.strip():
            raise TelemetryDecodeError("Empty payload received.")

        try:
            data: Any = json.loads(raw_payload)
        except json.JSONDecodeError as err:
            raise TelemetryDecodeError(f"Invalid JSON string: {err}") from err

        if not isinstance(data, dict):
            raise TelemetryDecodeError(
                f"Payload root must be a JSON object, got {type(data).__name__}"
            )

        try:
            return TelemetryEnvelope.from_dict(data)
        except (KeyError, ValueError, TypeError) as err:
            raise TelemetryDecodeError(
                f"Failed contract validation for TelemetryEnvelope: {err}"
            ) from err
