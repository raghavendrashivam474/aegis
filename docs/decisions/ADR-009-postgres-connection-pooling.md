# ADR-009: PostgreSQL Connection Pooling & Adapter Lifecycle

## Status
Accepted

## Context
In P1.S5 and P1.S6, `PostgresDeviceRegistry` and `PostgresTelemetryRepository` established a fresh TCP connection to PostgreSQL on every single query/method invocation via `psycopg.connect()`.
While functional for initial proof of concept, this approach has concrete limitations:
1. High TCP handshake and SSL negotiation latency per observation batch.
2. Inefficient resource utilization on both client and PostgreSQL server.
3. N+1 connection creation during device discovery (`list_devices()`).
4. Lack of bounded concurrency controls under high producer burst loads.

## Decision
1. Introduce `PostgresConnectionPool` wrapping `psycopg_pool.ConnectionPool` with bounded min/max sizing, checkout timeout, and idle reclamation.
2. Refactor `PostgresDeviceRegistry` and `PostgresTelemetryRepository` to acquire connections via pooled context managers without modifying pure domain contracts (`DeviceRegistry`, `TelemetryRepository`).
3. Retain backwards-compatibility by allowing adapter constructors to accept either a `database_url: str` (owning an internal pool) or an explicit shared `PostgresConnectionPool` instance.
4. Refactor `list_devices()` to utilize a single connection checkout for batch entity population.

## Consequences
### Positive
- Predictable and bounded concurrency against PostgreSQL.
- Drastically reduced latency per transaction.
- Safe connection recycling and health verification on database restart.
- Domain boundaries remain completely decoupled from database mechanics.

### Negative / Trade-offs
- Added dependency on `psycopg_pool` (standard companion package to psycopg 3).
- Resource lifecycle must be managed (closing pool at shutdown).
