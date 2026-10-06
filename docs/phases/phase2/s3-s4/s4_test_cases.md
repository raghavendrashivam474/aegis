# Phase 2 Sprint 4 (P2.S4) — Test Case Specification

## Scenario Matrix

| Scenario ID | Name | Description | Expected Priority | Expected Advisory Action |
|---|---|---|---|---|
| **S4-NOMINAL** | Nominal Condition | Stable, normal telemetry, high health | `NONE` | "No operational intervention required. Continue standard logging." |
| **S4-EARLY-DRIFT** | Early Drift | Emerging drift, low-severity anomaly, high health | `LOW` | "Initiate continuous observation; scheduled inspection is not yet required." |
| **S4-HIGH-RISK** | Persistent High Risk | Severe multi-sensor deviation, low health | `CRITICAL` | "Schedule immediate maintenance. Inspect the degraded subsystem." |
| **S4-MULTIPLE-HYPOTHESES** | Ambigous Candidates | Multiple hypotheses share close confidence levels | `MEDIUM` | "Initiate localized diagnostic checks to differentiate competing fault models." |
| **S4-LOW-CONFIDENCE** | Uncertain Findings | High deviation, but low diagnostic confidence | `LOW` or `MEDIUM` | "Review sensor health, calibration, and data quality flags." |
| **S4-RECOVERY** | Asset Self-Recovery | Asset returns to baseline after a spike | `NONE` | Resolution of previous alert; returns to nominal monitoring. |
| **S4-DETERMINISM** | Replay Determinism | Identical inputs processed twice | Same Priority | Identical recommended advisory action and metadata. |
| **S4-END-TO-END** | C-MAPSS Full Chain | Raw Telemetry -> Health -> Anomaly -> Diagnosis -> Finding | Nominal: `NONE` / Degraded: `CRITICAL` | Complete traceable path from finding back to sensor values. |
