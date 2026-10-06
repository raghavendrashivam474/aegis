# P2.S1 — Operational State & Asset Health: Requirements

> **Phase:** 2 (Intelligence Layer)
> **Sprint:** S1 (Operational State & Asset Health)
> **Baseline:** P1.S9 — 82 passed, 4 skipped (Docker offline)
> **Status:** DRAFT → FINAL (after review)

---

## 1. Context & Rationale

Aegis P1 delivers a complete telemetry pipeline:

```text
C-MAPSS / ESP32 / Simulator
↓
TelemetryEnvelope (contracts)
↓
ObservationMapper → domain.Observation
↓
TelemetryRepository (PostgreSQL / InMemory)
↓
TelemetryQueryService
↓
Dashboard
```

P2.S1 adds the **first intelligence layer** on top of this pipeline.
It answers: *"Given the available telemetry, how healthy does this asset currently appear?"*

### What Already Exists (from Block 2 inspection)

| Component | Location | Key Shape |
|---|---|---|
| `Observation` | `packages/domain/entities.py` | frozen dataclass: `device_id`, `sensor_id`, `timestamp`, `value`, `unit`, `quality`, `metadata` |
| `QualityFlag` | `packages/domain/entities.py` | `GOOD`, `UNCERTAIN`, `BAD`, `CALIBRATION` |
| `Asset` | `packages/domain/entities.py` | `asset_id`, `name`, `asset_type`, `world_id`, `devices[]` |
| `TelemetryRepository` | `packages/domain/repository.py` | `get_observations(device_id, sensor_id, start_time, end_time, limit)` |
| `TelemetryQueryService` | `apps/backend/query_service.py` | `get_device_history()`, `get_sensor_history()`, `get_latest_reading()` |
| C-MAPSS sensors | `apps/dataset_replay/registration.py` | 21 sensors per engine, IDs: `sensor-{name}-engine-{NNN}` |
| C-MAPSS metadata | `apps/dataset_replay/adapter.py` | `metadata["cycle"]` = cycle number, quality degrades to UNCERTAIN after cycle 95 |

### What Does NOT Exist Yet

- No `OperationalState` concept
- No `HealthAssessment` value object
- No `TrendDirection` concept
- No intelligence service
- No health persistence
- No health query boundary

---

## 2. Architectural Decisions

### ADR-P2-S1-001: Intelligence Layer Placement

**Decision:** The intelligence layer lives in a new package `packages/intelligence/` and consumes the `TelemetryRepository` port directly.

**Rationale:**
- The brief specifies: `Query Service → Intelligence Application Service → Health/State Model → Domain/Repository ports`
- `TelemetryQueryService` is a thin wrapper over `TelemetryRepository`. For intelligence use cases that need multi-sensor aggregation across time windows, consuming the repository port directly (via the same interface) avoids an unnecessary indirection while maintaining the same boundary.
- The intelligence service will accept `TelemetryRepository` as a constructor dependency (dependency inversion), making it testable with `InMemoryTelemetryRepository`.

**Impact on P1:** Zero. No existing files modified.

### ADR-P2-S1-002: Health Computed On-Demand (No Persistence Yet)

**Decision:** P2.S1 health assessments are computed on-demand from historical telemetry. No new database tables or persistence ports are introduced in S1.

**Rationale:**
- S1's goal is a *defensible representation*, not a production-scale caching layer.
- Adding persistence prematurely would require new repository ports, migrations, and query services before we've validated the health model itself.
- S2 or a future sprint can add `HealthAssessmentRepository` once the model is stable.

**Impact on P1:** Zero.

### ADR-P2-S1-003: New Domain Value Objects

**Decision:** New value objects are added in `packages/domain/intelligence.py` (new file), exported via `packages/domain/__init__.py`.

**New types:**

```python
class OperationalState(StrEnum):
    NORMAL = "NORMAL"
    DEGRADING = "DEGRADING"
    CRITICAL = "CRITICAL"
    UNKNOWN = "UNKNOWN"

class TrendDirection(StrEnum):
    STABLE = "STABLE"
    INCREASING = "INCREASING"
    DECREASING = "DECREASING"
    UNKNOWN = "UNKNOWN"

@dataclass(frozen=True)
class SensorSignal:
    """Per-sensor evidence contributing to an asset health assessment."""
    sensor_id: str
    measurement_type: str
    baseline_mean: float
    baseline_std: float
    current_mean: float
    deviation_score: float      # |current - baseline| / baseline_std
    trend: TrendDirection
    data_quality: float         # 0.0–1.0 fraction of GOOD observations
    sample_count: int

@dataclass(frozen=True)
class HealthAssessment:
    """Immutable snapshot of an asset's operational health at a point in time."""
    asset_id: str
    device_id: str
    operational_state: OperationalState
    health_score: float         # 0.0–100.0
    confidence: float           # 0.0–1.0
    trend: TrendDirection
    sensor_signals: tuple[SensorSignal, ...]
    evaluated_at: datetime
    evidence_summary: str       # Human-readable one-liner
    metadata: dict[str, Any]

```

**Rationale:**

