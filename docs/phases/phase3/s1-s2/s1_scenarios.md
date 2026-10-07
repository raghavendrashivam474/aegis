# P3.S1 — Fleet-Wide Intelligence Evaluation Scenarios

| Scenario ID | Name | Target Trajectories | Ground Truth | Expected Interpretation |
|---|---|---|---|---|
| `S1-FLEET-NOMINAL` | Early Lifecycle Nominal Fleet | FD001 units (cycles 1 to 0.35 * Tmax) | `NOMINAL` | `OperationalState.NORMAL`, `AnomalyStatus.NOMINAL`, `Priority.NONE` |
| `S1-FLEET-DEGRADATION` | Late Lifecycle Run-to-Failure | FD001 units (last 30 cycles) | `DEGRADING` | `AnomalyStatus.DEGRADATION_DETECTED`, `DiagnosticStatus.LIKELY_DEGRADATION`, `Priority.CRITICAL/HIGH` |
| `S1-FLEET-MIXED` | Mixed Fleet Evaluation | All FD001 trajectories evaluated in unified batch | Mixed (`NOMINAL` + `DEGRADING`) | Per-case matching without cross-unit bleed |
| `S1-METRIC-CALCULATION` | Metric Formulation Verification | Synthetic EvaluationResult test fixtures | Controlled TP/TN/FP/FN | Exact mathematical precision, recall, F1, and FPR |
| `S1-LEAD-TIME` | Lead Time Summary Stats | Positive detection cases | Cycle offsets | Accurate mean, median, min, max lead time calculation |
| `S1-DETERMINISM` | Idempotent Reproducibility | Identical case batch executed twice | Bit-identical | Exact match across scores, states, diagnoses, and findings |
| `S1-INSUFFICIENT-DATA` | Sub-minimum Observation Window | Trajectories < 10 samples | `UNKNOWN` | Graceful classification without false detection |
