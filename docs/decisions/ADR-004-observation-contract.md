 ADR-004 — Observation and Telemetry Interchange Contracts

## Status
Accepted

## Context
Aegis will receive data from both simulated assets (P1.S3) and physical edge hardware (ESP32 in P1.S4). A uniform, stable contract is required so the ingestion and domain systems do not distinguish between physical and virtual data producers.

## Decision
We define versioned data contracts in `packages/contracts` centered on:
* `ObservationPayload`: Single point-in-time sensor measurement.
* `TelemetryEnvelope`: Standard container bundling observations with device identity, timestamps, and an explicit `schema_version: "v1"`.

The contracts are protocol-agnostic. Adapters at the edge/transport boundary convert specific wire protocols (MQTT payloads, HTTP JSON, etc.) into these contract envelopes.

## Alternatives Considered
1. **Direct MQTT topic parsing in backend services:** Rejected because it couples ingestion to a specific topic hierarchy and message format.
2. **Binary serialization (Protobuf / FlatBuffers / CBOR):** Deferred. JSON-compatible schema dictionaries provide easier initial debugging and inspection during Phase 1.

## Consequences
* **What it enables:** Seamless simulation-to-real migration; tests can mock telemetry using simple dictionary fixtures conforming to the contract.
* **What it makes harder:** Slightly higher payload size over the wire compared to raw binary telemetry (acceptable for initial phase).

## Revisit Conditions
Reconsider binary serialization (e.g., Protobuf/CBOR) in P1.S4/P1.S5 if ESP32 network bandwidth or payload memory becomes a bottleneck.
