# Phase 2 Sprint 3 (P2.S3) — Context, Risk & Evidence / Root-Cause Hypotheses

## 1. Objective
Advance the Aegis Intelligence pipeline from anomaly detection ("Something abnormal is occurring") to explainable diagnosis ("What evidence explains the abnormal behavior, what operational context surrounds it, which subsystems are involved, and what are the most plausible hypotheses?").

## 2. Core Architectural Guarantees
1. **Evidence-First**: All hypotheses are derived deterministically from inspectable structured evidence (sensor deviations, trends, persistence, quality).
2. **Epistemic Modesty**: Aegis produces *hypotheses* and *interpretations*, never claiming physically confirmed root causes without ground-truth teardown proof.
3. **Purity & Non-breaking**:
   - Zero SQL or database queries inside `DiagnosticService`.
   - Zero external ML / LLM black-box models.
   - Zero modifications to working P2.S1 / P2.S2 code.
   - P2.S1 and P2.S2 test suites remain 100% green.
4. **Separation of Confidence**: Diagnostic confidence measures evidentiary support, distinct from asset health score and anomaly detection score.

## 3. Inputs
- `HealthAssessment` (P2.S1 frozen snapshot)
- `AnomalyDetectionResult` (P2.S2 frozen snapshot)
- Optional `TelemetryRepository` (query port for additional historical cross-signal verification)

## 4. Outputs
- `DiagnosticResult` (immutable frozen value object)
  - `asset_id`: str
  - `device_id`: str
  - `status`: DiagnosticStatus (NOMINAL, INVESTIGATING, LIKELY_DEGRADATION, MULTIPLE_POSSIBLE_CAUSES, INSUFFICIENT_EVIDENCE, UNKNOWN)
  - `overall_risk`: AnomalySeverity (NONE, LOW, MEDIUM, HIGH, CRITICAL)
  - `context`: DiagnosticContext
  - `evidence`: tuple[DiagnosticEvidence, ...]
  - `hypotheses`: tuple[DiagnosticHypothesis, ...]
  - `primary_hypothesis`: DiagnosticHypothesis | None
  - `confidence`: float (0.0 to 1.0)
  - `primary_finding`: str
  - `limitations`: str
  - `evaluated_at`: datetime
  - `diagnostic_method`: str
  - `metadata`: dict[str, Any]

## 5. Diagnostic Rule Engine
Deterministic pattern matchers:
- **Thermal Subsystem Degradation**: Significant elevation and increasing trend in temperature sensors with high persistence.
- **Mechanical / Vibration Degradation**: Elevated vibration / speed deviations with monotonic trends.
- **Pressure / Flow Subsystem Disturbance**: Significant pressure drops or flow deviations combined with elevated temperature.
- **Systemic / Multi-Subsystem Degradation**: Coordinated multi-sensor deviations across multiple physical subsystems.
- **Localized / Sensor Transient**: Isolated single-sensor deviation with nominal companion sensors and low persistence.
- **Nominal Baseline**: All sensors within normal bounds.
- **Insufficient Evidence**: Low data quality or insufficient baseline/current observations.
