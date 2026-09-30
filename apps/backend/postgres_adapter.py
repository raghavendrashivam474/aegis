# ruff: noqa: E501
"""
PostgreSQL Concrete Adapters for Aegis Persistence.

Implements:
- PostgresDeviceRegistry (implements domain.DeviceRegistry)
- PostgresTelemetryRepository (implements domain.TelemetryRepository)
"""

from __future__ import annotations

import json
import logging
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

logger = logging.getLogger(__name__)


class PostgresDeviceRegistry(DeviceRegistry):
    """PostgreSQL-backed Device and Sensor Identity Registry."""

    def __init__(self, database_url: str) -> None:
        self.database_url = database_url

    def _get_conn(self) -> psycopg.Connection:
        return psycopg.connect(self.database_url, row_factory=dict_row)

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
        with self._get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT device_id FROM aegis_devices;")
                rows = cur.fetchall()
                return [self.get_device(r["device_id"]) for r in rows]

    def validate_sensor_association(self, device_id: str, sensor_id: str) -> bool:
        with self._get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT 1 FROM aegis_sensors WHERE device_id = %s AND sensor_id = %s;",
                    (device_id, sensor_id),
                )
                return cur.fetchone() is not None


class PostgresTelemetryRepository(TelemetryRepository):
    """PostgreSQL-backed Historical Telemetry Persistence Repository."""

    def __init__(self, database_url: str) -> None:
        self.database_url = database_url

    def _get_conn(self) -> psycopg.Connection:
        return psycopg.connect(self.database_url, row_factory=dict_row)

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
