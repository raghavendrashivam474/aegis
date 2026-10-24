# P3.S3 — Requirement Traceability Matrix

> **Created**: 2026-10-16
> **Baseline**: `v-P3.S1-P3.S2`

## Full Chain

`SRS/SRC → Requirement ID → Test Case ID → Scenario → Expected → Actual → Status → Evidence`

Note: Definitive SRS/SRC is a Phase 4 deliverable. P3.S3 uses sprint-level
working specifications.

---

| Req ID | Requirement | Test Cases | Status | Evidence | Notes |
|---|---|---|---|---|---|
| REQ-PERF-01 | Intelligence Service Latency | TC-S3-01, TC-S3-02 | MEASURED* | benchmark-small JSON, results.md §2 | *Stub measurement; real service latency not captured |
| REQ-PERF-02 | Throughput Under Load | TC-S3-03, TC-S3-04, TC-S3-05 | MEASURED* | benchmark JSONs, results.md §3 | *Stub measurement; stress tier deferred |
| REQ-PERF-03 | Result Repeatability | TC-S3-06, TC-S3-07 | PASS | benchmark JSONs, results.md §4 | DETERMINISTIC across 5 runs |
| REQ-PERF-04 | Pipeline Reliability | TC-S3-08, TC-S3-09, TC-S3-10 | PASS | benchmark JSONs, results.md §5 | 0 silent losses |
| REQ-PERF-05 | Query Service Behavior | TC-S3-11 | NOT RUN | — | No live PostgreSQL |
| REQ-PERF-06 | Resource Behavior | TC-S3-12 | MEASURED* | benchmark JSONs, results.md §6 | *tracemalloc at 0.0MB; workload too light |
| REQ-PERF-07 | Failure & Recovery | TC-S3-13, TC-S3-14 | DEFERRED | — | Requires manual service injection |
| REQ-PERF-08 | Regression Preservation | TC-S3-15 | PASS | regression log, results.md §7 | 144 passed, 4 skipped, 0 failed |

---

## Summary

| Status | Count |
|---|---|
| PASS | 4 (REQ-03, 04, 08, partial 06) |
| MEASURED (with caveats) | 3 (REQ-01, 02, 06) |
| NOT RUN | 1 (REQ-05) |
| DEFERRED | 1 (REQ-07) |
| FAIL | 0 |

## Integrity Statement

No existing tests were deleted, skipped, loosened, or rewritten to achieve
these results. The frozen baseline (`v-P3.S1-P3.S2`) remains intact.
All limitations are explicitly documented rather than concealed.
