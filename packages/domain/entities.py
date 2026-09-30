"""
Aegis Domain Vocabulary & Core Entities.

P1.S1 established the foundational types.
P1.S2 adds lifecycle status while preserving all original signatures.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any


class QualityFlag(StrEnum):
    """Validity and quality indicator for sensor observations."""

    GOOD = "GOOD"
    UNCERTAIN = "UNCERTAIN"
    BAD = "BAD"
    CALIBRATION = "CALIBRATION"


class EntityStatus(StrEnum):
    """Operational lifecycle status for world model entities."""

    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


@dataclass(frozen=True)
class Observation:
    """A discrete measurement emitted by a sensor at a specific point in time."""

    observation_id: str
    device_id: str
    sensor_id: str
    timestamp: datetime
    value: float
    unit: str
    quality: QualityFlag = QualityFlag.GOOD
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Sensor:
    """A physical or virtual transducer providing measurable observations."""

    sensor_id: str
    name: str
    measurement_type: str  # e.g., 'temperature', 'vibration', 'pressure'
    unit: str  # e.g., 'celsius', 'mm/s', 'bar'
    device_id: str
    status: EntityStatus = EntityStatus.ACTIVE
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Device:
    """A hardware edge node or virtual compute unit associated with an asset."""

    device_id: str
    name: str
    asset_id: str
    sensors: list[Sensor] = field(default_factory=list)
    status: EntityStatus = EntityStatus.ACTIVE
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Asset:
    """A physical or operational industrial equipment entity being monitored."""

    asset_id: str
    name: str
    asset_type: str  # e.g., 'pump', 'compressor', 'turbine'
    world_id: str
    devices: list[Device] = field(default_factory=list)
    status: EntityStatus = EntityStatus.ACTIVE
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class World:
    """The root operational environment containing monitored assets."""

    world_id: str
    name: str
    description: str = ""
    assets: list[Asset] = field(default_factory=list)
    status: EntityStatus = EntityStatus.ACTIVE
    metadata: dict[str, Any] = field(default_factory=dict)
