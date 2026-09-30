"""Tests for World Repository port and In-Memory adapter."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "packages"))

from domain import (
    Asset,
    EntityNotFoundError,
    InMemoryWorldRepository,
    World,
    WorldModel,
)


def test_in_memory_repository_crud():
    """Verify in-memory repository saves, retrieves, lists, and deletes World models."""
    repo = InMemoryWorldRepository()

    # Empty check
    assert repo.list_all() == []
    assert not repo.exists("world-1")

    world1 = World(world_id="world-1", name="Plant 1")
    model1 = WorldModel(world1)
    model1.add_asset(
        Asset(asset_id="asset-1", name="Pump 1", asset_type="pump", world_id="world-1")
    )

    world2 = World(world_id="world-2", name="Plant 2")
    model2 = WorldModel(world2)

    # Save
    repo.save(model1)
    repo.save(model2)

    assert repo.exists("world-1")
    assert repo.exists("world-2")
    assert len(repo.list_all()) == 2

    # Retrieve
    retrieved = repo.get("world-1")
    assert retrieved.world.name == "Plant 1"
    assert retrieved.get_asset("asset-1").name == "Pump 1"

    # Delete
    repo.delete("world-2")
    assert not repo.exists("world-2")
    assert len(repo.list_all()) == 1

    # Exception on retrieving deleted or non-existent
    with pytest.raises(EntityNotFoundError):
        repo.get("world-2")

    with pytest.raises(EntityNotFoundError):
        repo.delete("world-2")
