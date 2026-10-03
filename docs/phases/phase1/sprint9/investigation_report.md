# P1.S9 Investigation Report — Architecture & Dataset Analysis

**Date:** 2026-10-03
**Sprint:** P1.S9 — Real-World Dataset Integration
**Status:** Investigation Complete — Ready for Implementation

---

## 1. Current Telemetry Flow (Verified from Source)

```text
Producer (Simulator / ESP32 / Dataset)
│
│ Constructs TelemetryEnvelope:
│ schema_version: "v1"
│ source_device_id: str
│ sent_at_iso: str (ISO-8601)
│ observations: list[ObservationPayload]
│ metadata: dict
│
▼
MQTT Transport (topic: aegis/telemetry/#)
│
▼
MqttTelemetryConsumer.process_raw_message()
│ TelemetryDecoder.decode(payload) → TelemetryEnvelope
│
▼
TelemetryIngestionPipeline.process_envelope(envelope)
│ 1. registry.is_registered(device_id) → reject if unknown
│ 2. device.status == ACTIVE → reject if inactive
│ 3. registry.validate_sensor_association() → reject if mismatch
│ 4. ObservationMapper.to_domain(payload) → Observation
│ 5. repository.save_batch(observations) → PostgreSQL
│ 6. retry_buffer on transient failure → dead-letter on exhaustion
│
▼
PostgresTelemetryRepository.save_batch()
│ INSERT INTO aegis_telemetry_observations
│
▼
TelemetryQueryService.get_device_history()
│
▼
Dashboard (Streamlit) — zero SQL, query service only
```

## 2. Existing Contracts (Exact Shapes)

### TelemetryEnvelope (packages/contracts/models.py)
| Field | Type | Required | Notes |
|-------|------|----------|-------|
| schema_version | str | Yes | Must be "v1" |
| source_device_id | str | Yes | Must match DeviceRegistry |
| sent_at_iso | str | Yes | ISO-8601 UTC |
| observations | list[ObservationPayload] | Yes | 1+ per envelope |
| metadata | dict | No | Source, transport, seq info |

### ObservationPayload (packages/contracts/models.py)
| Field | Type | Required | Notes |
|-------|------|----------|-------|
| observation_id | str | Yes | Unique per observation |
| sensor_id | str | Yes | Must be registered to device |
| timestamp_iso | str | Yes | ISO-8601 UTC |
| value | float | Yes | Numeric measurement |
| unit | str | Yes | e.g. "celsius", "mm/s" |
| quality | str | No | GOOD/UNCERTAIN/BAD/CALIBRATION |
| metadata | dict | No | Arbitrary context |

### Domain Observation (packages/domain/entities.py)
| Field | Type | Notes |
|-------|------|-------|
| observation_id | str | Frozen dataclass |
| device_id | str | Parent device |
| sensor_id | str | Parent sensor |
| timestamp | datetime | Parsed from ISO |
| value | float | Measurement |
| unit | str | Unit string |
| quality | QualityFlag | Enum |
| metadata | dict | Cleaned of device_id |

### ObservationMapper (packages/contracts/mappers.py)
- `to_contract(Observation) → ObservationPayload` — domain to wire format
- `to_domain(ObservationPayload, device_id) → Observation` — wire to domain
- **Key detail:** device_id is extracted from payload.metadata["device_id"] or explicit arg
- **Key detail:** timestamp parsing falls back to datetime.now(UTC) on failure
- **Key detail:** quality parsing falls back to GOOD on unknown values

## 3. Existing Producer Patterns

### Simulator (apps/simulator/simulator.py) — PRIMARY TEMPLATE
- Builds WorldModel: World → Asset → Device → Sensor
- Per tick: generates Observation per sensor, groups by device_id
- Maps via `ObservationMapper.to_contract(obs)` → ObservationPayload
- Creates TelemetryEnvelope per device per tick
- **This is the pattern the dataset adapter must follow**

### ESP32 Mock (scripts/mock_esp32_publisher.py)
- Constructs envelope dict manually (JSON)
- Publishes directly to MQTT via paho client
- Simpler pattern — no domain model, just wire format
- Good reference for MQTT publishing mechanics

