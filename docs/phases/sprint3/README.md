# Sprint P1.S3 — Digital Asset Simulator & Telemetry Consumer

## 1. Purpose
The Digital Asset Simulator makes the Aegis world model come alive by generating configurable, deterministic, and temporally coherent synthetic observations.

It functions as a controlled digital environment designed to feed realistic, structured telemetry into the Aegis boundary without coupling to presentation layers or physical edge hardware.

---

## 2. Architecture: Decoupled Producer/Consumer

During this sprint, we implemented a strict **Producer/Consumer** architecture using a lightweight Inter-Process Communication (IPC) stream. This ensures the Dashboard never directly imports or controls the domain engine.

```text
┌────────────────────────────────────────┐       ┌────────────────────────────────────────┐
│               PRODUCER                 │       │               CONSUMER                 │
│       Standalone Simulator App         │       │          Telemetry Dashboard           │
│      (python -m apps.simulator)        │       │ (streamlit run apps/dashboard/app.py)  │
└───────────────────┬────────────────────┘       └───────────────────▲────────────────────┘
                    │                                                │
                    │  Serializes TelemetryEnvelope contracts        │ Reads & Deserializes
                    │  to JSON-lines IPC stream                      │ TelemetryEnvelopes
                    ▼                                                │
          ┌──────────────────────────────────────────────────────────┴───┐
          │    IPC Telemetry Stream Ledger (data/telemetry_stream.jsonl) │
          └──────────────────────────────────────────────────────────────┘
```

## 3. Physical Sensor Dynamics

To provide highly realistic multi-dimensional telemetry, the `SensorGenerator` implements:

1. **Mean-Reverting Physics**: Ornstein-Uhlenbeck processes simulate thermal and hydraulic inertia.
2. **Multi-Frequency Harmonics**: Stacked sinusoidal waves simulate rotating machinery (pumps/motors).
3. **Bidirectional Load Wander**: Values naturally drift up and down over long cycles, mimicking 
   changing industrial load requirements.
4. **Transient Spikes**: Occasional random up/down spikes with cooldown recoveries.

## 4. Operational Scenarios

- **NORMAL (ScenarioType.NORMAL)**:
  Produces steady-state operations within established baselines (e.g., Temp: 65-75°C, Vibration: 1.5-2.5 mm/s).
- **DEGRADATION (ScenarioType.DEGRADATION)**:
   Smoothly ramps up stress factors. Rather than a flat upward line, degradation injects amplified bidirectional 
   turbulence and shifts the baseline higher, eventually triggering QualityFlag.UNCERTAIN limits.

## 5. Running the System

### Terminal 1: Run the Simulator (Producer)

>Run infinitely, emitting data every 0.5 seconds:

```PowerShell
python -m apps.simulator --scenario degradation --interval 0.5
(Use --ticks 100 to run a fixed batch instead of an infinite loop).
```

### Terminal 2: Run the Live Dashboard (Consumer)
```PowerShell

streamlit run apps/dashboard/app.py
```

## 6. Limitations & Future Integration

- **No Live Transport**: MQTT brokers and HTTP ingestion boundaries are deferred to Sprint P1.S4.
- **In-Memory Only**: Persistent database storage (PostgreSQL/TimescaleDB) is not yet implemented.
- **No Real Hardware**: ESP32 integration is out of scope until Sprint P1.S4.

When MQTT is introduced in P1.S4, the IPC file (data/telemetry_stream.jsonl) will simply be replaced by an MQTT topic broker, requiring zero changes to our domain, contracts, or dashboard rendering logic.
