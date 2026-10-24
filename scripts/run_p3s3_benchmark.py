#!/usr/bin/env python3
"""
P3.S3 Benchmark Runner

Entry point for the Aegis P3.S3 Performance & Reliability Evaluation.

Usage:
    python scripts/run_p3s3_benchmark.py [OPTIONS]

Options:
    --tier          small | representative | stress  (default: small)
    --runs          Number of latency repetitions    (default: 10)
    --determinism   Number of determinism runs       (default: 5)
    --budget        Throughput time budget in seconds (default: 60)
    --discover      Only run service discovery, then exit
    --output        Output JSON path                  (default: auto)

Examples:
    python scripts/run_p3s3_benchmark.py --discover
    python scripts/run_p3s3_benchmark.py --tier small
    python scripts/run_p3s3_benchmark.py --tier representative --budget 120
"""

import sys
import os
import argparse
from datetime import datetime

# Ensure project root is on the path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)


def main():
    parser = argparse.ArgumentParser(
        description="Aegis P3.S3 Performance & Reliability Benchmark"
    )
    parser.add_argument(
        "--tier",
        choices=["small", "representative", "stress"],
        default="small",
        help="Workload tier (default: small)",
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=10,
        help="Latency measurement repetitions (default: 10)",
    )
    parser.add_argument(
        "--determinism",
        type=int,
        default=5,
        help="Determinism check runs (default: 5)",
    )
    parser.add_argument(
        "--budget",
        type=float,
        default=60.0,
        help="Throughput time budget in seconds (default: 60)",
    )
    parser.add_argument(
        "--discover",
        action="store_true",
        help="Run service discovery only, then exit",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output JSON path (default: auto-generated)",
    )

    args = parser.parse_args()

    # Import harness
    try:
        from packages.evaluation.performance_harness import (
            PerformanceHarness,
            ServiceDiscovery,
        )
    except ImportError as e:
        print(f"ERROR: Cannot import performance harness: {e}")
        print(f"  sys.path: {sys.path[:3]}")
        print(f"  CWD: {os.getcwd()}")
        sys.exit(1)

    # Discovery-only mode
    if args.discover:
        print("\n=== AEGIS P3.S3 — SERVICE DISCOVERY ===\n")
        sd = ServiceDiscovery()
        sd.discover()
        print(sd.report())
        print(f"\nImport errors: {len(sd.import_errors)}")
        for err in sd.import_errors:
            print(f"  - {err}")
        print()
        return

    # Full benchmark
    harness = PerformanceHarness()
    report = harness.run_all(
        tier=args.tier,
        n_latency_runs=args.runs,
        n_determinism_runs=args.determinism,
        throughput_budget_s=args.budget,
    )

    # Save report
    if args.output:
        out_path = args.output
    else:
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        out_dir = os.path.join(
            project_root, "docs", "phases", "phase3", "s3", "evidence"
        )
        out_path = os.path.join(
            out_dir, f"benchmark-{args.tier}-{ts}.json"
        )

    saved = harness.save_report(report, out_path)
    print(f"Report saved to: {saved}")
    print(f"Errors: {len(report.errors)}")
    print(f"Limitations: {len(report.limitations)}")

    if report.errors:
        print("\nErrors:")
        for e in report.errors[:10]:
            print(f"  - {e}")

    if report.limitations:
        print("\nLimitations:")
        for lim in report.limitations:
            print(f"  - {lim}")


if __name__ == "__main__":
    main()

