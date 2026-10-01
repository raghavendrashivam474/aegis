# ruff: noqa: E501
"""
PostgreSQL Concrete Adapters and Connection Pooling for Aegis Persistence.

Implements:
- PostgresConnectionPool: Thread-safe, bounded connection pool wrapper.
- PostgresDeviceRegistry: implements domain.DeviceRegistry.
- PostgresTelemetryRepository: implements domain.TelemetryRepository.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from typing import Any

import psycopg
from domain import (
    Device,
    DeviceRegistry,
    EntityNotFoundError,
    EntityStatus,
    Observation,
    QualityFlag,
    Sensor,
    TelemetryRepository,
)
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool, PoolTimeout

logger = logging.getLogger(__name__)


class PostgresConnectionPool:
    """
    Thread-safe, bounded PostgreSQL connection pool manager.

    Provides controlled connection checkout, bounded concurrency,
    and automatic recycling on transient connection failure.
    """

    def __init__(
        self,
        database_url: str,
        min_size: int = 1,
        max_size: int = 10,
        timeout: float = 10.0,
        max_idle: float = 300.0,
        open_immediately: bool = True,
    ) -> None:
        self.database_url = database_url
        self.min_size = min_size
        self.max_size = max_size
        self.timeout = timeout
        self.max_idle = max_idle

        self._pool = ConnectionPool(
            conninfo=self.database_url,
            min_size=self.min_size,
            max_size=self.max_size,
            timeout=self.timeout,
            max_idle=self.max_idle,
            open=open_immediately,
            kwargs={"row_factory": dict_row},
        )
        logger.info(
            "Initialized PostgresConnectionPool (min=%d, max=%d, timeout=%.1fs)",
            min_size,
            max_size,
            timeout,
        )

    @contextmanager
    def connection(self, timeout: float | None = None) -> Iterator[psycopg.Connection]:
        """
        Context manager to acquire a connection from the pool and return it on exit.

        Raises PoolTimeout if no connection becomes available within timeout.
        """
        eff_timeout = timeout if timeout is not None else self.timeout
        try:
            with self._pool.connection(timeout=eff_timeout) as conn:
                yield conn
        except PoolTimeout as err:
            logger.error("Database connection pool exhausted (timeout=%.1fs): %s", eff_timeout, err)
            raise
        except psycopg.OperationalError as err:
            logger.warning("Database operational error on pooled connection: %s", err)
            raise

    def check_health(self) -> bool:
        """Verify database connectivity via pool."""
        try:
            with self.connection(timeout=2.0) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1;")
                    return cur.fetchone() is not None
        except Exception as err:
            logger.warning("PostgresConnectionPool health check failed: %s", err)
            return False

    def close(self) -> None:
        """Close all connections in the pool."""
        self._pool.close()
        logger.info("PostgresConnectionPool closed.")

    @property
    def stats(self) -> dict[str, Any]:
        """Return operational pool statistics."""
        return {
            "min_size": self.min_size,
            "max_size": self.max_size,
            "timeout": self.timeout,
            "closed": self._pool.closed,
        }

    def __enter__(self) -> PostgresConnectionPool:
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()


class PostgresDeviceRegistry(DeviceRegistry):
    """PostgreSQL-backed Device and Sensor Identity Registry with connection pooling."""

    def __init__(
        self,
        database_url: str | None = None,
        pool: PostgresConnectionPool | None = None,
    ) -> None:
        if pool is not None:
            self._pool = pool
            self.database_url = pool.database_url
            self._owns_pool = False
        elif database_url is not None:
            self.database_url = database_url
            self._pool = PostgresConnectionPool(database_url)
            self._owns_pool = True
        else:
            raise ValueError("Either database_url or pool must be provided.")

    @contextmanager
    def _get_conn(self) -> Iterator[psycopg.Connection]:
        with self._pool.connection() as conn:
            yield conn

    def register_device(self, device: Device) -> None:
        with self._get_conn() as conn:
            with conn.cursor() as cur:
                # Upsert Device
                cur.execute(
                    """
                    INSERT INTO aegis_devices (device_id, name, asset_id, status, metadata)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (device_id) DO UPDATE SET
                        name = EXCLUDED.name,
                        asset_id = EXCLUDED.asset_id,
                        status = EXCLUDED.status,
                        metadata = EXCLUDED.metadata;
                    """,
                    (
                        device.device_id,
                        device.name,
                        device.asset_id,
                        device.status.value,
                        json.dumps(device.metadata),
                    ),
                )

                # Upsert nested sensors
                for sensor in device.sensors:
                    cur.execute(
                        """
                        INSERT INTO aegis_sensors (sensor_id, device_id, name, measurement_type, unit, status, metadata)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (sensor_id) DO UPDATE SET
                            device_id = EXCLUDED.device_id,
                            name = EXCLUDED.name,
                            measurement_type = EXCLUDED.measurement_type,
                            unit = EXCLUDED.unit,
                            status = EXCLUDED.status,
                            metadata = EXCLUDED.metadata;
                        """,
                        (
                            sensor.sensor_id,
                            device.device_id,
                            sensor.name,
                            sensor.measurement_type,
                            sensor.unit,
                            sensor.status.value,
                            json.dumps(sensor.metadata),
                        ),
                    )
            conn.commit()

    def is_registered(self, device_id: str) -> bool:
        with self._get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT 1 FROM aegis_devices WHERE device_id = %s;",
                    (device_id,),
                )
                return cur.fetchone() is not None

    def get_device(self, device_id: str) -> Device:
        with self._get_conn() as conn:
            with conn.cursor() as cur:
                return self._fetch_device_with_cursor(cur, device_id)

    def _fetch_device_with_cursor(self, cur: psycopg.Cursor, device_id: str) -> Device:
        cur.execute(
            "SELECT device_id, name, asset_id, status, metadata FROM aegis_devices WHERE device_id = %s;",
            (device_id,),
        )
        row = cur.fetchone()
        if not row:
            raise EntityNotFoundError(f"Device with ID '{device_id}' is not registered.")

        # Fetch child sensors
        cur.execute(
            "SELECT sensor_id, name, measurement_type, unit, status, metadata FROM aegis_sensors WHERE device_id = %s;",
            (device_id,),
        )
        sensor_rows = cur.fetchall()

        sensors = [
            Sensor(
                sensor_id=s["sensor_id"],
                name=s["name"],
                measurement_type=s["measurement_type"],
                unit=s["unit"],
                device_id=device_id,
                status=EntityStatus(s["status"]),
                metadata=s["metadata"] if isinstance(s["metadata"], dict) else {},
            )
            for s in sensor_rows
        ]

        return Device(
            device_id=row["device_id"],
            name=row["name"],
            asset_id=row["asset_id"],
            sensors=sensors,
            status=EntityStatus(row["status"]),
            metadata=row["metadata"] if isinstance(row["metadata"], dict) else {},
        )

    def list_devices(self) -> list[Device]:
        """List all registered devices in a single connection checkout."""
        with self._get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT device_id FROM aegis_devices;")
                rows = cur.fetchall()
                return [self._fetch_device_with_cursor(cur, r["device_id"]) for r in rows]

    def validate_sensor_association(self, device_id: str, sensor_id: str) -> bool:
        with self._get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT 1 FROM aegis_sensors WHERE device_id = %s AND sensor_id = %s;",
                    (device_id, sensor_id),
                )
                return cur.fetchone() is not None

    def close(self) -> None:
        if self._owns_pool:
            self._pool.close()


class PostgresTelemetryRepository(TelemetryRepository):
    """PostgreSQL-backed Historical Telemetry Persistence Repository with connection pooling."""

    def __init__(
        self,
        database_url: str | None = None,
        pool: PostgresConnectionPool | None = None,
    ) -> None:
        if pool is not None:
            self._pool = pool
            self.database_url = pool.database_url
            self._owns_pool = False
        elif database_url is not None:
            self.database_url = database_url
            self._pool = PostgresConnectionPool(database_url)
            self._owns_pool = True
        else:
            raise ValueError("Either database_url or pool must be provided.")

    @contextmanager
    def _get_conn(self) -> Iterator[psycopg.Connection]:
        with self._pool.connection() as conn:
            yield conn

    def save_observation(self, observation: Observation) -> None:
        self.save_batch([observation])

    def save_batch(self, observations: list[Observation]) -> None:
        if not observations:
            return

        with self._get_conn() as conn:
            with conn.cursor() as cur:
                data = [
                    (
                        obs.observation_id,
                        obs.device_id,
                        obs.sensor_id,
                        obs.timestamp,
                        obs.value,
                        obs.unit,
                        obs.quality.value,
                        json.dumps(obs.metadata),
                    )
                    for obs in observations
                ]
                cur.executemany(
                    """
                    INSERT INTO aegis_telemetry_observations (
                        observation_id, device_id, sensor_id, timestamp, value, unit, quality, metadata
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s);
                    """,
                    data,
                )
            conn.commit()

    def get_observations(
        self,
        device_id: str | None = None,
        sensor_id: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 1000,
    ) -> list[Observation]:
        clauses = []
        params: list[Any] = []

        if device_id:
            clauses.append("device_id = %s")
            params.append(device_id)
        if sensor_id:
            clauses.append("sensor_id = %s")
            params.append(sensor_id)
        if start_time:
            clauses.append("timestamp >= %s")
            params.append(start_time)
        if end_time:
            clauses.append("timestamp <= %s")
            params.append(end_time)

        where_stmt = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        sql = f"""
            SELECT observation_id, device_id, sensor_id, timestamp, value, unit, quality, metadata
            FROM aegis_telemetry_observations
            {where_stmt}
            ORDER BY timestamp ASC
            LIMIT %s;
        """
        params.append(limit)

        with self._get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                rows = cur.fetchall()

                return [
                    Observation(
                        observation_id=r["observation_id"],
                        device_id=r["device_id"],
                        sensor_id=r["sensor_id"],
                        timestamp=r["timestamp"],
                        value=float(r["value"]),
                        unit=r["unit"],
                        quality=QualityFlag(r["quality"]),
                        metadata=r["metadata"] if isinstance(r["metadata"], dict) else {},
                    )
                    for r in rows
                ]

    def get_latest_observation(self, sensor_id: str) -> Observation | None:
        with self._get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT observation_id, device_id, sensor_id, timestamp, value, unit, quality, metadata
                    FROM aegis_telemetry_observations
                    WHERE sensor_id = %s
                    ORDER BY timestamp DESC
                    LIMIT 1;
                    """,
                    (sensor_id,),
                )
                row = cur.fetchone()
                if not row:
                    return None

                return Observation(
                    observation_id=row["observation_id"],
                    device_id=row["device_id"],
                    sensor_id=row["sensor_id"],
                    timestamp=row["timestamp"],
                    value=float(row["value"]),
                    unit=row["unit"],
                    quality=QualityFlag(row["quality"]),
                    metadata=row["metadata"] if isinstance(row["metadata"], dict) else {},
                )

    def close(self) -> None:
        if self._owns_pool:
            self._pool.close()
