# ADR-011: Telemetry Failure Classification & Dead-Letter Semantics

## Status
Accepted

## Context
A major risk in industrial telemetry ingestion is poison pill messages: if malformed payloads, unauthorized device IDs, or invalid sensor associations are placed into an infinite retry queue, they saturate database pools and exhaust CPU resources.

## Decision
1. Formally classify all failures into two mutually exclusive categories:
   - **Permanent Validation Failures**: Unknown device IDs, inactive/disabled devices, sensor ownership mismatches, and contract decoding errors. These are **never buffered or retried**. They are immediately rejected, logged, and quarantined.
   - **Transient Infrastructure Failures**: Connection timeouts, database connection errors, and pool saturation. These are **buffered and retried**.
2. Enforce a strict `RETRY_LIMIT` (default: 3 attempts) for transient failures.
3. Items exceeding `RETRY_LIMIT` are moved to a dedicated `DeadLetterRecord` quarantine, preserving the envelope, observation data, timestamp, and audit trail of failure reasons.

## Consequences
### Positive
- Prevents infinite retry loops on invalid telemetry.
- Preserves full auditability for failed records.
- Guarantees deterministic rejection behavior for non-recoverable errors.
