from __future__ import annotations
import logging
import uuid
from datetime import datetime, timedelta, UTC
from pathlib import Path
from typing import Generator

from contracts import TelemetryEnvelope, ObservationPayload, CURRENT_SCHEMA_VERSION
from apps.dataset_replay.config import DatasetReplayConfig
from apps.dataset_replay.registration import MAPSS_SENSORS

logger = logging.getLogger("aegis.dataset_replay.adapter")

class CmapssAdapter:
    """Parses and maps raw C-MAPSS historical records into Aegis TelemetryEnvelopes."""

    def __init__(self, config: DatasetReplayConfig | None = None) -> None:
        self.config = config or DatasetReplayConfig()
        self.base_time = datetime.fromisoformat(self.config.base_time_str)
        if self.base_time.tzinfo is None:
            self.base_time = self.base_time.replace(tzinfo=UTC)

    def parse_row(self, line: str) -> dict | None:
        """Parse space-separated string line into a typed dictionary representation."""
        parts = line.strip().split()
        if not parts:
            return None
        
        if len(parts) < 26:
            logger.warning("Row ignored. Expected at least 26 fields, got %d", len(parts))
            return None

        try:
            return {
                "unit": int(float(parts[0])),
                "cycle": int(float(parts[1])),
                "settings": [float(parts[2]), float(parts[3]), float(parts[4])],
                "sensors": [float(val) for val in parts[5:26]]
            }
        except (ValueError, TypeError) as err:
            logger.warning("Failed parsing numerical values in row: %s", err)
            return None

    def map_to_envelope(self, row: dict) -> TelemetryEnvelope:
        """Translate parsed dictionary row into a strongly-typed TelemetryEnvelope."""
        unit = row["unit"]
        cycle = row["cycle"]
        device_id = f"engine-{unit:03d}"

        # Synthesize timestamp chronologically: Base time + cycle minutes
        timestamp = self.base_time + timedelta(seconds=(cycle - 1) * self.config.time_increment_seconds)
        timestamp_iso = timestamp.isoformat()

        payloads = []
        for idx, (s_id, s_name, _, s_unit) in enumerate(MAPSS_SENSORS):
            sensor_val = row["sensors"][idx]
            qualified_sensor_id = f"{s_id}-{device_id}"

            # Simple progressive quality assertion baseline
            quality = "GOOD"
            if cycle > 95:  # Final runs near failures yield higher operational uncertainty
                quality = "UNCERTAIN"

            # Enforce schema constraints and contract models directly
            payloads.append(
                ObservationPayload(
                    observation_id=uuid.uuid4().hex,
                    sensor_id=qualified_sensor_id,
                    timestamp_iso=timestamp_iso,
                    value=sensor_val,
                    unit=s_unit,
                    quality=quality,
                    metadata={
                        "device_id": device_id,
                        "cycle": cycle,
                        "sensor_name": s_name
                    }
                )
            )

        return TelemetryEnvelope(
            schema_version=CURRENT_SCHEMA_VERSION,
            source_device_id=device_id,
            sent_at_iso=datetime.now(UTC).isoformat(),  # Ingestion/Sent Wall-Clock Marker
            observations=payloads,
            metadata={
                "source": "NASA_CMAPSS_FD001",
                "cycle": cycle,
                "settings": row["settings"]
            }
        )

    def iter_envelopes(self, limit_units: list[int] | None = None) -> Generator[TelemetryEnvelope, None, None]:
        """Generator streaming TelemetryEnvelopes parsed from dataset file."""
        filepath = self.config.dataset_file_path
        if not filepath.exists():
            raise FileNotFoundError(f"Missing active C-MAPSS dataset file: {filepath}")

        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                parsed = self.parse_row(line)
                if parsed is None:
                    continue
                
                # Bounded selection filter
                if limit_units and parsed["unit"] not in limit_units:
                    continue

                yield self.map_to_envelope(parsed)
