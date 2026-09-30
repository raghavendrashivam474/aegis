 ADR-005 — World Model Architecture & Invariants

## Status
Accepted

## Context
P1.S1 established pure domain vocabulary (`World`, `Asset`, `Device`, `Sensor`, `Observation`) as flat dataclasses with basic parent-ID references. While sufficient for defining what entities exist, this vocabulary alone cannot enforce structural integrity, prevent impossible states, or answer hierarchical queries such as "which asset does this sensor ultimately belong to?"

P1.S2 requires the domain to evolve from static vocabulary into a coherent, queryable, and self-validating World Model without introducing any infrastructure coupling.

## Decision
We introduce three new domain constructs:

1. **`WorldModel` aggregate** (`packages/domain/model.py`): A root aggregate that wraps a `World` entity and manages its full `Asset -> Device -> Sensor` hierarchy. It maintains internal lookup indexes for O(1) entity retrieval and enforces all structural invariants on mutation.

2. **Domain exceptions** (`packages/domain/exceptions.py`): `DuplicateEntityError`, `EntityNotFoundError`, and `InvariantViolationError` provide precise, typed failure modes for invalid operations.

3. **`EntityStatus` lifecycle enum**: A minimal `ACTIVE / INACTIVE` status added to all hierarchical entities (`World`, `Asset`, `Device`, `Sensor`) with a default of `ACTIVE`, preserving full backward compatibility with P1.S1 constructors.

### Enforced Invariants
* No duplicate entity IDs within a World Model.
* Child entities must reference their actual parent (`Asset.world_id == World.world_id`, `Device.asset_id == Asset.asset_id`, `Sensor.device_id == Device.device_id`).
* Observations must reference a known sensor whose parent device matches the observation's `device_id`.
* Entities cannot be attached to parents that do not exist in the model.

### Repository Port
A technology-neutral `WorldRepository` abstract base class defines the persistence boundary (`save`, `get`, `exists`, `list_all`, `delete`). An `InMemoryWorldRepository` adapter provides concrete storage for testing and simulation. The domain remains unaware of PostgreSQL, Redis, or any storage technology.

## Alternatives Considered
1. **Graph database / networkx-based relationship model:** Rejected as premature complexity. The hierarchy is strictly tree-structured (World -> Asset -> Device -> Sensor) and does not require arbitrary graph traversal at this stage.
2. **Event-sourced aggregate with full lifecycle state machine:** Rejected. The current requirement is simply active/inactive distinction. A full state machine would be over-engineering for Phase 1.
3. **Repository inside `infrastructure/`:** Considered but rejected. The repository *port* (abstract interface) belongs in the domain to express what persistence capability is required. Only concrete adapters (PostgreSQL, etc.) belong in infrastructure.

## Consequences
* **What it enables:** The system can construct, validate, query, and persist a complete industrial environment representation. Invalid states are rejected at the domain boundary before reaching any storage or transport layer.
* **What it makes harder:** All entity mutations must flow through the `WorldModel` aggregate rather than directly appending to lists, which requires slightly more discipline in application code.

## Revisit Conditions
Reconsider the invariant set and aggregate boundaries if P1.S3/P1.S4 introduces cross-asset device sharing, multi-world sensor federation, or complex lifecycle state machines beyond active/inactive.