* `HealthAssessment` is frozen (immutable) — it's a snapshot, not a mutable entity.
* `confidence` is separate from `health_score` per the brief's explicit requirement.
* `sensor_signals` provides inspectable reasoning (no black-box).
* `OperationalState` is derived from `health_score` + `trend` + `confidence` via explicit rules, not a separate ML output.

---

## 3. Health Model Specification

### 3.1 Baseline Computation

For each sensor on a device:

* Retrieve the first N observations (default: first 50 cycles) as the "healthy baseline window."
* Compute `baseline_mean` and `baseline_std` from GOOD-quality observations only.
* If fewer than 10 GOOD observations exist, the sensor is marked `insufficient_data` and contributes to reduced confidence.

### 3.2 Current Window Evaluation

For each sensor:

* Retrieve the most recent M observations (default: last 20 cycles) as the "current window."
* Compute `current_mean` from GOOD-quality observations.
* Compute `deviation_score = |current_mean - baseline_mean| / max(baseline_std, epsilon)`.
* Compute trend via simple linear regression slope over the current window:
* slope ≈ 0 → `STABLE`
* slope > threshold → `INCREASING`
* slope < -threshold → `DECREASING`


* Compute `data_quality = fraction of observations with QualityFlag.GOOD`.

### 3.3 Aggregation to Asset Health

**Per-sensor health contribution:**

* `sensor_health = max(0, 100 - (deviation_score * weight))`
* Default weight: 15.0 (a 2-sigma deviation → 70, a 4-sigma → 40)

**Asset health score:**

* Weighted average of all sensor health contributions.
* Sensors with `insufficient_data` are excluded from the average but reduce confidence.

**Confidence:**

* Base confidence = 1.0
* Penalty for insufficient sensors: -0.1 per sensor with < 10 GOOD observations
* Penalty for poor data quality: -0.2 if average data_quality < 0.7
* Penalty for staleness: -0.15 if latest observation is older than expected window
* Clamped to [0.0, 1.0]

**Operational State derivation:**

* `health_score >= 75` AND `trend == STABLE` → `NORMAL`
* `health_score >= 50` AND (`trend == INCREASING` OR `health_score < 75`) → `DEGRADING`
* `health_score < 50` → `CRITICAL`
* `confidence < 0.4` → `UNKNOWN` (overrides above)

**Overall trend:**

* Majority vote across sensor trends (excluding `UNKNOWN`).

### 3.4 C-MAPSS-Specific Considerations

* FD001 has 21 sensors, but sensors 1, 5, 6, 10, 16, 18, 19 are known to be constant or near-constant. These will naturally produce low deviation scores and `STABLE` trends — they won't distort the model.
* The cycle metadata field enables precise windowing for baseline vs. current evaluation.
* Engines in FD001 run to failure, providing natural degradation trajectories for S1-DEGRADING validation.

---

## 4. Requirements Traceability Matrix

### REQ-P2-S1-001: Compute Health Assessment from Telemetry

| Field | Value |
| --- | --- |
| **Requirement** | Given a `device_id` and `TelemetryRepository`, produce a `HealthAssessment` |
| **Input** | `device_id`, `TelemetryRepository` with historical observations |
| **Expected Output** | `HealthAssessment` with `health_score`, `confidence`, `state`, `trend`, `sensor_signals` |
| **Test Case** | TC-P2-S1-001 |
| **Scenario** | S1-NORMAL |
| **Implementation** | `HealthAssessmentService.assess(device_id)` |
| **Actual Result** | TBD |
| **Status** | PENDING |

### REQ-P2-S1-002: Normal Asset Produces High Health

| Field | Value |
| --- | --- |
| **Requirement** | Stable telemetry within baseline range → `NORMAL` state, health ≥ 75, confidence ≥ 0.8 |
| **Input** | 100 cycles of stable C-MAPSS engine data (early cycles of any engine) |
| **Expected Output** | `state=NORMAL`, `health ≥ 75`, `confidence ≥ 0.8`, `trend=STABLE` |
| **Test Case** | TC-P2-S1-002 |
| **Scenario** | S1-NORMAL |
| **Implementation** | `HealthAssessmentService.assess()` with early-cycle window |
| **Actual Result** | TBD |
| **Status** | PENDING |

### REQ-P2-S1-003: Degrading Asset Produces Decreasing Health

| Field | Value |
| --- | --- |
| **Requirement** | Progressively worsening telemetry → `DEGRADING` state, health decreasing, trend reflects deterioration |
| **Input** | C-MAPSS engine in final 30% of lifecycle (e.g., engine-001 cycles 150–192) |
| **Expected Output** | `state=DEGRADING` or `CRITICAL`, `health < 75`, `trend=INCREASING` (deviation increasing) |
| **Test Case** | TC-P2-S1-003 |
| **Scenario** | S1-DEGRADING |
| **Implementation** | `HealthAssessmentService.assess()` with late-cycle window |
| **Actual Result** | TBD |
| **Status** | PENDING |

### REQ-P2-S1-004: Insufficient Data Reduces Confidence

