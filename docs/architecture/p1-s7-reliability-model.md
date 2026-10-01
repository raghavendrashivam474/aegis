# Aegis Architecture — P1.S7 Reliability & Failure Model

## 1. Executive Summary

P1.S6 proved the complete end-to-end operational pipeline across all layers (Simulator -> MQTT -> Ingestion -> PostgreSQL -> QueryService -> Dashboard).
P1.S7 hardens this pipeline against infrastructure instability, network partitions, unannounced restarts, producer bursts, and persistence failures without modifying pure domain entities or contracts.

---

## 2. Ingestion & Persistence Failure Taxonomies

We categorize all runtime failures into two distinct classes:

```text
                                Incoming Telemetry
                                        │
                                        ▼
                             [ Contract Decoding ] ──(Malformed JSON/Schema)──► [ REJECT / BAD CONTRACT ]
                                        │
                                        ▼
                             [ Identity Validation ] ──(Unknown Device / Inactive)──► [ REJECT / INVALID IDENTITY ]
                                        │
                                        ▼
                             [ Sensor Validation ] ──(Sensor Not On Device)──► [ REJECT / SENSOR MISMATCH ]
                                        │
                                        ▼
                                [ Valid Domain Obs ]
                                        │
                                        ▼
                             [ Persistence Attempt ]
                                  │           │
                          (Success)           (Infrastructure Failure: DB Down / Pool Exhausted)
                                  │           │
                                  ▼           ▼
                           [ PostgreSQL ]  [ Bounded Reliability Buffer ]
                                              │
                                              ├── (Retry on recovery) ──► [ PostgreSQL ]
                                              └── (Retry Limit Reached) ──► [ DEAD-LETTER SINK ]
```

### 2.1 Permanent Rejections (Non-Retryable)

These errors represent structural, cryptographic, or contract violations. Retrying them is futile and would poison processing queues:

- **TelemetryDecodeError**: Invalid UTF-8, malformed JSON, schema version incompatibility, or missing mandatory contract fields.
- **UnknownDeviceError**: Device ID not found in `DeviceRegistry`.
- **InactiveDeviceError**: Device operational status is `INACTIVE`.
- **SensorAssociationError**: Sensor ID does not belong to the claiming device in `DeviceRegistry`.
- **Resolution**: Immediate rejection, logged with WARNING/SECURITY, count incremented, non-retryable.

### 2.2 Transient Failures (Retryable)

These errors represent infrastructure unavailability where the telemetry payload itself is completely valid:

- **PostgresConnectionError / psycopg.OperationalError**: Connection reset, DB restarting, pool exhaustion 
    timeout, network partition.
- **PostgresPoolTimeout**: Connection pool saturation under high concurrency.
- **MqttBrokerUnavailable**: Broker offline or restarting during publish/subscribe.

#### Resolution:

- **Ingestion**: Payload entered into bounded in-memory PersistenceRetryBuffer.
- **Publisher**: Acknowledged delivery (QoS 1) with retry/wait semantics.

## 3. Buffer, Retry & Dead-Letter Semantics

### 3.1 Persistence Retry Buffer Policies

- **MAX_BUFFER_SIZE**: Bounded capacity (default: 1,000 envelopes).
- **RETRY_LIMIT**: Max delivery attempts per envelope (default: 3 attempts).
- **BACKOFF_POLICY**: Configurable backoff (immediate retry on DB recovery notification or periodic drain).
- **OVERFLOW_POLICY**: When buffer reaches capacity under sustained DB downtime:
        - `DROP_OLDEST` (default for real-time telemetry freshness) or `REJECT_NEWEST`.

### 3.2 Dead-Letter Policy

- Envelopes exceeding `RETRY_LIMIT` are routed to the Dead-Letter handler (`DeadLetterSink` / file / log audit).
- Zero silent dropping: every envelope is either persisted, actively buffered, or formally dead-lettered with root-cause reason.

## 4. PostgreSQL Connection Pool Design

### 4.1 Boundary Preservation

- Domain repository contracts (`DeviceRegistry`, `TelemetryRepository`) remain 100% pure and untouched.
- `PostgresConnectionPool` manages bounded `psycopg_pool.ConnectionPool` instances with health check and auto-recovery.
- Adapters acquire connections via context managers from the pool rather than spawning ad-hoc TCP connections per query.

## 5. MQTT Delivery & Reconnection Semantics

### 5.1 QoS 1 Delivery Handshake

- Upgrade publishing and subscription to QoS 1 (at-least-once).
- Producers monitor `MQTTMessageInfo.wait_for_publish(timeout)` instead of artificial `time.sleep()`.

### 5.2 Broker Reconnection

- Consumers implement graceful `on_disconnect` / `on_connect` state handling with automatic subscription re-establishment.
