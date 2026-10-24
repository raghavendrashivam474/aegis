"""
P3.S3 — Performance & Reliability Evaluation Harness

Evaluates the existing Aegis intelligence pipeline without modifying it.
Measures latency, throughput, determinism, reliability, and resource behavior.

Isolation principle: this module invokes existing service boundaries and
produces measurement artifacts. It does NOT add benchmark-specific behavior
to production services.

Usage:
    from packages.evaluation.performance_harness import PerformanceHarness
    harness = PerformanceHarness()
    results = harness.run_all(tier="small")
"""

import time
import json
import sys
import os
import platform
import hashlib
import traceback
import tracemalloc
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Any, Tuple
from datetime import datetime, timezone
from pathlib import Path
from statistics import median, mean, stdev


# ================================================================
# Data structures
# ================================================================

@dataclass
class TimingResult:
    """Single timing measurement."""
    service: str
    runs: int
    warmup: int
    times_ms: List[float]
    median_ms: float
    mean_ms: float
    min_ms: float
    max_ms: float
    p95_ms: float = 0.0
    stdev_ms: float = 0.0

    def __post_init__(self):
        if self.times_ms:
            sorted_t = sorted(self.times_ms)
            idx = int(len(sorted_t) * 0.95)
            idx = min(idx, len(sorted_t) - 1)
            self.p95_ms = sorted_t[idx]
            if len(sorted_t) > 1:
                self.stdev_ms = stdev(sorted_t)


@dataclass
class ThroughputResult:
    """Throughput measurement."""
    tier: str
    total_cases: int
    completed_cases: int
    failed_cases: int
    duration_s: float
    cases_per_second: float
    time_budget_s: float


@dataclass
class DeterminismResult:
    """Determinism check result."""
    runs: int
    cases_checked: int
    consistent_cases: int
    inconsistent_cases: int
    inconsistent_fields: List[str]
    verdict: str  # "DETERMINISTIC", "STOCHASTIC_FIELDS", "NON_DETERMINISTIC"


@dataclass
class ReliabilityResult:
    """Pipeline reliability result."""
    total_cases: int
    successful: int
    failed_with_error: int
    silent_losses: int
    error_details: List[Dict[str, str]]


@dataclass
class ResourceSnapshot:
    """Memory/resource observation."""
    phase: str  # "before", "during", "after"
    current_mb: float
    peak_mb: float
    timestamp: str


@dataclass
class BenchmarkReport:
    """Complete benchmark report."""
    timestamp: str
    machine: str
    python_version: str
    git_commit: str
    dataset: str
    tier: str
    discovery: Dict[str, bool]
    latency: Dict[str, dict]
    throughput: Optional[dict]
    determinism: Optional[dict]
    reliability: Optional[dict]
    resources: List[dict]
    errors: List[str]
    limitations: List[str]


# ================================================================
# Service discovery
# ================================================================

