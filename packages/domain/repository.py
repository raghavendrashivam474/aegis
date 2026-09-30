"""
Aegis World Repository Port and In-Memory Adapter.

Defines the technology-neutral persistence boundary for World aggregates,
and provides a clean in-memory implementation for tests/simulations.
"""

from abc import ABC, abstractmethod

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
