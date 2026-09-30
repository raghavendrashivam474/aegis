"""CLI Entry point for running the Aegis MQTT Ingestion Adapter."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from .config import IngestionConfig
from .mqtt_consumer import MqttTelemetryConsumer


def main() -> int:
    parser = argparse.ArgumentParser(description="Aegis MQTT Ingestion Bridge")
    parser.add_argument("--host", type=str, default="localhost", help="MQTT Broker hostname")
    parser.add_argument("--port", type=int, default=1883, help="MQTT Broker port")
    parser.add_argument("--topic", type=str, default="aegis/telemetry/#", help="MQTT Topic pattern")
    parser.add_argument(
        "--sink",
        type=str,
        default="data/telemetry_stream.jsonl",
        help="Target stream file path",
    )
    parser.add_argument(
        "--reset-sink",
        action="store_true",
        help="Clear existing telemetry stream file at startup",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable DEBUG logging",
    )

    args = parser.parse_args()

    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="[%(asctime)s] %(levelname)-7s [%(name)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    sink_path = Path(args.sink)
    if args.reset_sink:
        sink_path.parent.mkdir(parents=True, exist_ok=True)
        sink_path.write_text("", encoding="utf-8")

    config = IngestionConfig(
        broker_host=args.host,
        broker_port=args.port,
        topic=args.topic,
        stream_sink=sink_path,
    )

    def log_and_sink(envelope):
        sink_path.parent.mkdir(parents=True, exist_ok=True)
        import json

        with sink_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(envelope.to_dict()) + "\n")

        obs_summary = ", ".join(f"{o.sensor_id}={o.value}{o.unit}" for o in envelope.observations)
        print(
            f"[{envelope.sent_at_iso}] Ingested from '{envelope.source_device_id}': {obs_summary}"
        )

    consumer = MqttTelemetryConsumer(config=config, on_envelope=log_and_sink)

    print("==================================================")
    print(" AEGIS MQTT INGESTION ADAPTER (BRIDGE)")
    print("==================================================")
    print(f"Broker:          {config.broker_host}:{config.broker_port}")
    print(f"Topic Pattern:   {config.topic}")
    print(f"Client ID:       {config.client_id}")
    print(f"IPC Sink:        {config.stream_sink}")
    print("==================================================")
    print("Connecting to broker... (Press Ctrl+C to stop)\n")

    try:
        consumer.start(blocking=True)
    except KeyboardInterrupt:
        print("\nStopping Ingestion Adapter...")
        consumer.stop()
        print(
            f"Done. Processed: {consumer.received_count} valid, {consumer.invalid_count} rejected."
        )
    except Exception as err:
        print(f"\nFatal ingestion error: {err}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
