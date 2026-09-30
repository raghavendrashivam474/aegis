 Aegis — Architectural Boundaries & Technology Independence

## 1. The Core Dependency Inversion Rule

```text
Domain code must NEVER depend on infrastructure implementations.
```

### Prohibited Dependencies in Domain (packages/domain)

- ❌ No database packages (psycopg2, sqlalchemy, tortoise, etc.)
- ❌ No transport or broker clients (paho-mqtt, requests, aiohttp, httpx)
- ❌ No web or presentation frameworks (fastapi, starlette, pydantic, flask)
- ❌ No hardware-specific drivers (microdot, machine, etc.)

>The domain layer depends solely on Python's standard library and represents pure industrial operational truths.

## 2. Technology-Neutral Contract Flow

>Aegis handles telemetry identically regardless of whether the source is a physical edge device or a synthetic load simulator:

```text
┌───────────────────────────┐         ┌───────────────────────────┐
│       Physical Edge       │         │      Asset Simulator      │
│        (ESP32 Node)       │         │   (Synthetic Generator)   │
└─────────────┬─────────────┘         └─────────────┬─────────────┘
              │                                     │
              ▼                                     ▼
┌───────────────────────────┐         ┌───────────────────────────┐
│       Edge Adapter        │         │     Simulator Adapter     │
│ (Formats to TelemetryDTO) │         │ (Formats to TelemetryDTO) │
└─────────────┬─────────────┘         └─────────────┬─────────────┘
              │                                     │
              └──────────────────┬──────────────────┘
                                 ↓
              ┌─────────────────────────────────────┐
              │    Canonical TelemetryEnvelope      │
              │       (packages/contracts)          │
              └──────────────────┬──────────────────┘
                                 ↓
              ┌─────────────────────────────────────┐
              │          Aegis Core Boundary        │
              │         (packages/domain)           │
              └─────────────────────────────────────┘
```

## 3. Pluggable Infrastructure

>Infrastructure components sit strictly at the boundaries and implement domain-defined interfaces:

| Capability | Phase 1 Baseline Interface | Swappable Implementations |
| --- | --- | --- |
| **Telemetry Transport** | Telemetry Ingestion Contract | Mosquitto, HiveMQ, HTTP Webhook, Direct Memory Queue |
| **Persistence** | State Storage Port (P1.S2) | In-Memory (Dev), PostgreSQL / TimescaleDB (Prod) |
| **Edge Hardware** | Device Identity Contract | ESP32-WROOM, ESP32-S3, Raspberry Pi, Simulated Runtime |
