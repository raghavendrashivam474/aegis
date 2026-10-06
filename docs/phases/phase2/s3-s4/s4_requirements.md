# Phase 2 Sprint 4 (P2.S4) — Operational Risk & Prioritized Findings

## 1. Objective
Consume the outputs of Health (P2.S1), Anomaly (P2.S2), and Diagnosis (P2.S3) to generate highly explainable, operator-oriented prioritized findings and recommended next actions. 

This layer does NOT perform automated actuation or control. It is an advisory risk-prioritization matrix designed to protect human operators from alarm fatigue.

## 2. Core Architectural Guarantees
1. **Traceability**: Findings must be traceable backward from finding priority -> risk level -> diagnostic hypothesis -> anomaly evidence -> telemetry.
2. **Deterministic Prioritization**: Avoid arbitrary scores; prioritize based on a clear, explainable lookup matrix of Health, Severity, Persistence, and Diagnostic Status.
3. **Purity**: Zero SQL, zero third-party I/O, zero network calls inside the intelligence service. Respect the architectural boundary tests.

## 3. Inputs
- `HealthAssessment`
- `AnomalyDetectionResult`
- `DiagnosticResult`

## 4. Outputs
- `OperationalFinding` (immutable frozen value object)
  - `asset_id`: str
  - `device_id`: str
  - `priority`: OperationalPriority (NONE, LOW, MEDIUM, HIGH, CRITICAL)
  - `risk_level`: AnomalySeverity
  - `summary`: str
  - `health_score`: float
  - `anomaly_score`: float
  - `diagnostic_status`: DiagnosticStatus
  - `primary_hypothesis`: DiagnosticHypothesis | None
  - `recommendation`: str
  - `traceability_chain`: dict[str, Any]
  - `evaluated_at`: datetime
  - `limitations`: str