### Critical Observation
Both producers create **one envelope per device per time-step**, containing
all sensor observations for that device. The dataset adapter should do the same:
group dataset rows by (device_id, timestamp) into single envelopes.

## 4. Registration Requirements

The ingestion pipeline **permanently rejects** telemetry from:
- Unknown device_id (not in DeviceRegistry)
- Inactive devices (status != ACTIVE)
- Unregistered sensor_id (not associated with device)

**Therefore:** Before replaying any dataset, the adapter MUST:
1. Register each dataset "machine" as a Device in DeviceRegistry
2. Register each dataset "sensor column" as a Sensor under that Device
3. Ensure device status is ACTIVE

## 5. Dataset Candidate Evaluation

### Candidate A: NASA C-MAPSS FD001 (Turbofan Degradation) ★ SELECTED
| Criterion | Assessment |
|-----------|------------|
| Source | NASA Prognostics Data Repository |
| Equipment | Turbofan jet engines |
| Records | ~20,631 rows (FD001 train) |
| Units | 100 engines (unit_id 1–100) |
| Sensors | 21 sensor columns (T, P, flow, speed) |
| Timestamps | Cycle number (sequential, no wall-clock) |
| Degradation | Yes — engines degrade to failure |
| License | NASA open data, no restrictions |
| Aegis mapping | Excellent — temp, pressure, vibration-like signals |
| Phase 2 value | Very high — degradation → anomaly detection |

### Candidate B: AI4I 2020 Predictive Maintenance (UCI)
| Criterion | Assessment |
|-----------|------------|
| Source | UCI Machine Learning Repository |
| Equipment | Milling machine (synthetic) |
| Records | 10,000 rows |
| Units | Single machine |
| Sensors | Air temp, process temp, rotational speed, torque, tool wear |
| Timestamps | None (sequential index) |
| Degradation | Binary failure labels |
| License | CC BY 4.0 |
| Aegis mapping | Good but single device limits multi-device proof |

### Candidate C: NAB (Numenta Anomaly Benchmark)
| Criterion | Assessment |
|-----------|------------|
| Source | Numenta |
| Equipment | IT infrastructure (CPU, traffic, temperature) |
| Records | Varies per file |
| Units | Single metric per file |
| Sensors | 1 per file |
| Timestamps | Real wall-clock timestamps |
| Degradation | Anomaly labels |
| License | MIT |
| Aegis mapping | Poor — not industrial, single-sensor files |

### Selection Rationale
**NASA C-MAPSS FD001** is selected because:
1. Multiple engines (100) → proves multi-device ingestion
2. 21 sensors → maps to temperature, pressure, vibration categories
3. Degradation trajectory → directly feeds Phase 2 anomaly detection
4. Well-documented, widely used in prognostics research
5. Manageable size (~20K rows) for sprint scope
6. Cycle-based timestamps → tests historical time handling

## 6. C-MAPSS → Aegis Field Mapping (Preliminary)

### Identity Mapping
| C-MAPSS Field | Aegis Concept | Notes |
|---------------|---------------|-------|
| unit_number | device_id | "engine-001" through "engine-100" |
| (implicit) | asset_id | "asset-turbofan-fleet" |
| (implicit) | asset_type | "turbofan_engine" |

