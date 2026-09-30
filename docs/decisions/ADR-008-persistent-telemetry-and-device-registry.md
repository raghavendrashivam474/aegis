# ADR-008: Persistent Telemetry Storage & Device Identity Boundary

## Status
Accepted

## Context
In Sprint P1.S4, we introduced transport-agnostic MQTT ingestion, allowing physical ESP32 nodes and simulated digital twins to publish telemetry into a shared transitional JSON-lines sink (`data/telemetry_stream.jsonl`).

While effective for decoupling processes, this approach had two fundamental architectural limitations:
1. **Lack of Identity Verification**: Any client could publish arbitrary device IDs or fabricate unregistered sensor metrics, and the system would accept and persist them.
2. **Transient / Non-Queryable Persistence**: A flat JSONL file lacks indexing, cannot support time-bounded range queries efficiently, and cannot scale to industrial telemetry workloads.

## Decision
We established two formal boundaries in Aegis:

1. **Device Identity Registry (`DeviceRegistry` Port)**:
   - Every incoming `TelemetryEnvelope` must originate from a registered device in `ACTIVE` lifecycle status.
   - Every observation within the envelope must match a known sensor explicitly assigned to that parent device.
   - Unknown devices or mismatched sensor IDs are deterministic rejected/quarantined before reaching any persistence layer (**FR-S5-04**, **FR-S5-05**, **FR-S5-06**).

2. **Persistent Telemetry Storage (`TelemetryRepository` Port)**:
   - Domain observations are persisted to PostgreSQL (with future TimescaleDB compatibility) through a technology-neutral port (`packages/domain/repository.py`).
   - Observations are indexed chronologically by `(device_id, timestamp)` and `(sensor_id, timestamp)` for high-speed timeseries query performance.
   - Presentation layers (e.g. Streamlit Dashboard) consume historical records strictly via an application service (`apps/backend/query_service.py`), eliminating SQL dependencies in UI code (**FR-S5-09**, **FR-S5-11**).

3. **Containerized Infrastructure**:
   - PostgreSQL and Mosquitto are containerized via `docker-compose.yml`. Infrastructure details remain strictly isolated from domain business models.

## NTP Synchronization Decision (FR-S5-12)
Edge hardware (ESP32) timestamps are formatted as ISO-8601 UTC strings. In P1.S5, we investigated NTP clock synchronization:
- Standard local development networks and isolated simulators use host UTC clocks.
- Physical ESP32 nodes fetch time from SNTP servers when Wi-Fi is active. In offline/mocked modes, fallback to ingress-time stamping is permitted with the `metadata.transport = 'mqtt'` tag.
- Full hardware RTC clock drift compensation is formally deferred to Phase 2 edge hardening.

## Consequences
- **Security & Integrity**: Unregistered edge nodes cannot corrupt the Aegis World Model or pollute telemetry data.
- **Architectural Purity**: The domain package (`packages/domain/`) remains 100% free of PostgreSQL/psycopg/SQLAlchemy imports.
- **Backward Compatibility**: The legacy JSONL stream is maintained as a configurable mirror sink during transition without disrupting existing test suites or demonstrators.
