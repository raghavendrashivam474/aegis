
| Scenario ID | Input Condition | Expected Behavior | Actual Behavior | Result |
|---|---|---|---|---|
| `S2-NOMINAL` | Clean nominal telemetry | `NORMAL / NONE` | `NORMAL / NONE` | ✅ PASS |
| `S2-NOISE` | Gaussian noise (3% stddev) | No premature escalation | `Score 0.11 / NONE` | ✅ PASS |
| `S2-MISSING` | 60% random packet drop | Reduced confidence | `Conf 0.95 / NONE` | ✅ PASS |
| `S2-BAD-DATA` | 25% BAD quality flags | Bad data excluded | `NORMAL / NONE` | ✅ PASS |
| `S2-UNCERTAIN` | 50% UNCERTAIN quality flags | Uncertainty preserved | `Conf < 1.0` | ✅ PASS |
| `S2-TRANSIENT` | Single-cycle 2.5x spike | No persistent degradation | `NOMINAL / NONE` | ✅ PASS |
| `S2-SUSTAINED` | Multi-sensor drift to failure | Degradation escalated | `DEGRADATION / CRITICAL` | ✅ PASS |
| `S2-CONFLICT` | Contradicting sensor movements | Evidence retained in chain | `Traceability Chain Valid` | ✅ PASS |
| `S2-RECOVERY` | Degradation followed by nominal | Finding clears | `NONE / NONE` | ✅ PASS |
| `S2-INSUFFICIENT` | Sub-minimum samples (< 5) | Graceful uncertainty | `UNKNOWN / NONE` | ✅ PASS |