### Sensor Mapping (21 sensors → Aegis categories)
| C-MAPSS Column | Physical Meaning | Aegis sensor_id | measurement_type | unit |
|----------------|-----------------|-----------------|------------------|------|
| T2 | Total temp at fan inlet | sensor-t2-inlet | temperature | K |
| T24 | Total temp at LPC outlet | sensor-t24-lpc | temperature | K |
| T30 | Total temp at HPC outlet | sensor-t30-hpc | temperature | K |
| T50 | Total temp at LPT outlet | sensor-t50-lpt | temperature | K |
| P2 | Pressure at fan inlet | sensor-p2-inlet | pressure | psi |
| P15 | Total pressure in bypass | sensor-p15-bypass | pressure | psi |
| P30 | Total pressure at HPC outlet | sensor-p30-hpc | pressure | psi |
| Nf | Physical fan speed | sensor-nf-fan | rotational_speed | rpm |
| Nc | Physical core speed | sensor-nc-core | rotational_speed | rpm |
| epr | Engine pressure ratio | sensor-epr | pressure_ratio | ratio |
| Ps30 | Static pressure at HPC outlet | sensor-ps30 | pressure | psi |
| phi | Ratio of fuel flow to Ps30 | sensor-phi | flow_ratio | ratio |
| NRf | Corrected fan speed | sensor-nrf | rotational_speed | rpm |
| NRc | Corrected core speed | sensor-nrc | rotational_speed | rpm |
| BPR | Bypass ratio | sensor-bpr | ratio | ratio |
| farB | Burner fuel-air ratio | sensor-farb | ratio | ratio |
| htBleed | Bleed enthalpy | sensor-htbleed | enthalpy | kJ/kg |
| Nf_dmd | Demanded fan speed | sensor-nf-dmd | rotational_speed | rpm |
| PCNfR_dmd | Demanded corrected fan speed | sensor-pcnfr-dmd | rotational_speed | rpm |
| W31 | HPT coolant bleed | sensor-w31 | flow | lbm/s |
| W32 | LPT coolant bleed | sensor-w32 | flow | lbm/s |

### Timestamp Handling
| C-MAPSS Field | Aegis Concept | Notes |
|---------------|---------------|-------|
| time_in_cycles | observation.timestamp | Synthetic: 2026-01-01T00:00:00Z + cycle * 1min |
| (ingestion time) | sent_at_iso | datetime.now(UTC) at replay time |

**Critical:** C-MAPSS has no wall-clock timestamps. We will synthesize
deterministic timestamps from cycle numbers to preserve ordering and
enable time-based queries. This tests the "historical time" requirement
without pretending the data has real wall-clock provenance.

## 7. Proposed Adapter Architecture

```text
datasets/cmapss_fd001/
train_FD001.txt ← raw dataset (not in git)
manifest.yaml ← provenance + metadata

apps/dataset_replay/
init.py
adapter.py ← CmapssAdapter: reads, maps, creates envelopes
replay.py ← ReplayEngine: timing control, MQTT publish
registration.py ← registers dataset devices in DeviceRegistry
config.py ← DatasetReplayConfig
```

### Adapter Flow
1. Read train_FD001.txt (space-delimited)
2. Parse columns: unit_number, cycle, setting1-3, sensor1-21
3. Group by (unit_number, cycle)
4. For each group:
   a. Map unit_number → device_id ("engine-XXX")
   b. Map sensor columns → ObservationPayload list
   c. Synthesize timestamp from cycle number
   d. Create TelemetryEnvelope(schema_version="v1", ...)
5. Publish envelope via MQTT (or direct pipeline injection for tests)

### What the adapter does NOT do
- No direct PostgreSQL writes
- No SQL
- No dashboard modifications
- No new telemetry schema
- No anomaly detection
- No bypass of DeviceRegistry
- No bypass of ingestion validation

## 8. Genuine Architectural Gaps Identified

**None.** The existing architecture fully supports this integration.

The TelemetryEnvelope contract is source-agnostic by design.
The ingestion pipeline validates by device/sensor identity, not by source.
The simulator already proves the producer → envelope → pipeline pattern works.

No ADR is needed for P1.S9.

## 9. Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| 100 engines × 21 sensors = 2100 sensor registrations | Batch registration script, run once before replay |
| Cycle-based timestamps may confuse time-range queries | Document synthetic time base; use deterministic offset |
| Large replay may overwhelm MQTT broker | Default to bounded sample (e.g., 5 engines, 50 cycles) |
| Dataset file not in git | manifest.yaml tracks provenance; .gitignore raw data |

## 10. Next Steps

1. ✅ Investigation report (this document)
2. → Dataset evaluation matrix (dataset_evaluation.md)
3. → Download C-MAPSS FD001 and create manifest
4. → Implement device/sensor registration script
5. → Implement CmapssAdapter
6. → Implement ReplayEngine (bounded mode first)
7. → Write tests (scenarios A–G from brief)
8. → Write showcase_p1_s9.py
9. → Verify regression suite green
