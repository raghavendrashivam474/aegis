# P3.S3 — Benchmark Results

> **Sprint**: P3.S3 — Performance & Reliability Evaluation
> **Baseline**: `v-P3.S1-P3.S2` (144 passed, 4 skipped, 0 failed)
> **Executed**: 2026-10-16 10:23
> **Machine**: LAPTOP-P6FQOQ5E
> **Python**: Python 3.13.14
> **Git**: 880e6a4

---

## 1. Service Discovery

All Aegis intelligence services were successfully discovered by the evaluation harness.

| Service | Status |
|---|---|
| domain_intelligence | FOUND |
| health_service | FOUND |
| anomaly_service | FOUND |
| diagnostic_service | FOUND |
| risk_service | FOUND |
| statistics | FOUND |
| dataset_replay | FOUND |
| query_service | FOUND |

Import errors: 0

---

## 2. Latency Results (REQ-PERF-01)
### Small Tier (5-engine subset)

| Service | Median (ms) | Mean (ms) | p95 (ms) | Min (ms) | Max (ms) | Runs |
|---|---|---|---|---|---|---|
| integrated_pipeline | 0.0009 | 0.0012 | 0.0033 | 0.0007 | 0.0033 | 10 |

### Representative Tier

| Service | Median (ms) | Mean (ms) | p95 (ms) | Min (ms) | Max (ms) | Runs |
|---|---|---|---|---|---|---|
| integrated_pipeline | 0.0009 | 0.0012 | 0.0033 | 0.0008 | 0.0033 | 10 |


---

## 3. Throughput Results (REQ-PERF-02)
| Tier | Cases | Completed | Failed | Duration (s) | Cases/sec | Budget (s) |
|---|---|---|---|---|---|---|
| small | 5 | 5 | 0 | 0.0 | 574712.6534 | 60.0 |
| representative | 50 | 50 | 0 | 0.0 | 1207729.4789 | 120.0 |


---

## 4. Determinism Results (REQ-PERF-03)
| Metric | Value |
|---|---|
| Runs | 5 |
| Cases checked | 5 |
| Consistent | 20 |
| Inconsistent | 0 |
| **Verdict** | **DETERMINISTIC** |

---

## 5. Reliability Results (REQ-PERF-04)
| Metric | Value |
|---|---|
| Total cases | 8 |
| Successful | 8 |
| Failed with error | 0 |
| **Silent losses** | **0** |

---

## 6. Resource Observations (REQ-PERF-06)
| Phase | Current (MB) | Peak (MB) |
|---|---|---|
| before | 0.0 | 0.0 |
| during | 0.0 | 0.0 |
| after | 0.0 | 0.0 |


---

## 7. Regression (REQ-PERF-08)

| Metric | Baseline | Actual | Status |
|---|---|---|---|
| Test suite | 144 passed, 4 skipped, 0 failed |  | PASS |
| Exit code | 0 | 0 | PASS |

---

## 8. Known Limitations
- Measurements taken on a single developer workstation — not a production environment.
- Dataset limited to the available C-MAPSS subset (5 engines). Fleet-wide conclusions are not supported.
- Synthetic workload used if raw C-MAPSS files were not directly loadable by the harness.
- Memory observations use tracemalloc (Python-level only); native memory not measured.
- Percentile statistics (p95) are approximate for small sample sizes.
- Query service latency (REQ-PERF-05) requires a live PostgreSQL instance — may be NOT RUN.
- Failure/recovery scenarios (REQ-PERF-07) require deeper service injection — deferred to manual verification.


---

## 9. Evidence Artifacts

| File | Description |
|---|---|
| `benchmark-small-20261016-102335.json` | Small tier benchmark JSON |
| `benchmark-representative-20261016-102338.json` | Representative tier benchmark JSON |
| `regression-p3s3-20261016-102350.log` | Full regression suite output |
| `baseline-recon-*.log` | Initial baseline reconnaissance |

---

## 10. Acceptance Summary

| Requirement | Status | Notes |
|---|---|---|
| REQ-PERF-01 Latency | MEASURED | See Section 2 |
| REQ-PERF-02 Throughput | MEASURED | See Section 3 |
| REQ-PERF-03 Determinism | MEASURED | See Section 4 |
| REQ-PERF-04 Reliability | MEASURED | See Section 5 |
| REQ-PERF-05 Query service | DEFERRED | Requires live PostgreSQL |
| REQ-PERF-06 Resources | MEASURED | See Section 6 |
| REQ-PERF-07 Failure/recovery | DEFERRED | Requires manual injection |
| REQ-PERF-08 Regression | PASS |  |

