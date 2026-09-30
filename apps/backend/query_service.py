"""
Aegis Historical Telemetry Query Service.

Defines the application-level query boundary used by dashboards and APIs,
ensuring presentation layers never write direct SQL.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime

from domain import Observation, TelemetryRepository

from apps.backend.postgres_adapter import PostgresTelemetryRepository

logger = logging.getLogger(__name__)


class TelemetryQueryService:
    """Application-layer service for querying historical telemetry records."""

    def __init__(self, repository: TelemetryRepository) -> None:
        self.repository = repository

    @classmethod
    def create_default(cls, database_url: str | None = None) -> TelemetryQueryService:
        """Factory method to construct with concrete PostgreSQL repository."""
        db_url = database_url or os.getenv(
            "AEGIS_DATABASE_URL",
            "postgresql://aegis_admin:aegis_password@localhost:5434/aegis_db",
        )
        repo = PostgresTelemetryRepository(db_url)
        return cls(repo)

    def get_device_history(
        self,
        device_id: str,
        sensor_id: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 1000,
    ) -> list[Observation]:
        """Fetch chronological historical observations for a registered device."""
        return self.repository.get_observations(
            device_id=device_id,
            sensor_id=sensor_id,
            start_time=start_time,
            end_time=end_time,
            limit=limit,
        )

    def get_sensor_history(
        self,
        sensor_id: str,
        limit: int = 500,
    ) -> list[Observation]:
        """Fetch historical records for a specific sensor."""
        return self.repository.get_observations(sensor_id=sensor_id, limit=limit)

    def get_latest_reading(self, sensor_id: str) -> Observation | None:
        """Fetch the single most recent reading for a sensor."""
        return self.repository.get_latest_observation(sensor_id=sensor_id)
