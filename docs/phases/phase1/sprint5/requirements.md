# P1.S5 Requirements Specification

**Sprint:** P1.S5 — Persistent Telemetry & Device Registration
**Baseline:** v-P1.S4 (41 tests, 0 regressions)
**Status:** Draft → Approved before implementation

---

## 1. Functional Requirements

### FR-S5-01 — Persistent Telemetry Storage
Aegis shall persist valid telemetry observations in a PostgreSQL database
behind a technology-neutral repository port.

**Rationale:** The JSONL file (ADR-006) was always transitional. P1.S5
establishes durable storage for historical analysis.

### FR-S5-02 — Telemetry Retrieval
Aegis shall retrieve persisted telemetry by device, sensor, and time range
through an application-level query interface.

### FR-S5-03 — Device Registration
Aegis shall maintain a registry of recognized telemetry-producing devices
with deterministic lookup by device_id.

### FR-S5-04 — Device Validation
Aegis shall validate every incoming TelemetryEnvelope against the device
registry before persistence.

### FR-S5-05 — Unknown Device Handling
Aegis shall reject or quarantine telemetry from unregistered devices.
Rejected telemetry shall NOT be silently persisted as trusted data.

### FR-S5-06 — Sensor Identity Validation
Aegis shall validate that each observation's sensor_id is associated with
the envelope's source_device_id in the registry.
Unknown sensor → deterministic rejection (documented policy).

### FR-S5-07 — Real MQTT Integration Test
Aegis shall demonstrate end-to-end telemetry transfer through an actual
MQTT broker (Mosquitto via Docker) in a reproducible test environment.

### FR-S5-08 — Persistence Failure Handling
Aegis shall handle database failures explicitly. The system shall NOT
report telemetry as successfully stored when the database write failed.

### FR-S5-09 — Historical Query Interface
Aegis shall provide a defined application-level mechanism for querying
historical telemetry, independent of the dashboard or any specific UI.

### FR-S5-10 — Existing Producer Compatibility
P1.S3 simulator, P1.S4 mock ESP32 publisher, and physical ESP32 producer
behavior shall remain fully compatible with the Aegis telemetry path.

### FR-S5-11 — Dashboard Compatibility
The existing Streamlit dashboard shall continue to display valid telemetry
after the persistence transition. No SQL in dashboard code.

### FR-S5-12 — NTP Decision
ESP32 timestamp synchronization shall be implemented or formally deferred
with documented rationale and verification implications.

---

## 2. Input / Output Matrix

| Req      | Input                              | Expected Output                          |
|----------|------------------------------------|------------------------------------------|
| FR-S5-01 | Valid TelemetryEnvelope            | Persisted observation rows in PostgreSQL |
| FR-S5-02 | device_id, sensor_id, time range   | Matching historical observations         |
| FR-S5-03 | Device definition (id, type, etc.) | Registered device record                 |
| FR-S5-04 | TelemetryEnvelope + device_id      | Accept / Reject decision                 |
| FR-S5-05 | Envelope from unknown device       | Rejection result + log entry             |
| FR-S5-06 | Envelope with mismatched sensor    | Deterministic rejection                  |
| FR-S5-07 | MQTT publisher + Mosquitto broker  | Broker-delivered envelope at consumer    |
| FR-S5-08 | DB unavailable during write        | Explicit failure result (no silent OK)   |
| FR-S5-09 | Query request (device/time)        | List of historical observations          |
| FR-S5-10 | Existing simulator / mock producer | Existing telemetry behavior preserved    |
| FR-S5-11 | Persisted telemetry                | Dashboard-visible telemetry              |
| FR-S5-12 | ESP32 timestamps                   | NTP sync or formal deferral ADR          |

---

## 3. Non-Functional Constraints

| Constraint | Detail |
|---|---|
| Architecture | No infrastructure imports in `packages/domain/` (enforced by `test_architecture_boundaries.py`) |
| Contracts | `TelemetryEnvelope` schema v1 unchanged |
| CI | Python 3.11, 3.12, 3.13 — all green |
| Linting | `ruff check` + `ruff format --check` clean |
| Regression | All 41 P1.S4 tests continue passing |
| Dashboard | No SQL, no psycopg, no SQLAlchemy in `apps/dashboard/` |
| Domain | No paho, mqtt, postgres, sqlalchemy in `packages/domain/` |