| Field | Value |
| --- | --- |
| **Requirement** | Fewer than 10 GOOD observations → no unjustified health conclusion, confidence reduced |
| **Input** | Device with only 5 observations across all sensors |
| **Expected Output** | `state=UNKNOWN`, `confidence < 0.5`, `health_score` present but flagged |
| **Test Case** | TC-P2-S1-004 |
| **Scenario** | S1-INSUFFICIENT-DATA |
| **Implementation** | `HealthAssessmentService.assess()` with sparse data |
| **Actual Result** | TBD |
| **Status** | PENDING |

### REQ-P2-S1-005: Bad Data Does Not Produce Strong Claims

| Field | Value |
| --- | --- |
| **Requirement** | Observations with `QualityFlag.BAD` must not silently inflate or deflate health |
| **Input** | 50 observations where 40 are `QualityFlag.BAD` |
| **Expected Output** | `confidence < 0.5`, BAD observations excluded from baseline/current computation |
| **Test Case** | TC-P2-S1-005 |
| **Scenario** | S1-BAD-DATA |
| **Implementation** | `HealthAssessmentService.assess()` with quality filtering |
| **Actual Result** | TBD |
| **Status** | PENDING |

### REQ-P2-S1-006: Recovery Returns Health Toward Normal

| Field | Value |
| --- | --- |
| **Requirement** | Asset returning to baseline after degradation → health improves, state transitions back |
| **Input** | Synthetic: 50 normal cycles → 20 degrading cycles → 30 recovery cycles |
| **Expected Output** | Final assessment: health improving, `trend=STABLE` or `DECREASING` (deviation decreasing) |
| **Test Case** | TC-P2-S1-006 |
| **Scenario** | S1-RECOVERY |
| **Implementation** | `HealthAssessmentService.assess()` with synthetic recovery data |
| **Actual Result** | TBD |
| **Status** | PENDING |

### REQ-P2-S1-007: Health Assessment is Deterministic

| Field | Value |
| --- | --- |
| **Requirement** | Same input observations → identical `HealthAssessment` output |
| **Input** | Fixed set of 100 observations, assessed twice |
| **Expected Output** | Two identical `HealthAssessment` objects |
| **Test Case** | TC-P2-S1-007 |
| **Scenario** | S1-DETERMINISM |
| **Implementation** | `HealthAssessmentService.assess()` called twice |
| **Actual Result** | TBD |
| **Status** | PENDING |

### REQ-P2-S1-008: No SQL in Intelligence or Presentation Code

| Field | Value |
| --- | --- |
| **Requirement** | Intelligence layer consumes `TelemetryRepository` port; dashboard consumes intelligence service. No raw SQL outside persistence adapters. |
| **Input** | Architecture boundary check |
| **Expected Output** | `test_architecture_boundaries.py` passes with new intelligence module |
| **Test Case** | TC-P2-S1-008 |
| **Scenario** | Architecture compliance |
| **Implementation** | Architecture test extension |
| **Actual Result** | TBD |
| **Status** | PENDING |

### REQ-P2-S1-009: P1 Regression Preserved

| Field | Value |
| --- | --- |
| **Requirement** | All 86 existing P1 tests continue to pass (82 pass + 4 skip) |
| **Input** | Full test suite |
| **Expected Output** | 82 passed, 4 skipped, 0 failed |
| **Test Case** | TC-P2-S1-009 |
| **Scenario** | Regression |
| **Implementation** | `pytest tests/` |
| **Actual Result** | TBD |
| **Status** | PENDING |

---

## 5. File Plan

| New File | Purpose |
| --- | --- |
| `packages/domain/intelligence.py` | `OperationalState`, `TrendDirection`, `SensorSignal`, `HealthAssessment` |
| `packages/intelligence/__init__.py` | Package init |
| `packages/intelligence/health_service.py` | `HealthAssessmentService` |
| `packages/intelligence/statistics.py` | Baseline computation, deviation, trend (pure functions) |
| `tests/test_p2_s1_health.py` | Unit + scenario tests for S1 |
| `docs/phases/p2/s1/requirements.md` | This file |
| `docs/phases/p2/s1/test_cases.md` | Detailed test case specifications |
| `scripts/showcase_p2_s1.py` | End-to-end demonstration |

| Modified File | Change |
| --- | --- |
| `packages/domain/__init__.py` | Export new intelligence types |
| `tests/test_architecture_boundaries.py` | Add intelligence module to allowed boundaries (if needed) |

*No other P1 files are modified.*

---

## 6. Definition of Done (P2.S1)

* [ ] All 9 requirements above have PASS status
* [ ] `packages/domain/intelligence.py` created with frozen value objects
* [ ] `HealthAssessmentService` implemented and tested
* [ ] S1-NORMAL scenario passes
* [ ] S1-DEGRADING scenario passes (C-MAPSS late-cycle data)
* [ ] S1-INSUFFICIENT-DATA scenario passes
* [ ] S1-BAD-DATA scenario passes
* [ ] S1-RECOVERY scenario passes
* [ ] Determinism verified
* [ ] Architecture boundary check passes
* [ ] P1 regression: 82 passed, 4 skipped, 0 failed
* [ ] Lint + format pass
* [ ] Showcase script demonstrates capability
* [ ] Traceability complete

```