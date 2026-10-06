# P2.S2 — Anomaly & Degradation Detection: Test Cases

| Test Case ID | Target Scenario | Input Description | Expected Output | Actual Result | Status |
|---|---|---|---|---|---|
| **TC-P2-S2-001** | S2-NORMAL | 60 cycles nominal multi-sensor telemetry | `status=NOMINAL`, `severity=NONE`, `anomaly_score < 0.25` | `status=NOMINAL`, `score=0.00`, `severity=NONE` | **PASS** |
| **TC-P2-S2-002** | S2-EARLY-DEGRADATION | 50 baseline cycles + 10 mild drift cycles | `status=ANOMALY_DETECTED`, `severity=LOW/MEDIUM`, `score < 0.80` | `status=ANOMALY_DETECTED`, `severity=LOW`, `score=0.31` | **PASS** |
| **TC-P2-S2-003** | S2-CLEAR-DEGRADATION | Persistent multi-signal severe deterioration | `status=DEGRADATION_DETECTED`, `severity=HIGH/CRITICAL`, `score >= 0.75` | `status=DEGRADATION_DETECTED`, `severity=CRITICAL`, `score=0.96` | **PASS** |
| **TC-P2-S2-004** | S2-NOISY-DATA | White noise / sensor jitter ($\sigma=0.3$) | `status=NOMINAL`, `severity=NONE`, `score < 0.30` | `status=NOMINAL`, `score=0.00`, `severity=NONE` | **PASS** |
| **TC-P2-S2-005** | S2-MISSING-DATA | 3 observations total | `status=UNKNOWN`, `confidence=0.0`, `severity=NONE` | `status=UNKNOWN`, `confidence=0.0`, `severity=NONE` | **PASS** |
| **TC-P2-S2-006** | S2-RECOVERY | Baseline → Thermal spike → Cooled nominal | Returns cleanly to `status=NOMINAL`, `severity=NONE` | `status=NOMINAL`, `score=0.00`, `severity=NONE` | **PASS** |
| **TC-P2-S2-007** | S2-REPLAY | Replay of 65 cycles evaluated twice | 100% identical outputs (status, score, confidence, severity) | Bit-for-bit identical outputs | **PASS** |
| **TC-P2-S2-008** | S2-GROUND-TRUTH-CMAPSS | NASA C-MAPSS FD001 Turbofan lifecycle | Early: `NOMINAL` (score < 0.25); Late: `DEGRADATION_DETECTED` (score >= 0.70) | Early: `NOMINAL` (0.00); Late: `DEGRADATION_DETECTED` (0.97, 13 sensors) | **PASS** |