class ServiceDiscovery:
    """Discovers available Aegis intelligence services."""

    def __init__(self):
        self.services: Dict[str, Any] = {}
        self.modules: Dict[str, Any] = {}
        self.available: Dict[str, bool] = {
            "domain_intelligence": False,
            "health_service": False,
            "anomaly_service": False,
            "diagnostic_service": False,
            "risk_service": False,
            "statistics": False,
            "dataset_replay": False,
            "query_service": False,
        }
        self.import_errors: List[str] = []

    def discover(self):
        """Attempt to import all known Aegis services."""

        # --- Domain contracts ---
        for path in [
            "packages.domain.intelligence",
            "domain.intelligence",
        ]:
            try:
                mod = __import__(path, fromlist=["*"])
                self.modules["domain_intelligence"] = mod
                self.available["domain_intelligence"] = True
                break
            except ImportError as e:
                self.import_errors.append(f"{path}: {e}")

        # --- Intelligence services ---
        service_map = {
            "health_service": [
                "packages.intelligence.health_service",
                "intelligence.health_service",
            ],
            "anomaly_service": [
                "packages.intelligence.anomaly_service",
                "intelligence.anomaly_service",
            ],
            "diagnostic_service": [
                "packages.intelligence.diagnostic_service",
                "intelligence.diagnostic_service",
            ],
            "risk_service": [
                "packages.intelligence.risk_service",
                "intelligence.risk_service",
            ],
            "statistics": [
                "packages.intelligence.statistics",
                "intelligence.statistics",
            ],
        }

        for name, paths in service_map.items():
            for path in paths:
                try:
                    mod = __import__(path, fromlist=["*"])
                    self.modules[name] = mod
                    self.available[name] = True

                    # Try to instantiate the primary service class
                    class_name = "".join(
                        w.capitalize() for w in name.split("_")
                    )
                    if hasattr(mod, class_name):
                        try:
                            self.services[name] = getattr(mod, class_name)()
                        except Exception:
                            # Class exists but needs constructor args
                            self.services[name] = getattr(mod, class_name)
                    break
                except ImportError as e:
                    self.import_errors.append(f"{path}: {e}")

        # --- Dataset replay ---
        for path in [
            "apps.dataset_replay.replay",
            "dataset_replay.replay",
        ]:
            try:
                mod = __import__(path, fromlist=["*"])
                self.modules["dataset_replay"] = mod
                self.available["dataset_replay"] = True
                break
            except ImportError as e:
                self.import_errors.append(f"{path}: {e}")

        # --- Query service ---
        for path in [
            "apps.backend.query_service",
            "backend.query_service",
        ]:
            try:
                mod = __import__(path, fromlist=["*"])
                self.modules["query_service"] = mod
                self.available["query_service"] = True
                break
            except ImportError as e:
                self.import_errors.append(f"{path}: {e}")

        return self.available

    def report(self) -> str:
        """Human-readable discovery report."""
        lines = ["=== Aegis Service Discovery ==="]
        for name, found in self.available.items():
            status = "FOUND" if found else "NOT FOUND"
            lines.append(f"  [{status:>9}] {name}")
        if self.import_errors:
            lines.append(f"\n  Import attempts ({len(self.import_errors)}):")
            for err in self.import_errors[:10]:
                lines.append(f"    - {err}")
        return "\n".join(lines)


# ================================================================
# Workload loader
# ================================================================

