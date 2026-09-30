# ADR-006: Decoupled Telemetry Stream Architecture (Producer / Consumer)

## Status
Accepted

## Context
In Sprint P1.S3 (Digital Asset Simulator), we required a runnable simulation engine to generate synthetic physical observations and a web dashboard to visualize live operational metrics.

Initial prototypes instantiated the Simulator aggregate directly inside the Streamlit dashboard process. This introduced tight monolithic coupling, where the UI thread directly controlled domain ticks and simulation state rather than consuming contracts asynchronously across a boundary.

## Decision
We decided to decouple the simulator and dashboard into two independent OS processes using a file-based JSON-lines Inter-Process Communication (IPC) stream:

1. **Producer Process (pps.simulator)**: Runs independently (e.g. python -m apps.simulator), generates observations, validates domain invariants, maps them to TelemetryEnvelope contracts, and appends serialized JSON envelopes to data/telemetry_stream.jsonl.
2. **Consumer Process (pps.dashboard)**: Runs independently (e.g. streamlit run apps/dashboard/app.py), polls data/telemetry_stream.jsonl, deserializes TelemetryEnvelope objects, and updates UI charts in real time.

## Alternatives Considered

### Option A: Monolithic UI (In-Memory Simulator Invocation)
- **Pros**: Single command startup, no file I/O overhead.
- **Cons**: Blurs the boundary between domain simulation and presentation. Does not model real-world edge/cloud separation.
- **Verdict**: Rejected.

### Option B: Early Database Integration (SQLite / PostgreSQL)
- **Pros**: Persistent storage, SQL query flexibility.
- **Cons**: Introduces premature infrastructure dependencies before Phase 1 persistence sprint.
- **Verdict**: Deferred.

### Option C: File-Based JSON-Lines IPC Stream (data/telemetry_stream.jsonl)
- **Pros**: Technology-neutral, zero third-party database dependencies, mimics streaming message queues (Kafka/MQTT), enforces pure contract serialization/deserialization.
- **Cons**: Requires two open terminal sessions during local showcase runs.
- **Verdict**: **Accepted**.

## Consequences
- **Architectural Boundary Intact**: packages/domain remains untouched and completely isolated from presentation code.
- **Contract Proof**: Proves that TelemetryEnvelope (v1) contracts successfully bridge independent application processes.
- **Seamless Upgrade Path**: When MQTT is introduced in Sprint P1.S4, the IPC stream file sink will be replaced by an MQTT topic broker, requiring **zero changes** to contracts, domain models, or dashboard visualizers.
