# P1.S9 Dataset Evaluation Matrix

**Date:** 2026-10-03
**Sprint:** P1.S9 — Real-World Dataset Integration
**Decision:** NASA C-MAPSS FD001 selected

---

## 1. Evaluation Criteria

Each candidate is assessed against two categories:

### Technical Suitability
- **Real industrial data:** Originates from actual or high-fidelity simulated industrial equipment
- **Timestamp quality:** Presence, resolution, and ordering of temporal markers
- **Sensor breadth:** Number and variety of measurable physical quantities
- **Asset/device identity:** Whether individual equipment units are distinguishable
- **Sampling consistency:** Regular vs irregular sampling intervals
- **Dataset size:** Manageable within a single sprint (~10K–100K rows ideal)
- **Signal variation:** Sufficient dynamic range to exercise validation and quality logic

### Aegis Compatibility
- **Temperature signals:** Mappable to Aegis temperature observation type
- **Pressure signals:** Mappable to Aegis pressure observation type
- **Vibration/rotational signals:** Mappable to Aegis vibration or rotational observation types
- **Multi-device proof:** Supports registering multiple distinct devices
- **Degradation trajectory:** Contains progressive behavioral change useful for Phase 2
- **Mapping complexity:** Effort required to translate dataset schema to Aegis contracts
- **Provenance clarity:** Well-documented source, license, and methodology

---

## 2. Candidate Comparison

| Criterion | A: NASA C-MAPSS FD001 | B: AI4I 2020 (UCI) | C: NAB (Numenta) |
|-----------|----------------------|---------------------|-------------------|
| **Source** | NASA Prognostics CoE | UCI ML Repository | Numenta Inc. |
| **Equipment** | Turbofan jet engines | Milling machine (synthetic) | IT servers, AWS, traffic |
| **Real industrial** | ✅ High-fidelity simulation | ⚠️ Synthetic | ❌ IT infrastructure |
| **Total records** | ~20,631 | 10,000 | ~7,000–130,000 per file |
| **Distinct units** | 100 engines | 1 machine | 1 metric per file |
| **Sensor count** | 21 continuous | 5 continuous | 1 per file |
| **Temperature** | ✅ T2, T24, T30, T50 | ✅ Air temp, process temp | ⚠️ Some files |
| **Pressure** | ✅ P2, P15, P30, Ps30 | ❌ | ❌ |
| **Vibration/rotation** | ✅ Nf, Nc, NRf, NRc | ✅ Rotational speed | ❌ |
| **Timestamp type** | Cycle number (ordinal) | None (index) | ✅ Real wall-clock |
| **Timestamp quality** | ⚠️ Synthetic, monotonic | ❌ None | ✅ High quality |
| **Sampling** | Uniform (1/cycle) | Uniform (1/row) | Irregular |
| **Degradation** | ✅ Progressive to failure | ⚠️ Binary failure labels | ⚠️ Anomaly labels |
| **Multi-device** | ✅ 100 engines | ❌ Single machine | ❌ Single metric |
| **License** | NASA open (no restriction) | CC BY 4.0 | MIT |
| **Provenance** | ✅ Peer-reviewed, cited | ✅ UCI documented | ✅ Numenta documented |
| **File format** | Space-delimited text | CSV | CSV |
| **File size** | ~2.5 MB | ~1.2 MB | Varies |
| **Mapping complexity** | Medium (21 sensors) | Low (5 sensors) | Low (1 sensor) |
| **Aegis compatibility** | ✅ Excellent | ⚠️ Good (single device) | ❌ Poor fit |
| **Phase 2 value** | ✅ High (degradation curves) | ⚠️ Medium (binary labels) | ⚠️ Medium (anomaly labels) |

---

## 3. Factual Trade-Offs

