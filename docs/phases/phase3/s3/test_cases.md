# P3.S3 — Test Cases (Final Status)

> **Baseline**: `v-P3.S1-P3.S2` · 144 passed · 4 skipped · 0 failed
> **Executed**: 2026-10-16
> **Status**: FINAL

## Traceability Convention

`Requirement ID → Test Case ID → Scenario → Expected → Actual → Status → Evidence`

---

| ID | Req | Scenario | Status | Evidence |
|---|---|---|---|---|
| TC-S3-01 | REQ-PERF-01 | Nominal single-case latency | PASS* | benchmark-small JSON |
| TC-S3-02 | REQ-PERF-01 | Integrated path latency | PASS* | benchmark-small JSON |
| TC-S3-03 | REQ-PERF-02 | Small workload throughput | PASS* | benchmark-small JSON |
| TC-S3-04 | REQ-PERF-02 | Representative throughput | PASS* | benchmark-representative JSON |
| TC-S3-05 | REQ-PERF-02 | Stress/boundary throughput | DEFERRED | Stress tier not executed |
| TC-S3-06 | REQ-PERF-03 | Determinism (3 runs) | PASS | DETERMINISTIC verdict |
| TC-S3-07 | REQ-PERF-03 | Determinism (5 runs) | PASS | 40 consistent, 0 inconsistent |
| TC-S3-08 | REQ-PERF-04 | Valid input success rate | PASS | 0 silent losses |
| TC-S3-09 | REQ-PERF-04 | Invalid input handling | PASS | Errors surfaced, no crashes |
| TC-S3-10 | REQ-PERF-04 | Insufficient data handling | PASS | P3.S2 robustness preserved |
| TC-S3-11 | REQ-PERF-05 | Query service reads | NOT RUN | No live PostgreSQL |
| TC-S3-12 | REQ-PERF-06 | Memory during workload | PASS* | tracemalloc snapshots |
| TC-S3-13 | REQ-PERF-07 | Service exception injection | DEFERRED | Requires manual injection |
| TC-S3-14 | REQ-PERF-07 | Recovery after failure | DEFERRED | Requires manual injection |
| TC-S3-15 | REQ-PERF-08 | Full regression suite | PASS | 144 passed, 4 skipped, 0 failed |

**\*PASS with caveat**: Latency/throughput/resource measurements reflect the
harness module-level pipeline stub, not the full intelligence service chain.
Service classes require dependency injection (repositories, config) that the
harness does not provide. See `benchmark_methodology.md` and
`post_completion_report.md` for details.
