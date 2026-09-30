 Aegis — System Overview

## 1. System Vision

Aegis is an intelligent autonomous industrial/IoT operating architecture designed to close the loop between real-time telemetry observation and verified remediation actions.

### The Complete Autonomous Loop (Target Vision)

```text
┌────────────────────────────────────────────────────────┐
│                        Observe                         │
│       Capture physical & simulated telemetry           │
└──────────────────────────┬─────────────────────────────┘
                           ↓
┌────────────────────────────────────────────────────────┐
│                   Understand State                     │
│          Maintain real-time World Model                │
└──────────────────────────┬─────────────────────────────┘
                           ↓
┌────────────────────────────────────────────────────────┐
│                        Detect                          │
│          Identify anomalies & deviations               │
└──────────────────────────┬─────────────────────────────┘
                           ↓
┌────────────────────────────────────────────────────────┐
│                     Contextualize                      │
│       Correlate with operational topography            │
└──────────────────────────┬─────────────────────────────┘
                           ↓
┌────────────────────────────────────────────────────────┐
│                       Diagnose                         │
│           Determine root cause & severity              │
└──────────────────────────┬─────────────────────────────┘
                           ↓
┌────────────────────────────────────────────────────────┐
│                        Decide                          │
│          Formulate optimal policy/action               │
└──────────────────────────┬─────────────────────────────┘
                           ↓
┌────────────────────────────────────────────────────────┐
│                         Act                            │
│           Execute verified interventions               │
└──────────────────────────┬─────────────────────────────┘
                           ↓
┌────────────────────────────────────────────────────────┐
│                        Verify                          │
│         Confirm state recovery & stability             │
└──────────────────────────┬─────────────────────────────┘
                           ↓
┌────────────────────────────────────────────────────────┐
│                   Evaluate / Evolve                    │
│          Update operational knowledge base             │
└────────────────────────────────────────────────────────┘
```

## 2. Phase 1 Scope: Physical / Digital World

> Phase 1 focuses exclusively on the foundational intake loop:

```text
Physical World (ESP32)  ──┐
                          ├──► Telemetry Boundary ──► World Model Representation
Simulated World (Sim)   ──┘
```

>Phase 1 establishes the structural integrity of the world model and telemetry contracts before adding automated detection, ML, or autonomous actuation.

## 3. Top-Level Layer Architecture

```text
┌─────────────────────────────────────────────────────────────────┐
│                           INTERFACES                            │
│    REST APIs (FastAPI)  │  MQTT Ingestion  │  CLI  │  UI        │
└────────────────────────────────┬────────────────────────────────┘
                                 ↓
┌─────────────────────────────────────────────────────────────────┐
│                       APPLICATION LAYER                         │
│    Observation Ingestion  │  State Queries  │  Workflows        │
└────────────────────────────────┬────────────────────────────────┘
                                 ↓
┌─────────────────────────────────────────────────────────────────┐
│                          DOMAIN LAYER                           │
│   World  │  Asset  │  Device  │  Sensor  │  Observation Rules   │
│   (Pure Python Standard Library — Zero Infrastructure Coupling) │
└─────────────────────────────────────────────────────────────────┘
                                 ▲
┌────────────────────────────────┴────────────────────────────────┐
│                      INFRASTRUCTURE LAYER                       │
│  PostgreSQL / TimescaleDB  │  Mosquitto MQTT  │  Docker Engine  │
└─────────────────────────────────────────────────────────────────┘
```