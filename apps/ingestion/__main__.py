"""
Ingestion Adapter Process Runner.

Initializes Device Identity Registry, Telemetry Persistence, Ingestion Pipeline,
and connects the MQTT telemetry listener.
"""

from __future__ import annotations

import logging
import os
import sys

from apps.backend.migrations import run_migrations
from apps.backend.postgres_adapter import PostgresDeviceRegistry, PostgresTelemetryRepository
from apps.ingestion.config import IngestionConfig
from apps.ingestion.mqtt_consumer import MqttTelemetryConsumer
from apps.ingestion.pipeline import TelemetryIngestionPipeline

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

logger = logging.getLogger("aegis.ingestion")


def main() -> int:
    logger.info("================================================")
    logger.info(" AEGIS TELEMETRY INGESTION SERVICE (S5)")
    logger.info("================================================")

    config = IngestionConfig()

    # Determine database connection details
    database_url = os.getenv(
        "AEGIS_DATABASE_URL",
        "postgresql://aegis_admin:aegis_password@localhost:5434/aegis_db",
    )

    try:
        # Enforce schemas are verified and migration rules matched
        run_migrations(database_url)

        # Initialize concrete infrastructure adapters
        logger.info("Connecting Ingestion Pipeline to database...")
        registry = PostgresDeviceRegistry(database_url)
        repository = PostgresTelemetryRepository(database_url)

        # Establish Telemetry Pipeline (including legacy JSONL stream mirroring)
        pipeline = TelemetryIngestionPipeline(
            registry=registry,
            repository=repository,
            stream_sink=config.stream_sink,
        )

        logger.info("Verifying registered device identity footprint...")
        devices = registry.list_devices()
        logger.info("Loaded %d registered device identities from database.", len(devices))

        # Spin up MQTT consumer with injected Pipeline
        consumer = MqttTelemetryConsumer(config=config, pipeline=pipeline)

        logger.info("Starting MQTT Subscriber loop...")
        consumer.start(blocking=True)

    except KeyboardInterrupt:
        logger.info("Ingestion process interrupted by keyboard.")
    except Exception as err:
        logger.exception("Fatal exception in ingestion runner: %s", err)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
