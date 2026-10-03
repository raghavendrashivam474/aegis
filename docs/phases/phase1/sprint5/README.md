# P1.S5 — Persistent Telemetry & Device Registration

## Overview

P1.S5 evolves Aegis from a transient JSONL telemetry pipeline into a
persistent, identity-aware observability system.

## Architecture
```text
Simulator / ESP32 / Mock Producer
↓
MQTT (Mosquitto)
↓
Ingestion Adapter (apps/ingestion)
↓
TelemetryEnvelope (contracts)
↓
Device Validation (registry)
↓
Persistence Port (domain)
↓
PostgreSQL Adapter (infrastructure)
↓
Historical Query → Dashboard
```

## Key Boundaries

| Layer | Location | Responsibility |
|---|---|---|
| Contracts | `packages/contracts/` | TelemetryEnvelope v1 (unchanged) |
| Domain | `packages/domain/` | Entities, ports, validation (no infra) |
| Ingestion | `apps/ingestion/` | MQTT → Envelope → Validation → Sink |
| Persistence | `packages/domain/repository.py` (port) + adapter | Telemetry storage + retrieval |
| Dashboard | `apps/dashboard/` | Query consumer (no SQL) |

## Setup

### Prerequisites
- Python 3.11+
- Docker (for PostgreSQL + Mosquitto)

### Quick Start
```bash
# 1. Start infrastructure
docker compose up -d

# 2. Install dependencies
pip install -e ".[dev]"

# 3. Run migrations
python -m apps.backend.migrate

# 4. Register default devices
python -m apps.backend.seed_devices

# 5. Run tests
pytest -v

# 6. Start ingestion
python -m apps.ingestion

# 7. Start simulator
python -m apps.simulator --live

# 8. Start dashboard
streamlit run apps/dashboard/app.py
```
## Database

- **Technology**: PostgreSQL 16 (TimescaleDB extension available)
- **Schema**: See apps/backend/migrations/
- **Port**: TelemetryRepository (abstract) → PostgresTelemetryRepository (concrete)

## Device Registration

- **Registry**: DeviceRegistry port → PostgresDeviceRegistry adapter
- **Validation**: Every envelope checked before persistence
- **Unknown devices**: Rejected + logged (not silently stored)

## Testing

```Bash
pytest -v                    # All tests
pytest tests/test_s5_*.py    # P1.S5 only
pytest -m integration        # Real broker + DB tests
```

## Known Limitations

- **NTP synchronization**: [implemented | deferred — see ADR-008]
- **JSONL stream**: retained as [fallback | debug output] during transition
- TimescaleDB continuous aggregates: not yet configured

## P1.S6 Handoff

P1.S5 delivers persistent storage + identity validation.

P1.S6 can build on this for full Phase 1 operational showcase.

## Documentation
- Requirements
- Test Scenarios
- Post-Completion Report
