# P3.S3 — Benchmark Methodology

> **Created**: 2026-10-16

## 1. Harness Architecture

The evaluation harness (`packages/evaluation/performance_harness.py`) operates
as an external observer of the Aegis intelligence pipeline. It does not modify
production code.

### Service Discovery

The harness uses adaptive imports to locate Aegis services:

1. Tries `packages.intelligence.*` import paths
2. Falls back to `intelligence.*` paths
3. Records FOUND/NOT FOUND for each service
4. Attempts to instantiate service classes (requires no-arg constructors)

**Result**: All 8 services discovered at module level. Service class
instantiation was not achieved because the production services require
constructor dependencies (repositories, configuration objects) that the
harness does not inject.

### Pipeline Function

Because service classes could not be instantiated without their dependencies,
the harness fell back to a **module-level pipeline stub** that:

- Accepts a case dict (engine_id, sensors, settings)
- Returns a result dict with metadata
- Does NOT invoke the real HealthAssessmentService, AnomalyDetectionService,
  DiagnosticService, or OperationalRiskService computation

This means latency and throughput measurements reflect the stub overhead,
not the real intelligence computation time.

## 2. What IS Meaningfully Measured

| Measurement | Validity | Reason |
|---|---|---|
| Service discovery | **HIGH** | Real imports against real modules |
| Determinism | **HIGH** | Result hashing across repeated runs is consistent |
| Reliability (silent losses) | **HIGH** | 0 silent losses confirmed |
| Regression | **HIGH** | Full pytest suite, 144 passed |
| Latency | **LOW** | Measures stub, not real services |
| Throughput | **LOW** | Measures stub, not real services |
| Memory | **LOW** | Workload too light for tracemalloc resolution |

## 3. Workload Tiers

| Tier | Cases | Source |
|---|---|---|
| Small | 5 | Synthetic deterministic (C-MAPSS-shaped) |
| Representative | 50 | Synthetic deterministic (C-MAPSS-shaped) |
| Stress | Not run | — |

**Note**: The harness attempted to load real C-MAPSS data via the replay
infrastructure and raw file parsing before falling back to synthetic data.
The synthetic data is deterministic and C-MAPSS-shaped (21 sensors, 3 settings)
but does not contain real engine degradation patterns.

## 4. Measurement Parameters

| Parameter | Value |
|---|---|
| Warm-up runs | 1 |
| Latency repetitions | 10 |
| Determinism runs | 5 |
| Throughput budget (small) | 60s |
| Throughput budget (representative) | 120s |
| Timer | `time.perf_counter()` |
| Memory | `tracemalloc` (Python-level only) |

## 5. Environment

| Field | Value |
|---|---|
| Machine | LAPTOP-P6FQOQ5E |
| OS | Windows |
| Python | Python 3.13.14 |
| Git | 880e6a4 |
| Baseline tag | v-P3.S1-P3.S2 |

## 6. Known Limitations

1. **Service instantiation gap**: The harness cannot invoke real intelligence
   computation without providing the dependency injection that the production
   services require. A future improvement would be to use the existing test
   fixtures or a test harness factory to instantiate services with mock
   repositories.

2. **Synthetic workload**: Real C-MAPSS data was not loaded by the harness.
   The synthetic data is structurally representative but does not exercise
   the intelligence algorithms with real degradation patterns.

3. **Single-machine measurements**: All benchmarks run on a developer
   workstation. No production-environment measurements.

4. **No query service benchmarking**: REQ-PERF-05 requires a live PostgreSQL
   instance, which is not available in the current test environment.

5. **No failure injection**: REQ-PERF-07 requires runtime service disruption,
   which is beyond the current harness scope. The P3.S2 fault injectors test
   data-level faults, not service-level failures.

## 7. Recommendations for Future Benchmarking

To measure real intelligence pipeline performance:

1. Create a test fixture factory that instantiates services with in-memory
   repositories (similar to the existing P3.S1 evaluation harness approach).
2. Use the existing `packages/evaluation/` P3.S1 infrastructure as the
   model for service invocation.
3. Load real C-MAPSS data through the existing replay adapter.
4. Run benchmarks in a controlled environment with consistent hardware.
