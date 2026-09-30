# ADR-007: Transport-Agnostic Ingestion Boundary & Edge Node Integration

## Status
Accepted

## Context
In Sprint P1.S4, we introduced the first physical edge producer (ESP32 node with environmental and vibration sensors) and an MQTT messaging transport.

A common anti-pattern in IoT platforms is allowing transport protocols (such as MQTT topics, client reconnection logic, or binary serialization specifics) to bleed into the core business domain or presentation dashboards. Furthermore, directly coupling edge nodes to presentation layers prevents seamless switching between physical and digital twins.

## Decision
We decided to introduce a dedicated **Ingestion Adapter layer (`apps/ingestion`)** that acts as an isolated transport boundary:

1. **Protocol Decoupling**: All MQTT subscription, network reconnection, and paho-mqtt dependencies are strictly confined to `apps/ingestion`. The core domain (`packages/domain`) contains zero networking code.
2. **Strict Contract Validation**: Incoming raw payloads from MQTT topics (e.g. `aegis/telemetry/#`) are parsed and validated through `TelemetryDecoder` into strongly-typed `TelemetryEnvelope` (v1) contracts. Malformed payloads or invalid schemas are rejected with warnings without terminating the consumer process.
3. **Multi-Producer Convergence**: The ingestion bridge outputs validated `TelemetryEnvelope` records directly to the shared Aegis telemetry sink (`data/telemetry_stream.jsonl`). As a result, both the Digital Twin Simulator and Physical ESP32 Edge Nodes stream through the identical downstream boundary, and the Dashboard consumes them without knowledge of the transport mechanism.

## Alternatives Considered

### Option A: Direct Broker Polling in Dashboard (Streamlit MQTT Client)
- **Pros**: Fewer processes to run concurrently during local testing.
- **Cons**: Binds UI rendering lifecycle directly to transport packet arrival. Violates single-responsibility principle.
- **Verdict**: Rejected.

### Option B: MQTT Logic inside Domain Layer (`packages/domain/mqtt.py`)
- **Pros**: Co-locates all system logic in one package.
- **Cons**: Destroys domain purity and introduces infrastructure dependencies into pure Python domain models.
- **Verdict**: Rejected.

### Option C: Standalone Ingestion Adapter (`apps/ingestion`)
- **Pros**: Pure separation of concerns; domain and UI remain 100% transport agnostic; supports multiple simultaneous heterogeneous producers (ESP32, Simulator, future PLCs); easy to swap broker or replace IPC sink with Kafka/PostgreSQL in future sprints.
- **Cons**: Requires running the ingestion process alongside the broker.
- **Verdict**: **Accepted**.

## Consequences
- **Zero Domain Contamination**: `packages/domain` remains completely free of any `paho-mqtt` or networking imports.
- **Interchangeable Producers**: The dashboard and future consumers treat physical edge nodes and simulated digital twins identically.
- **Robust Error Handling**: Hardware faults or corrupt payloads from external nodes are caught at the perimeter and cannot crash the core pipeline.
