 Aegis Data Contracts Package

This package defines versioned, technology-neutral data interchange contracts shared across Aegis sub-systems (Edge firmware, Simulators, Ingestion pipelines, and Backend runtimes).

## Core Principles

1. **Protocol Independence:** Contracts describe *what* is exchanged, not *how* it travels (MQTT, HTTP, WebSockets, IPC).
2. **Explicit Versioning:** Every wire payload contract carries an explicit `schema_version` to support backwards compatibility and schema evolution.
3. **Decoupled from Infrastructure:** Zero dependencies on external frameworks or network transport packages.
4. **Boundary Adapters:** Physical devices (ESP32) and Simulators convert their raw payload formats into these standard contract envelopes before passing them into the Aegis boundary.

## Contract Catalog (v1)

* `DeviceIdentity`: Hardware and logical device identifier metadata.
* `SensorIdentity`: Transducer descriptor and unit specification.
* `ObservationPayload`: Single point-in-time sensor measurement contract.
* `TelemetryEnvelope`: Standard transport envelope bundling one or more observation payloads with routing and timestamp metadata.
