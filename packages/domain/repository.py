"""
Aegis World, Telemetry, and Device Registry Repository Ports.

Defines technology-neutral persistence boundaries for World aggregates,
historical telemetry observations, and registered edge devices.
"""

from abc import ABC, abstractmethod
from datetime import datetime

from .entities import Device, Observation
from .exceptions import EntityNotFoundError
from .model import WorldModel


class WorldRepository(ABC):
    """
    Abstract Port for World Model persistence.

    Decouples the domain/application layer from concrete storage engines
    (e.g., PostgreSQL, TimescaleDB, In-Memory).
    """

    @abstractmethod
    def save(self, world_model: WorldModel) -> None:
        """
        Persist a World Model aggregate.

        If the World already exists, it is updated; otherwise, it is created.
        """
        pass

    @abstractmethod
    def get(self, world_id: str) -> WorldModel:
        """
        Retrieve a World Model aggregate by its unique identity.

        Raises EntityNotFoundError if the world does not exist.
        """
        pass

    @abstractmethod
    def exists(self, world_id: str) -> bool:
        """Return True if a World aggregate with the given ID exists."""
        pass

    @abstractmethod
    def list_all(self) -> list[WorldModel]:
        """List all persisted World Model aggregates."""
        pass

    @abstractmethod
    def delete(self, world_id: str) -> None:
        """
        Delete a World Model aggregate by ID.

        Raises EntityNotFoundError if the world does not exist.
        """
        pass


class InMemoryWorldRepository(WorldRepository):
    """Concrete in-memory implementation of WorldRepository for testing and simulation."""

    def __init__(self) -> None:
        self._storage: dict[str, WorldModel] = {}

    def save(self, world_model: WorldModel) -> None:
        self._storage[world_model.world.world_id] = world_model

    def get(self, world_id: str) -> WorldModel:
        if world_id not in self._storage:
            raise EntityNotFoundError(f"World aggregate with ID '{world_id}' not found.")
        return self._storage[world_id]

    def exists(self, world_id: str) -> bool:
        return world_id in self._storage

    def list_all(self) -> list[WorldModel]:
        return list(self._storage.values())

    def delete(self, world_id: str) -> None:
        if world_id not in self._storage:
            raise EntityNotFoundError(f"World aggregate with ID '{world_id}' not found.")
        del self._storage[world_id]


# --- P1.S5 Persistent Telemetry & Device Registry Ports ---


class DeviceRegistry(ABC):
    """
    Abstract Port for checking registered device identities and their schemas.

    Guarantees that untrusted/unknown devices are validated at the perimeter.
    """

    @abstractmethod
    def register_device(self, device: Device) -> None:
        """Register a new device structure and its linked sensors."""
        pass

    @abstractmethod
    def is_registered(self, device_id: str) -> bool:
        """Return True if the device ID is formally registered in Aegis."""
        pass

    @abstractmethod
    def get_device(self, device_id: str) -> Device:
        """Retrieve a registered device definition. Raises EntityNotFoundError if missing."""
        pass

    @abstractmethod
    def list_devices(self) -> list[Device]:
        """List all registered devices."""
        pass

    @abstractmethod
    def validate_sensor_association(self, device_id: str, sensor_id: str) -> bool:
        """Verify that a given sensor_id is formally registered to the specific device_id."""
        pass


class TelemetryRepository(ABC):
    """
    Abstract Port for historical telemetry persistence.

    Separates domain and query logic from specific storage engines.
    """

    @abstractmethod
    def save_observation(self, observation: Observation) -> None:
        """
        Persist a validated domain observation.

        Raises an explicit persistence exception on database failure.
        """
        pass

    @abstractmethod
    def save_batch(self, observations: list[Observation]) -> None:
        """Atomically persist a collection of observations."""
        pass

    @abstractmethod
    def get_observations(
        self,
        device_id: str | None = None,
        sensor_id: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 1000,
    ) -> list[Observation]:
        """
        Query historical observations matching the given criteria.

        Returns observations sorted by timestamp in ascending order.
        """
        pass

    @abstractmethod
    def get_latest_observation(self, sensor_id: str) -> Observation | None:
        """Retrieve the single most recent observation for a given sensor."""
        pass


class InMemoryDeviceRegistry(DeviceRegistry):
    """In-memory implementation of DeviceRegistry for tests and offline processing."""

    def __init__(self) -> None:
        self._devices: dict[str, Device] = {}

    def register_device(self, device: Device) -> None:
        self._devices[device.device_id] = device

    def is_registered(self, device_id: str) -> bool:
        return device_id in self._devices

    def get_device(self, device_id: str) -> Device:
        if device_id not in self._devices:
            raise EntityNotFoundError(f"Device with ID '{device_id}' is not registered.")
        return self._devices[device_id]

    def list_devices(self) -> list[Device]:
        return list(self._devices.values())

    def validate_sensor_association(self, device_id: str, sensor_id: str) -> bool:
        if device_id not in self._devices:
            return False
        device = self._devices[device_id]
        return any(s.sensor_id == sensor_id for s in device.sensors)


class InMemoryTelemetryRepository(TelemetryRepository):
    """In-memory implementation of TelemetryRepository for testing and fast simulations."""

    def __init__(self) -> None:
        self._observations: list[Observation] = []

    def save_observation(self, observation: Observation) -> None:
        self._observations.append(observation)

    def save_batch(self, observations: list[Observation]) -> None:
        self._observations.extend(observations)

    def get_observations(
        self,
        device_id: str | None = None,
        sensor_id: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 1000,
    ) -> list[Observation]:
        results = self._observations

        if device_id:
            results = [o for o in results if o.device_id == device_id]
        if sensor_id:
            results = [o for o in results if o.sensor_id == sensor_id]
        if start_time:
            results = [o for o in results if o.timestamp >= start_time]
        if end_time:
            results = [o for o in results if o.timestamp <= end_time]

        # Sort chronologically by timestamp
        results = sorted(results, key=lambda x: x.timestamp)
        return results[:limit]

    def get_latest_observation(self, sensor_id: str) -> Observation | None:
        matching = [o for o in self._observations if o.sensor_id == sensor_id]
        if not matching:
            return None
        return max(matching, key=lambda x: x.timestamp)
