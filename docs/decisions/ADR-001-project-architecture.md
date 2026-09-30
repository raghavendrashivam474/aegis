 ADR-001 — Project Architecture & Dependency Inversion

## Status
Accepted

## Context
Aegis is an industrial/IoT autonomous system that will evolve through multiple phases—from world representation to autonomous decision making. Without explicit architectural boundaries, systems of this nature quickly suffer from tight coupling between physical communication protocols (MQTT, HTTP, Serial), databases (PostgreSQL, TimescaleDB), and core domain logic.

## Decision
We adopt a Hexagonal / Ports-and-Adapters architectural pattern enforcing strict Dependency Inversion:
1. **Domain (`packages/domain`):** Contains pure business entities and invariant rules. Depends on nothing.
2. **Contracts (`packages/contracts`):** Technology-neutral interchange contracts for cross-boundary data transfer.
3. **Applications (`apps/*`):** Use-case orchestration and runtime applications (backend, simulator, edge).
4. **Infrastructure (`infrastructure/*`):** Technical implementations, database adapters, transport drivers, and container topologies.

Dependencies strictly point inward:
`Interfaces / Infrastructure -> Application -> Domain`

## Alternatives Considered
1. **Traditional 3-Tier Layered Architecture (UI -> Service -> DB):** Rejected due to the tight coupling between business logic and database models.
2. **Microservices per Sensor/Asset immediately:** Rejected due to premature complexity, network overhead, and distributed debugging burden at Phase 1.

## Consequences
* **What it enables:** Telemetry sources (ESP32 vs. digital simulator) and persistence backends can be swapped without touching domain logic or business rules.
* **What it makes harder:** Requires explicit boundary mapping and conversion between transport wire models, contracts, and domain entities.

## Revisit Conditions
Reconsider if the domain proves to be strictly pass-through CRUD with zero operational logic across three consecutive sprints.
