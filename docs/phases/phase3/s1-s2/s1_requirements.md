# P3.S1 — Fleet-Wide Intelligence Evaluation Requirements

## REQ-P3S1-001: Fleet Population Evaluation
The evaluation harness MUST systematically exercise the existing intelligence pipeline across a representative sample of C-MAPSS FD001 engine trajectories (minimum 5).

## REQ-P3S1-002: Same Intelligence Execution Path
The evaluation harness MUST reuse the exact production intelligence service classes implemented in Phase 2:
- `HealthAssessmentService`
- `AnomalyDetectionService`
- `DiagnosticService`
- `OperationalRiskService`
No parallel benchmark-specific detectors are permitted.

## REQ-P3S1-003: Ground Truth Alignment
Every evaluation case MUST register an explicit `GroundTruthLabel` (e.g., `NOMINAL`, `DEGRADING`, `FAILURE_BOUND`, `UNKNOWN`) to compare Aegis predictions against.

## REQ-P3S1-004: Standard Detection Metrics
The evaluation harness MUST compute standard binary classification metrics across evaluated cases:
- True Positives (TP), True Negatives (TN), False Positives (FP), False Negatives (FN)
- Precision, Recall, F1 Score
- False Positive Rate (FPR)

## REQ-P3S1-005: Operational Risk & Escalation Rates
The harness MUST track the percentage of correct risk escalations on degraded engines (expecting HIGH or CRITICAL priority findings) and false escalations on nominal engines.

## REQ-P3S1-006: Bit-Identical Determinism
The benchmark evaluation suite MUST run with 100% deterministic reproducibility. Two identical consecutive runs over the same trajectories MUST yield bit-identical scores, states, confidence intervals, and priority classifications.

## REQ-P3S1-007: No Production Code Pollution
The benchmark calculations and metrics suite MUST live outside of the production packages (e.g., in a separate `packages/evaluation/` package) to prevent polluting the core intelligence domain with evaluation-specific constructs.
