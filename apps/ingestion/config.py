"""Configuration for the Aegis MQTT Ingestion Adapter."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class IngestionConfig:
    """MQTT Ingestion Adapter settings with environment variable overrides."""

    broker_host: str = os.getenv("AEGIS_MQTT_HOST", "localhost")
    broker_port: int = int(os.getenv("AEGIS_MQTT_PORT", "1883"))
    topic: str = os.getenv("AEGIS_MQTT_TOPIC", "aegis/telemetry/#")
    client_id: str = os.getenv("AEGIS_MQTT_CLIENT_ID", "aegis-ingestion-adapter")
    stream_sink: Path = Path(os.getenv("AEGIS_STREAM_SINK", "data/telemetry_stream.jsonl"))
    keepalive: int = 60