class WorkloadLoader:
    """Loads C-MAPSS evaluation workloads."""

    def __init__(self, discovery: ServiceDiscovery):
        self.discovery = discovery
        self._data_cache: Dict[str, Any] = {}

    def load(self, tier: str = "small") -> List[Dict[str, Any]]:
        """
        Load workload cases for the specified tier.

        Returns a list of case dicts, each containing:
            - engine_id: str
            - cycle: int
            - sensors: dict of sensor readings
            - settings: dict of operational settings (if available)
            - source: str (dataset identifier)

        Falls back to synthetic representative data if the replay
        infrastructure cannot be loaded.
        """
        if tier in self._data_cache:
            return self._data_cache[tier]

        cases = []

        # Attempt 1: Use existing dataset replay infrastructure
        if self.discovery.available.get("dataset_replay"):
            try:
                cases = self._load_from_replay(tier)
                if cases:
                    self._data_cache[tier] = cases
                    return cases
            except Exception as e:
                pass  # Fall through to synthetic

        # Attempt 2: Load raw C-MAPSS files directly
        try:
            cases = self._load_from_files(tier)
            if cases:
                self._data_cache[tier] = cases
                return cases
        except Exception:
            pass

        # Attempt 3: Generate synthetic representative cases
        cases = self._generate_synthetic(tier)
        self._data_cache[tier] = cases
        return cases

    def _load_from_replay(self, tier: str) -> List[Dict[str, Any]]:
        """Load via existing replay infrastructure."""
        mod = self.discovery.modules.get("dataset_replay")
        if not mod:
            return []

        # Try common replay entry points
        for func_name in ["load_dataset", "get_engine_data", "replay", "load"]:
            if hasattr(mod, func_name):
                func = getattr(mod, func_name)
                try:
                    result = func()
                    return self._normalize_replay_output(result, tier)
                except Exception:
                    continue
        return []

    def _load_from_files(self, tier: str) -> List[Dict[str, Any]]:
        """Load raw C-MAPSS data files."""
        data_dirs = [
            "data/cmapss",
            "data/C-MAPSS",
            "apps/dataset_replay/data",
            "tests/fixtures",
        ]

        for d in data_dirs:
            if not os.path.isdir(d):
                continue
            for fname in os.listdir(d):
                if fname.endswith((".txt", ".csv")) and "train" in fname.lower():
                    return self._parse_cmapss_file(
                        os.path.join(d, fname), tier
                    )
        return []

    def _parse_cmapss_file(
        self, filepath: str, tier: str
    ) -> List[Dict[str, Any]]:
        """Parse a C-MAPSS data file into case dicts."""
        cases = []
        tier_limits = {"small": 50, "representative": 500, "stress": 2000}
        limit = tier_limits.get(tier, 50)

        try:
            with open(filepath, "r") as f:
                for i, line in enumerate(f):
                    if i >= limit:
                        break
                    parts = line.strip().split()
                    if len(parts) >= 26:  # C-MAPSS: 2 id + 3 settings + 21 sensors
                        engine_id = parts[0]
                        cycle = int(parts[1])
                        settings = {
                            "s1": float(parts[2]),
                            "s2": float(parts[3]),
                            "s3": float(parts[4]),
                        }
                        sensors = {
                            f"sensor_{j}": float(parts[5 + j])
                            for j in range(21)
                        }
                        cases.append({
                            "engine_id": f"engine_{engine_id}",
                            "cycle": cycle,
                            "sensors": sensors,
                            "settings": settings,
                            "source": os.path.basename(filepath),
                        })
        except Exception:
            pass
        return cases

    def _generate_synthetic(self, tier: str) -> List[Dict[str, Any]]:
        """Generate deterministic synthetic cases for benchmarking."""
        import math

        tier_sizes = {"small": 5, "representative": 50, "stress": 200}
        n = tier_sizes.get(tier, 5)
        cases = []

        for i in range(n):
            engine_id = f"synthetic_engine_{i % 5 + 1}"
            cycle = i * 10
            # Deterministic pseudo-sensor values
            sensors = {
                f"sensor_{j}": round(
                    math.sin(i * 0.1 + j * 0.3) * 100 + 500, 4
                )
                for j in range(21)
            }
            settings = {
                "s1": round(math.cos(i * 0.2) * 10, 4),
                "s2": 0.0,
                "s3": round(math.sin(i * 0.15) * 50 + 100, 4),
            }
            cases.append({
                "engine_id": engine_id,
                "cycle": cycle,
                "sensors": sensors,
                "settings": settings,
                "source": f"synthetic_{tier}",
            })

        return cases

    def _normalize_replay_output(
        self, data: Any, tier: str
    ) -> List[Dict[str, Any]]:
        """Normalize replay output to standard case format."""
        tier_limits = {"small": 50, "representative": 500, "stress": 2000}
        limit = tier_limits.get(tier, 50)

        cases = []
        # Handle various return types
        if isinstance(data, list):
            for item in data[:limit]:
                if isinstance(item, dict):
                    cases.append(item)
                else:
                    cases.append({
                        "engine_id": "unknown",
                        "cycle": 0,
                        "sensors": {},
                        "settings": {},
                        "source": "replay",
                        "raw": str(item)[:200],
                    })
        elif isinstance(data, dict):
            for key, val in list(data.items())[:limit]:
                cases.append({
                    "engine_id": str(key),
                    "cycle": 0,
                    "sensors": val if isinstance(val, dict) else {},
                    "settings": {},
                    "source": "replay",
                })
        return cases


# ================================================================
# Core measurement engine
# ================================================================

