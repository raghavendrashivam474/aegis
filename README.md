 Aegis

> An intelligent autonomous industrial and IoT system designed for resilient observation, context-aware diagnosis, and operational integrity.

---

## Vision

Aegis is being engineered as an autonomous loop capable of observing physical and simulated environments, forming a verifiable world model, contextualizing anomalies, and taking verified actions:

```text
Observe
   ↓
Understand State
   ↓
Detect
   ↓
Contextualize
   ↓
Diagnose
   ↓
Decide
   ↓
Act
   ↓
Verify
   ↓
Evaluate / Evolve
```

---

## Current Status

* **Phase:** Phase 1 — Physical / Digital World
* **Sprint:** P1.S1 — Repository & Architecture Foundation
* **Status:** Foundation Complete

### Current Capability (Honest Assessment)
At the conclusion of **P1.S1**, the repository establishes architectural boundaries, data contract conventions, domain vocabulary definitions, verification tooling, and ADRs.

**What Aegis does NOT do yet:**
* It does NOT perform anomaly detection, classification, or machine learning.
* It does NOT perform real-time MQTT telemetry ingestion (planned for P1.S5).
* It does NOT execute simulated industrial loops (planned for P1.S3).
* It does NOT interface with physical ESP32 hardware firmware (planned for P1.S4).
* It does NOT execute autonomous actions or equipment control.

---

## Architecture

Aegis enforces a strict dependency inversion boundary: **Domain code never depends on infrastructure implementations.**

```text
┌──────────────────────────────┐
│          Interfaces          │
│ API / MQTT / UI / CLI / etc. │
└──────────────┬───────────────┘
               ↓
┌──────────────────────────────┐
│         Application          │
│       Use-case logic         │
└──────────────┬───────────────┘
               ↓
┌──────────────────────────────┐
│           Domain             │
│ World / Asset / Device / ... │
└──────────────────────────────┘
               ↑
┌──────────────┴───────────────┐
│       Infrastructure         │
│ DB / MQTT / devices / etc.   │
└──────────────────────────────┘
```

* **Technology Independence:** Telemetry sources (ESP32, Simulator, PLC, OPC UA) and infrastructure components (Mosquitto, Postgres, TimescaleDB) remain pluggable behind clean contract interfaces.

---

## Repository Structure

```text
aegis/
├── apps/
│   ├── backend/           # Future backend runtime & API services
│   ├── simulator/         # Future digital asset/industrial simulator
│   └── edge/              # Future physical edge device code (ESP32)
├── packages/
│   ├── contracts/         # Versioned, technology-neutral data contracts
│   └── domain/            # Core business concepts (World, Asset, Device, Sensor)
├── infrastructure/
│   ├── docker/            # Container and orchestration assets
│   └── config/            # Environment and deployment profiles
├── docs/
│   ├── architecture/      # Architectural blueprints and diagrams
│   ├── decisions/         # Architectural Decision Records (ADRs)
│   └── development/       # Local setup, standards, and contributor workflows
├── tests/                 # Unit, integration, and architecture contract tests
├── scripts/               # Developer automation and health-check scripts
├── .github/               # Continuous integration workflows
├── pyproject.toml         # Workspace tooling and test configuration
└── compose.yaml           # Local container topology blueprint
```

---

## Phase 1 Roadmap

```text
P1.S1  Repository & Architecture Foundation  ◄ (Current)
          ↓
P1.S2  World Model
          ↓
P1.S3  Digital Asset Simulator
          ↓
P1.S4  Physical Edge Node
          ↓
P1.S5  Common Telemetry Boundary
          ↓
P1.S6  Integrated World
```

---

## Development Setup

### 1. Prerequisites
* Python >= 3.11
* PowerShell or Bash
* Docker (optional for foundation check)

### 2. Verify Repository Health
Run the verification check script to ensure formatting, structure, and basic tests pass:

```powershell
# Run the local health check
.\scripts\check.ps1
```

### 3. Run Tests
```Bash
pytest
```

---

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
