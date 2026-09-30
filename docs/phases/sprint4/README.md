# Sprint P1.S4 — Physical Edge Node & Transport Ingestion Bridge

## 1. Purpose
Sprint P1.S4 proves that the Aegis core architecture is completely independent of the telemetry source. We introduce a real physical edge producer (ESP32 microcontroller with temperature, humidity, and vibration telemetry) and an MQTT ingestion boundary while preserving every existing Aegis contract, domain invariant, simulator capability, and dashboard view.

---

## 2. Target Architecture: Multi-Producer Convergence

Both digital twin simulators and physical hardware nodes publish telemetry into the exact same Aegis pipeline without coupling to presentation or storage layers:

```text
       DIGITAL WORLD                                  PHYSICAL WORLD
 ┌───────────────────────┐                      ┌────────────────────────┐
 │ Digital Twin Sim      │                      │ ESP32 Hardware Node    │
 │ (apps.simulator)      │                      │ (edge/esp32)           │
 └──────────┬────────────┘                      └───────────┬────────────┘
            │                                               │
            │ Direct Envelope Mapping                       │ MQTT Transport
            ▼                                               ▼
 ┌───────────────────────┐                      ┌────────────────────────┐
 │ TelemetryEnvelope     │                      │ Mosquitto Broker       │
 │ Contract (v1)         │                      │ (port 1883)            │
 └──────────┬────────────┘                      └───────────┬────────────┘
            │                                               │
            │                                               ▼
            │                                   ┌────────────────────────┐
            │                                   │ MQTT Ingestion Bridge  │
            │                                   │ (apps.ingestion)       │
            │                                   └───────────┬────────────┘
            │                                               │
            │                                               │ Decodes & Validates
            ▼                                               ▼
 ┌───────────────────────────────────────────────────────────────────────┐
 │               Unified Telemetry Sink (data/telemetry_stream.jsonl)    │
 └───────────────────────────────────┬───────────────────────────────────┘
                                     │
                                     ▼
                        ┌────────────────────────┐
                        │ Live Streamlit UI      │
                        │ (apps.dashboard)       │
                        └────────────────────────┘
```

## 3. Key Components Delivered

### 1. Ingestion Adapter (`apps/ingestion`)

- **`TelemetryDecoder`**: Validates raw incoming JSON against the TelemetryEnvelope (v1) contract.
   Rejects non-UTF8, empty, malformed, or invalid payloads safely without crashing the service.
- **`MqttTelemetryConsumer`**: Manages MQTT connection lifecycle, topic subscription
   (aegis/telemetry/#), and forwards valid envelopes to the Aegis sink.
- **`IngestionConfig`**: Fully configurable broker endpoints via environment variables or CLI flags
   (AEGIS_MQTT_HOST, AEGIS_MQTT_PORT, AEGIS_MQTT_TOPIC).

### 2. Physical ESP32 Edge Firmware (`edge/esp32`)

- **`config.h`**: Wi-Fi credentials, broker endpoints, and stable identity mappings (device-esp32-01,
   sensor-temp-esp32-01, sensor-humidity-esp32-01, sensor-vibration-esp32-01).
- **`main.cpp`**: PlatformIO/Arduino C++ implementation with Wi-Fi auto-reconnect, MQTT transport,
   sensor acquisition (or fallback internal dynamics), and JSON serialization compliant with TelemetryEnvelope v1.
- **`platformio.ini`**: Build definition targeting standard esp32dev boards.

### 3. Mock Edge Publisher (`scripts/mock_esp32_publisher.py`)

Emulates identical binary and network behavior of the ESP32 firmware for automated CI pipelines and environments without live hardware attached.

### 4. Additive Dashboard Evolution (`apps/dashboard`)

Non-breaking extension: added live producer origin tags ([physical_esp32], [simulator]) and an ambient humidity chart tab.

## 4. Verification & Testing

The test suite expanded from 28 to 41 passing tests (13 new verification tests added in Sprint 4):

| Test Category | Coverage | Status |
| --- | --- | --- |
| **Contract Ingestion** | Valid payload parsing, empty payload rejection, malformed JSON recovery, schema validation | ✅ PASS |
| **Pipeline Safety** | Custom sink integration, dropped message counters, UTF-8 enforcement | ✅ PASS |
| **Domain Purity** | Strict boundary scan ensuring zero paho/mqtt imports in packages/domain | ✅ PASS |
| **Simulator Baseline** | All 10 existing simulation and scenario tests preserved without regression | ✅ PASS |
| **World Model Baseline** | Invariant rules, hierarchy transitions, entity indexes intact | ✅ PASS |

## 5. How to Run the System

### Option A: Complete Automated Showcase

Run the automated end-to-end multi-producer convergence showcase:

```PowerShell
python scripts/showcase_p1_s4.py
```

### Option B: Live Multi-Terminal Demonstration

#### Terminal 1 — MQTT Broker (Mosquitto):

```PowerShell
mosquitto -v
```

#### Terminal 2 — Ingestion Bridge:

```PowerShell
python -m apps.ingestion --reset-sink
```

#### Terminal 3 — Physical Edge Node or Mock Producer:

```PowerShell
# If using physical hardware: Power on the ESP32 node
# If using mock edge publisher:
python scripts/mock_esp32_publisher.py --interval 1.0
```

#### Terminal 4 — Digital Twin Simulator (Optional Co-Producer):

```PowerShell
python -m apps.simulator --live --scenario normal
```

#### Terminal 5 — Live Dashboard:

```PowerShell
streamlit run apps/dashboard/app.py
```

## 6. Resilience & Failure Handling

- **Broker Offline**: The Ingestion Bridge and ESP32 nodes gracefully detect connection loss, log non-
  fatal warnings, and automatically attempt reconnections without crashing.
- **Malformed MQTT Payloads**: The `TelemetryDecoder` traps invalid JSON and contract violations,
  increments `invalid_count`, and discards the message while continuing to process future messages.
- **Hardware Fallback**: If physical edge hardware disconnects, the digital twin simulator can immediately
   provide telemetry fallback without modifying the dashboard or backend.

## 7. Deferred to Sprint P1.S5

- Persistent database storage (PostgreSQL/TimescaleDB time-series ingestion).
- Bidirectional command & control topics (aegis/commands/#).
- Cryptographic device authentication (TLS/mTLS x509 edge certificates).
