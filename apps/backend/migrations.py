# ruff: noqa: E501
"""Database Migration and Schema Management for Aegis PostgreSQL/TimescaleDB."""

from __future__ import annotations

import logging
import os
from collections.abc import Generator
from contextlib import contextmanager

import psycopg
from psycopg.rows import dict_row

logger = logging.getLogger(__name__)

DEFAULT_DATABASE_URL = os.getenv(
    "AEGIS_DATABASE_URL",
    "postgresql://aegis_admin:aegis_password@localhost:5434/aegis_db",
)

SCHEMA_SQL = """
-- 1. Registered Devices Table
CREATE TABLE IF NOT EXISTS aegis_devices (
    device_id VARCHAR(64) PRIMARY KEY,
    name VARCHAR(128) NOT NULL,
    asset_id VARCHAR(64) NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'ACTIVE',
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    registered_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 2. Registered Sensors Table
CREATE TABLE IF NOT EXISTS aegis_sensors (
    sensor_id VARCHAR(64) PRIMARY KEY,
    device_id VARCHAR(64) NOT NULL REFERENCES aegis_devices(device_id) ON DELETE CASCADE,
    name VARCHAR(128) NOT NULL,
    measurement_type VARCHAR(64) NOT NULL,
    unit VARCHAR(32) NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'ACTIVE',
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);

-- 3. Telemetry Observations Table (Optimized for Timeseries)
CREATE TABLE IF NOT EXISTS aegis_telemetry_observations (
    id BIGSERIAL,
    observation_id VARCHAR(128) NOT NULL,
    device_id VARCHAR(64) NOT NULL,
    sensor_id VARCHAR(64) NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    value DOUBLE PRECISION NOT NULL,
    unit VARCHAR(32) NOT NULL,
    quality VARCHAR(32) NOT NULL DEFAULT 'GOOD',
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    persisted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (id, timestamp)
);

-- Indexing for fast chronological queries
CREATE INDEX IF NOT EXISTS idx_telemetry_dev_ts ON aegis_telemetry_observations(device_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_telemetry_sens_ts ON aegis_telemetry_observations(sensor_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_telemetry_ts ON aegis_telemetry_observations(timestamp DESC);
"""


@contextmanager
def get_db_connection(
    database_url: str = DEFAULT_DATABASE_URL,
) -> Generator[psycopg.Connection, None, None]:
    """Context manager yielding an active psycopg connection."""
    conn = psycopg.connect(database_url, autocommit=True, row_factory=dict_row)
    try:
        yield conn
    finally:
        conn.close()


def run_migrations(database_url: str = DEFAULT_DATABASE_URL) -> None:
    """Apply schema migrations to ensure all required tables and indexes exist."""
    logger.info("Applying database migrations on %s...", database_url.split("@")[-1])
    with get_db_connection(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(SCHEMA_SQL)
    logger.info("Database migrations applied successfully.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_migrations()
