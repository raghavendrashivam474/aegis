# P2.S1 — Operational State & Asset Health: Test Cases

| Test Case ID | Target Scenario | Input | Expected Output | Actual Result | Status |
|---|---|---|---|---|---|
| **TC-P2-S1-001** | S1-STATISTICS | Uniform & Gaussian synthetic vectors | Correct mean, Bessel std, deviation score | Mean & Std match analytical baselines | **PASS** |
| **TC-P2-S1-002** | S1-TREND | Monotonic rising, falling, stable time series | Normalized slope mapped to `STABLE`, `INCREASING`, `DECREASING` | Accurately categorized all series | **PASS** |
| **TC-P2-S1-003** | S1-NORMAL | 70 cycles of multi-sensor nominal telemetry | `state=NORMAL`, `health_score >= 85`, `confidence >= 0.85` | `state=NORMAL`, `health_score=98.5`, `confidence=1.0` | **PASS** |
| **TC-P2-S1-004** | S1-DEGRADING | 50 baseline cycles + 30 rapid escalation cycles | `state=DEGRADING` / `CRITICAL`, `health_score < 60`, trend flagged | `state=CRITICAL`, `health_score=0.0`, trend flagged | **PASS** |
| **TC-P2-S1-005** | S1-INSUFFICIENT | 4 observations (< 10 sample requirement) | `state=UNKNOWN`, `confidence < 0.4`, sensor signals preserved | `state=UNKNOWN`, `confidence=0.0`, signals retained | **PASS** |
| **TC-P2-S1-006** | S1-BAD-DATA | 40 observations with 35 `QualityFlag.BAD` | BAD observations filtered, confidence penalized | Filtered properly, `state=UNKNOWN` | **PASS** |
| **TC-P2-S1-007** | S1-RECOVERY | Baseline → Thermal spike → Cooled return to nominal | Health score returns towards normal baseline | Health recovered to `100.0`, state `NORMAL` | **PASS** |
| **TC-P2-S1-008** | S1-DETERMINISM | 60 cycles evaluated twice identically | Idempotent numerical outputs across evaluations | Bit-for-bit identical assessments | **PASS** |
| **TC-P2-S1-009** | S1-CMAPSS-REAL | NASA C-MAPSS FD001 Engine-001 lifecycle | Early stage `NORMAL`, Late stage `DEGRADING` / `CRITICAL` | Early: `NORMAL` (88.70), Late: `CRITICAL` (36.97, 13 deviating sensors) | **PASS** |
