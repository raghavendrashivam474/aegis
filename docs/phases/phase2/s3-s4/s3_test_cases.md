# Phase 2 Sprint 3 (P2.S3) — Test Case Specification

## Scenarios Matrix

| Scenario ID | Name | Description | Expected Status | Expected Risk / Hypothesis |
|---|---|---|---|---|
| **S3-NOMINAL** | Stable Nominal Telemetry | All sensors stable within ±0.2σ | `NOMINAL` | Risk: `NONE`, No abnormal hypotheses |
| **S3-SINGLE-SENSOR** | Localized Sensor Anomaly | Single sensor > 3.0σ, neighbors nominal, low persistence | `INVESTIGATING` | Localized sensor / transient hypothesis, moderate confidence |
| **S3-CORRELATED-DEVIATION** | Correlated Subsystem Drift | Multiple thermal sensors escalating concurrently (>2.5σ, increasing trend) | `LIKELY_DEGRADATION` | Subsystem hypothesis (Thermal), High confidence (>0.75), structured supporting evidence |
| **S3-TRANSIENT** | Transient Spike | Brief single-cycle spike with immediate recovery | `INVESTIGATING` or `NOMINAL` | Transient hypothesis, low diagnostic confidence |
| **S3-PERSISTENT** | Persistent Multi-Signal Degradation | Temperature & vibration escalating over 25+ cycles | `LIKELY_DEGRADATION` | High/Critical Risk, Subsystem Degradation, Persistence documented in evidence |
| **S3-CONFLICTING-EVIDENCE** | Conflicting / Mixed Signals | Temperature rises but companion thermal/pressure signals remain flat | `MULTIPLE_POSSIBLE_CAUSES` or `INVESTIGATING` | Retains contradicting evidence, reduced hypothesis confidence |
| **S3-INSUFFICIENT** | Insufficient / Low Quality Telemetry | Sparse observations or bad quality flags | `INSUFFICIENT_EVIDENCE` / `UNKNOWN` | Confidence < 0.4, explicit limitations note |
| **S3-DETERMINISM** | Evaluation Idempotency | Identical inputs evaluated twice | Same status, scores, evidence, and hypotheses | Identical hash/equality |
| **S3-CMAPSS-GROUND-TRUTH** | NASA C-MAPSS FD001 Real Lifecycle | Engine-001 early vs late lifecycle | Early: `NOMINAL` / Late: `LIKELY_DEGRADATION` with multi-sensor degradation evidence |