### NASA C-MAPSS FD001
**Strengths:**
- 100 distinct engines directly prove multi-device ingestion
- 21 sensors span temperature, pressure, and rotational categories
- Progressive degradation trajectory feeds Phase 2 anomaly detection
- Well-established benchmark in prognostics/health management research
- Manageable size (~20K rows) for sprint scope

**Weaknesses:**
- No wall-clock timestamps — cycle numbers only
- Requires synthetic timestamp generation (documented, deterministic)
- 21 sensors × 100 engines = 2,100 sensor registrations (batch script needed)
- Space-delimited format requires custom parsing (not CSV)

### AI4I 2020
**Strengths:**
- Simple CSV format, easy to parse
- Contains temperature and rotational speed
- Binary failure labels for future classification

**Weaknesses:**
- Single machine — cannot prove multi-device ingestion
- No pressure sensors
- No timestamps at all
- Synthetic data with limited physical fidelity
- Limited Phase 2 value beyond binary classification

### NAB
**Strengths:**
- Real wall-clock timestamps
- Labeled anomalies with known ground truth
- MIT license

**Weaknesses:**
- IT infrastructure data, not industrial equipment
- One metric per file — no multi-sensor envelopes
- No temperature/pressure/vibration in industrial context
- Would require stitching multiple files to simulate multi-sensor device
- Poor fit for Aegis's industrial telemetry domain model

---

## 4. Selection Decision

**Selected: NASA C-MAPSS FD001**

### Rationale
1. **Multi-device proof is the primary architectural goal of P1.S9.**
   C-MAPSS provides 100 distinct engines, each becoming a registered
   Aegis Device. This directly validates that the telemetry pipeline
   is source-agnostic across many producers.

2. **Sensor breadth exercises the full Aegis observation vocabulary.**
   Temperature (T2, T24, T30, T50), pressure (P2, P15, P30, Ps30),
   and rotational speed (Nf, Nc, NRf, NRc) map cleanly to existing
   Aegis measurement_type categories.

3. **Degradation trajectory sets up Phase 2.**
   Each engine degrades from nominal to failure over 128–362 cycles.
   This data will directly feed anomaly detection, context analysis,
   and diagnosis capabilities in Phase 2.

4. **Timestamp limitation is a feature, not a bug.**
   The absence of wall-clock timestamps forces explicit handling of
   historical event time vs ingestion time — a critical capability
   for any real-world telemetry system. The synthetic timestamp
   approach is fully documented and deterministic.

5. **Scope is manageable.**
   ~20K rows is large enough to be realistic but small enough to
   replay within a sprint demo. Bounded replay (5 engines, 50 cycles)
   keeps development iteration fast.

### Rejection Rationale
- **AI4I 2020:** Single device cannot prove multi-device ingestion.
- **NAB:** IT infrastructure data does not match Aegis's industrial
  domain model. Single-sensor files would require artificial stitching.

---

## 5. Dataset Provenance Record

| Field | Value |
|-------|-------|
| **Name** | C-MAPSS Turbofan Engine Degradation Simulation |
| **Subset** | FD001 (single operating condition, single fault mode) |
| **Publisher** | NASA Prognostics Center of Excellence |
| **Source URL** | https://www.nasa.gov/content/prognostics-center-of-excellence-data-set-repository |
| **Mirror** | https://ti.arc.nasa.gov/tech/dash/groups/pcoe/prognostic-data-repository/ |
| **Version** | Original release (2008) |
| **License** | NASA Open Data — no restrictions on use or redistribution |
| **Format** | Space-delimited text (.txt) |
| **File** | train_FD001.txt |
| **Approximate size** | ~2.5 MB |
| **Records** | 20,631 rows |
| **Signals** | 26 columns (unit, cycle, 3 settings, 21 sensors) |
| **Timestamps** | Cycle number (integer, 1-based, per unit) |
| **Known limitations** | Simulated data; no wall-clock time; single fault mode in FD001 |

---

## 6. Checksum (Post-Download)

> To be populated after dataset download in Block 5.
> ```
> SHA-256: <pending>
> ```
