# ADR-010: Ingestion Retry & Bounded Buffering Policy

## Status
Accepted

## Context
In P1.S6, transient database unavailability (e.g., PostgreSQL restarting or connection pool timeout) resulted in persistence failures that returned `accepted=False`. Because the MQTT message had already been pulled from the broker, the telemetry payload was dropped.
To achieve high operational resilience without introducing heavy distributed queue dependencies (such as Kafka or RabbitMQ) during Phase 1, the ingestion adapter requires an in-process reliability buffer.

## Decision
1. Introduce `PersistenceRetryBuffer` to stage valid telemetry observations upon transient persistence failure.
2. Maintain strict capacity bounds (`MAX_BUFFER_SIZE = 1000` by default).
3. Provide explicit overflow policies: `DROP_OLDEST` (prioritizing recent operational state) or `REJECT_NEWEST`.
4. Implement **Opportunistic Backlog Draining**: when any subsequent observation write succeeds, the pipeline triggers an immediate drain pass over pending buffered items.
5. Provide explicit manual/scheduled `drain_buffer()` execution for active recovery loops.

## Consequences
### Positive
- Zero data loss during typical transient database restarts (< 60 seconds).
- Bounded RAM footprint preventing memory exhaustion under extended outages.
- Retains pure domain architecture; no distributed infrastructure overhead added.

### Negative / Trade-offs
- In-memory buffer is volatile across sudden process kills (Phase 2 will introduce persistent write-ahead logs).