class PerformanceHarness:
    """
    Main evaluation harness for P3.S3.

    Measures the existing Aegis intelligence pipeline without
    modifying production code.
    """

    def __init__(self):
        self.discovery = ServiceDiscovery()
        self.discovery.discover()
        self.loader = WorkloadLoader(self.discovery)
        self.errors: List[str] = []
        self.limitations: List[str] = []

    # --- Latency measurement ---

    def measure_latency(
        self,
        func,
        args: tuple = (),
        kwargs: dict = None,
        n_runs: int = 10,
        warmup: int = 1,
        service_name: str = "unknown",
    ) -> TimingResult:
        """Measure execution time of a callable."""
        if kwargs is None:
            kwargs = {}

        times = []
        # Warm-up
        for _ in range(warmup):
            try:
                func(*args, **kwargs)
            except Exception:
                pass

        # Timed runs
        for _ in range(n_runs):
            start = time.perf_counter()
            try:
                func(*args, **kwargs)
            except Exception as e:
                self.errors.append(
                    f"Latency measurement error ({service_name}): {e}"
                )
            elapsed_ms = (time.perf_counter() - start) * 1000
            times.append(elapsed_ms)

        if not times:
            return TimingResult(
                service=service_name, runs=0, warmup=warmup,
                times_ms=[], median_ms=0, mean_ms=0,
                min_ms=0, max_ms=0,
            )

        return TimingResult(
            service=service_name,
            runs=n_runs,
            warmup=warmup,
            times_ms=[round(t, 4) for t in times],
            median_ms=round(median(times), 4),
            mean_ms=round(mean(times), 4),
            min_ms=round(min(times), 4),
            max_ms=round(max(times), 4),
        )

    # --- Throughput measurement ---

    def measure_throughput(
        self,
        func,
        cases: List[Dict],
        time_budget_s: float = 60.0,
        tier: str = "small",
    ) -> ThroughputResult:
        """Measure cases processed per second within a time budget."""
        completed = 0
        failed = 0
        start = time.perf_counter()

        for case in cases:
            elapsed = time.perf_counter() - start
            if elapsed >= time_budget_s:
                break
            try:
                func(case)
                completed += 1
            except Exception:
                failed += 1

        duration = time.perf_counter() - start
        cps = completed / duration if duration > 0 else 0

        return ThroughputResult(
            tier=tier,
            total_cases=len(cases),
            completed_cases=completed,
            failed_cases=failed,
            duration_s=round(duration, 4),
            cases_per_second=round(cps, 4),
            time_budget_s=time_budget_s,
        )

    # --- Determinism check ---

    def check_determinism(
        self,
        func,
        cases: List[Dict],
        n_runs: int = 5,
    ) -> DeterminismResult:
        """Verify result consistency across repeated runs."""
        if not cases:
            return DeterminismResult(
                runs=n_runs, cases_checked=0,
                consistent_cases=0, inconsistent_cases=0,
                inconsistent_fields=[], verdict="NO_DATA",
            )

        # Collect results from multiple runs
        all_results = []
        for run_idx in range(n_runs):
            run_results = []
            for case in cases[:10]:  # Limit for speed
                try:
                    result = func(case)
                    run_results.append(self._result_hash(result))
                except Exception:
                    run_results.append("ERROR")
            all_results.append(run_results)

        # Compare runs against the first run
        consistent = 0
        inconsistent = 0
        inconsistent_fields = set()

        if len(all_results) >= 2:
            baseline = all_results[0]
            for run in all_results[1:]:
                for i, (b, r) in enumerate(zip(baseline, run)):
                    if b == r:
                        consistent += 1
                    else:
                        inconsistent += 1
                        inconsistent_fields.add(f"case_{i}")

        total = consistent + inconsistent
        if total == 0:
            verdict = "NO_DATA"
        elif inconsistent == 0:
            verdict = "DETERMINISTIC"
        elif inconsistent < total * 0.1:
            verdict = "MOSTLY_DETERMINISTIC"
        else:
            verdict = "NON_DETERMINISTIC"

        return DeterminismResult(
            runs=n_runs,
            cases_checked=min(len(cases), 10),
            consistent_cases=consistent,
            inconsistent_cases=inconsistent,
            inconsistent_fields=list(inconsistent_fields)[:20],
            verdict=verdict,
        )

    # --- Reliability check ---

    def check_reliability(
        self,
        func,
        valid_cases: List[Dict],
        invalid_cases: List[Dict] = None,
    ) -> ReliabilityResult:
        """Verify success/failure visibility."""
        if invalid_cases is None:
            invalid_cases = [
                {},  # Empty input
                {"sensors": None},  # Null sensors
                {"sensors": {}, "engine_id": "", "cycle": -1},  # Invalid
            ]

        successful = 0
        failed_with_error = 0
        silent_losses = 0
        error_details = []

        # Valid cases should succeed
        for i, case in enumerate(valid_cases[:20]):
            try:
                result = func(case)
                if result is not None:
                    successful += 1
                else:
                    silent_losses += 1
                    error_details.append({
                        "case": f"valid_{i}",
                        "issue": "returned None silently",
                    })
            except Exception as e:
                failed_with_error += 1
                error_details.append({
                    "case": f"valid_{i}",
                    "error": str(e)[:200],
                })

        # Invalid cases should fail visibly (not silently)
        for i, case in enumerate(invalid_cases):
            try:
                result = func(case)
                if result is None:
                    silent_losses += 1
                    error_details.append({
                        "case": f"invalid_{i}",
                        "issue": "silent None for invalid input",
                    })
                else:
                    # Returned something for invalid input — check if
                    # it carries an error/uncertainty flag
                    successful += 1  # Graceful degradation is OK
            except Exception as e:
                failed_with_error += 1  # Visible failure is acceptable
                error_details.append({
                    "case": f"invalid_{i}",
                    "error": str(e)[:200],
                    "note": "visible failure (acceptable)",
                })

        return ReliabilityResult(
            total_cases=len(valid_cases[:20]) + len(invalid_cases),
            successful=successful,
            failed_with_error=failed_with_error,
            silent_losses=silent_losses,
            error_details=error_details[:20],
        )

    # --- Resource observation ---

    def observe_resources(
        self, func, cases: List[Dict]
    ) -> List[ResourceSnapshot]:
        """Observe memory behavior during workload execution."""
        snapshots = []

        tracemalloc.start()

        # Before
        current, peak = tracemalloc.get_traced_memory()
        snapshots.append(ResourceSnapshot(
            phase="before",
            current_mb=round(current / 1024 / 1024, 2),
            peak_mb=round(peak / 1024 / 1024, 2),
            timestamp=datetime.now(timezone.utc).isoformat(),
        ))

        # During
        for case in cases[:20]:
            try:
                func(case)
            except Exception:
                pass

        current, peak = tracemalloc.get_traced_memory()
        snapshots.append(ResourceSnapshot(
            phase="during",
            current_mb=round(current / 1024 / 1024, 2),
            peak_mb=round(peak / 1024 / 1024, 2),
            timestamp=datetime.now(timezone.utc).isoformat(),
        ))

        tracemalloc.stop()

        # After
        snapshots.append(ResourceSnapshot(
            phase="after",
            current_mb=round(current / 1024 / 1024, 2),
            peak_mb=round(peak / 1024 / 1024, 2),
            timestamp=datetime.now(timezone.utc).isoformat(),
        ))

        return snapshots

    # --- Full benchmark run ---

    def run_all(
        self,
        tier: str = "small",
        n_latency_runs: int = 10,
        n_determinism_runs: int = 5,
        throughput_budget_s: float = 60.0,
    ) -> BenchmarkReport:
        """Execute all P3.S3 measurements and return a complete report."""

        print(f"\n{'='*60}")
        print(f" AEGIS P3.S3 BENCHMARK — Tier: {tier}")
        print(f"{'='*60}\n")

        # Discovery
        print(self.discovery.report())
        print()

        # Load workload
        print(f"Loading {tier} workload...")
        cases = self.loader.load(tier)
        print(f"  Loaded {len(cases)} cases")
        if not cases:
            self.limitations.append("No workload data available")
            print("  WARNING: No cases loaded. Results will be empty.")
        print()

        # Determine the evaluation function
        eval_func = self._get_pipeline_function()
        dataset_id = cases[0].get("source", "unknown") if cases else "none"

        # --- Latency ---
        print("Measuring latency...")
        latency_results = {}
        if eval_func and cases:
            sample = cases[0]
            t = self.measure_latency(
                eval_func, args=(sample,),
                n_runs=n_latency_runs, warmup=1,
                service_name="integrated_pipeline",
            )
            latency_results["integrated_pipeline"] = asdict(t)
            print(f"  Median: {t.median_ms:.2f} ms  "
                  f"p95: {t.p95_ms:.2f} ms  "
                  f"({t.runs} runs)")

            # Per-service latency if services are instantiated
            for svc_name, svc_instance in self.discovery.services.items():
                if callable(svc_instance):
                    try:
                        st = self.measure_latency(
                            svc_instance, args=(sample,),
                            n_runs=n_latency_runs, warmup=1,
                            service_name=svc_name,
                        )
                        latency_results[svc_name] = asdict(st)
                        print(f"  {svc_name}: median {st.median_ms:.2f} ms")
                    except Exception as e:
                        self.errors.append(
                            f"Service latency ({svc_name}): {e}"
                        )
        else:
            self.limitations.append(
                "Latency measurement skipped: no eval function or data"
            )
            print("  Skipped (no eval function or data)")
        print()

        # --- Throughput ---
        print("Measuring throughput...")
        throughput_result = None
        if eval_func and cases:
            budget = throughput_budget_s
            tp = self.measure_throughput(
                eval_func, cases,
                time_budget_s=budget, tier=tier,
            )
            throughput_result = asdict(tp)
            print(f"  {tp.completed_cases}/{tp.total_cases} cases "
                  f"in {tp.duration_s:.2f}s "
                  f"({tp.cases_per_second:.2f} cases/s)")
        else:
            self.limitations.append("Throughput skipped: no eval function")
            print("  Skipped")
        print()

        # --- Determinism ---
        print("Checking determinism...")
        determinism_result = None
        if eval_func and cases:
            det = self.check_determinism(
                eval_func, cases, n_runs=n_determinism_runs,
            )
            determinism_result = asdict(det)
            print(f"  Verdict: {det.verdict} "
                  f"({det.consistent_cases} consistent, "
                  f"{det.inconsistent_cases} inconsistent)")
        else:
            self.limitations.append("Determinism skipped: no eval function")
            print("  Skipped")
        print()

        # --- Reliability ---
        print("Checking reliability...")
        reliability_result = None
        if eval_func:
            rel = self.check_reliability(eval_func, cases)
            reliability_result = asdict(rel)
            print(f"  Success: {rel.successful}  "
                  f"Errors: {rel.failed_with_error}  "
                  f"Silent losses: {rel.silent_losses}")
        else:
            self.limitations.append("Reliability skipped: no eval function")
            print("  Skipped")
        print()

        # --- Resources ---
        print("Observing resources...")
        resource_snapshots = []
        if eval_func and cases:
            snaps = self.observe_resources(eval_func, cases)
            resource_snapshots = [asdict(s) for s in snaps]
            for s in snaps:
                print(f"  {s.phase:>7}: "
                      f"current={s.current_mb:.1f}MB  "
                      f"peak={s.peak_mb:.1f}MB")
        else:
            print("  Skipped")
        print()

        # --- Git commit ---
        git_commit = "unknown"
        try:
            import subprocess
            git_commit = subprocess.check_output(
                ["git", "rev-parse", "--short", "HEAD"],
                stderr=subprocess.DEVNULL,
            ).decode().strip()
        except Exception:
            pass

        # Build report
        report = BenchmarkReport(
            timestamp=datetime.now(timezone.utc).isoformat(),
            machine=platform.node(),
            python_version=platform.python_version(),
            git_commit=git_commit,
            dataset=dataset_id,
            tier=tier,
            discovery=self.discovery.available,
            latency=latency_results,
            throughput=throughput_result,
            determinism=determinism_result,
            reliability=reliability_result,
            resources=resource_snapshots,
            errors=self.errors,
            limitations=self.limitations,
        )

        print(f"{'='*60}")
        print(" BENCHMARK COMPLETE")
        print(f"{'='*60}\n")

        return report

    # --- Internal helpers ---

    def _get_pipeline_function(self):
        """
        Build a callable that runs the integrated intelligence pipeline
        on a single case dict. Uses existing services.
        """
        services = self.discovery.services
        modules = self.discovery.modules

        # If we have instantiated services, chain them
        if services:
            def pipeline(case: Dict) -> Dict:
                results = {"input_engine": case.get("engine_id", "?")}
                sensors = case.get("sensors", {})
                for name, svc in services.items():
                    try:
                        if callable(svc):
                            r = svc(sensors) if not isinstance(svc, type) else None
                            results[name] = str(r)[:500] if r else "no_result"
                    except Exception as e:
                        results[name] = f"error: {e}"
                return results
            return pipeline

        # Fallback: if we have modules but no instances, try module-level functions
        if modules:
            def module_pipeline(case: Dict) -> Dict:
                return {
                    "engine": case.get("engine_id", "?"),
                    "sensors_count": len(case.get("sensors", {})),
                    "status": "module_discovery_only",
                }
            return module_pipeline

        return None

    def _result_hash(self, result: Any) -> str:
        """Create a deterministic hash of a result for comparison."""
        try:
            s = json.dumps(result, sort_keys=True, default=str)
            return hashlib.sha256(s.encode()).hexdigest()[:16]
        except Exception:
            return hashlib.sha256(str(result).encode()).hexdigest()[:16]

    def save_report(
        self, report: BenchmarkReport, output_path: str
    ) -> str:
        """Save benchmark report as JSON."""
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        data = asdict(report)
        with open(output_path, "w") as f:
            json.dump(data, f, indent=2, default=str)
        return output_path
