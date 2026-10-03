# P1.S5 Test Cases & Scenarios

**Sprint:** P1.S5
**Baseline tests:** 41 (P1.S1–P1.S4)

---

## Test Case Traceability

### FR-S5-01 — Persistent Telemetry

| Test ID  | Description                                      | Category |
|----------|--------------------------------------------------|----------|
| TC-S5-01 | Valid envelope with 1 observation is persisted    | Normal   |
| TC-S5-02 | Valid envelope with 3 observations is persisted   | Normal   |
| TC-S5-03 | Persistence preserves timestamp, device, sensor   | Normal   |
| TC-S5-04 | Multiple envelopes from same device are persisted  | Normal   |
| TC-S5-05 | Observation metadata is preserved in storage       | Normal   |
| TC-S5-06 | Quality flag (GOOD/UNCERTAIN/BAD) is preserved     | Boundary |

### FR-S5-02 — Telemetry Retrieval

| Test ID  | Description                                      | Category |
|----------|--------------------------------------------------|----------|
| TC-S5-07 | Retrieve by device_id returns correct records     | Normal   |
| TC-S5-08 | Retrieve by sensor_id returns correct records     | Normal   |
| TC-S5-09 | Retrieve by time range returns correct records    | Normal   |
| TC-S5-10 | Retrieve latest observation for a sensor          | Normal   |
| TC-S5-11 | Empty result for non-existent device              | Boundary |
| TC-S5-12 | Combined device + time range filter               | Normal   |

### FR-S5-03 — Device Registration

| Test ID  | Description                                      | Category |
|----------|--------------------------------------------------|----------|
| TC-S5-13 | Register a new device successfully                | Normal   |
| TC-S5-14 | Query registered device returns correct data      | Normal   |
| TC-S5-15 | Duplicate registration is handled deterministically| Boundary |
| TC-S5-16 | List all registered devices                       | Normal   |
| TC-S5-17 | Disable a registered device                       | Normal   |

### FR-S5-04 — Device Validation

| Test ID  | Description                                      | Category |
|----------|--------------------------------------------------|----------|
| TC-S5-18 | Registered device envelope is accepted            | Normal   |
| TC-S5-19 | Unknown device envelope is rejected               | Invalid  |
| TC-S5-20 | Disabled device envelope is rejected              | Invalid  |

### FR-S5-05 — Unknown Device Handling

| Test ID  | Description                                      | Category |
|----------|--------------------------------------------------|----------|
| TC-S5-21 | Unknown device telemetry is NOT persisted         | Invalid  |
| TC-S5-22 | Unknown device rejection is logged                | Invalid  |
| TC-S5-23 | Repeated unknown device does not crash pipeline   | Failure  |

### FR-S5-06 — Sensor Identity Validation

| Test ID  | Description                                      | Category |
|----------|--------------------------------------------------|----------|
| TC-S5-24 | Known device + known sensor is accepted           | Normal   |
| TC-S5-25 | Known device + unknown sensor is rejected         | Invalid  |
| TC-S5-26 | Known device + sensor belonging to other device   | Invalid  |

### FR-S5-07 — Real MQTT Integration

| Test ID  | Description                                      | Category |
|----------|--------------------------------------------------|----------|
| TC-S5-27 | Publisher → Mosquitto → Consumer → DB works       | Normal   |
| TC-S5-28 | Consumer reconnects after broker restart          | Recovery |
| TC-S5-29 | Malformed MQTT payload does not crash consumer    | Invalid  |
| TC-S5-30 | Multiple producers via broker simultaneously      | Concurrency |

### FR-S5-08 — Persistence Failure Handling

| Test ID  | Description                                      | Category |
|----------|--------------------------------------------------|----------|
| TC-S5-31 | DB unavailable → explicit failure (no silent OK)  | Failure  |
| TC-S5-32 | DB recovers → subsequent writes succeed           | Recovery |
| TC-S5-33 | Connection lost mid-write → failure reported      | Failure  |

### FR-S5-09 — Historical Query

| Test ID  | Description                                      | Category |
|----------|--------------------------------------------------|----------|
| TC-S5-34 | Query returns observations in timestamp order     | Normal   |
| TC-S5-35 | Query with no matches returns empty list          | Boundary |

### FR-S5-10 — Producer Compatibility

| Test ID  | Description                                      | Category |
|----------|--------------------------------------------------|----------|
| TC-S5-36 | Simulator envelopes still flow through pipeline   | Normal   |
| TC-S5-37 | Mock ESP32 publisher envelopes still flow         | Normal   |
| TC-S5-38 | All P1.S4 tests still pass (41/41)                | Regression |

### FR-S5-11 — Dashboard Compatibility

| Test ID  | Description                                      | Category |
|----------|--------------------------------------------------|----------|
| TC-S5-39 | Dashboard reads persisted telemetry via query API | Normal   |
| TC-S5-40 | Dashboard shows no SQL imports (arch test)        | Boundary |

### FR-S5-12 — NTP Decision

| Test ID  | Description                                      | Category |
|----------|--------------------------------------------------|----------|
| TC-S5-41 | NTP decision documented in ADR or sprint report   | Documentation |

---

## Scenario Matrix

| Test     | Scenario | Description                        | Expected             |
|----------|----------|------------------------------------|----------------------|
| TC-S5-27 | S1       | Single producer → broker → DB      | Envelope persisted   |
| TC-S5-27 | S2       | Simulator + ESP32 simultaneously   | Both persisted       |
| TC-S5-27 | S3       | Continuous telemetry (10+ msgs)    | All persisted        |
| TC-S5-27 | S4       | Burst telemetry (rapid fire)       | All persisted        |
| TC-S5-28 | S5       | Broker restart mid-stream          | Consumer reconnects  |
| TC-S5-28 | S6       | Consumer restart                   | Resumes consumption  |
| TC-S5-31 | S7       | DB down at startup                 | Explicit error       |
| TC-S5-31 | S8       | DB drops during ingestion          | Failure reported     |
| TC-S5-32 | S9       | DB recovers after outage           | Writes resume        |
| TC-S5-19 | S10      | Unknown device sends telemetry     | Rejected, not stored |
| TC-S5-25 | S11      | Known device, wrong sensor         | Rejected             |
| TC-S5-30 | S12      | 3 producers simultaneously         | All persisted        |

---

## Mandatory Scenario Categories Coverage

| Category          | Covered By                          |
|-------------------|-------------------------------------|
| Normal            | TC-S5-01..05, 07..10, 13..14, 18   |
| Invalid           | TC-S5-19..26, 29                    |
| Degraded          | TC-S5-20 (disabled device)          |
| Failure           | TC-S5-31..33                        |
| Recovery          | TC-S5-28, 32                        |
| Boundary          | TC-S5-06, 11, 15, 35, 40            |
| Concurrency       | TC-S5-30, S12                       |
| Regression        | TC-S5-38                            |
