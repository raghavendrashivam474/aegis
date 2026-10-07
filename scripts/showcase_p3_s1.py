"""
Aegis P3.S1 Showcase — Fleet-Wide Intelligence Evaluation

Executes the protected Phase 2 intelligence pipeline across C-MAPSS engine
trajectories and displays quantitative evaluation metrics.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from packages.evaluation.benchmark import FleetBenchmarkHarness
from packages.evaluation.case_generator import generate_fleet_evaluation_cases
from packages.evaluation.metrics import (
    compute_detection_metrics,
    compute_fleet_summary,
)


def run_showcase():
    print("=" * 72)
    print("  AEGIS PHASE 3.S1: FLEET-WIDE INTELLIGENCE BENCHMARK REPORT")
    print("=" * 72)

    harness = FleetBenchmarkHarness()
    dataset_path = "datasets/cmapss_fd001/train_FD001.txt"
    print(f"\n[1] Loading C-MAPSS trajectories from: {dataset_path}")
    trajectories = harness.load_cmapss_trajectories(dataset_path)
    print(f"    Engines loaded: {len(trajectories)}")
    for eng_id, obs_list in sorted(trajectories.items()):
        max_cycle = max(o.metadata.get("cycle", 0) for o in obs_list)
        print(f"    - {eng_id}: {len(obs_list)} observations ({max_cycle} cycles)")

    fleet_tuples = []
    for eng_id, obs_list in sorted(trajectories.items()):
        max_cycle = max(o.metadata.get("cycle", 0) for o in obs_list)
        fleet_tuples.append((eng_id, max_cycle))

    cases = generate_fleet_evaluation_cases(
        engine_trajectories=fleet_tuples,
        nominal_cutoff_ratio=0.35,
        degradation_lead_cycles=30,
    )
    print(f"\n[2] Generated {len(cases)} evaluation cases across {len(fleet_tuples)} engines")

    print("\n[3] Executing Aegis Intelligence Chain...")
    results = harness.run_fleet_benchmark(cases, trajectories)

    summary = compute_fleet_summary(results)
    det = compute_detection_metrics(results)

    pass_pct = summary["pass_rate"] * 100
    prec_str = f"{det.precision * 100:.1f}%" if det.precision is not None else "0.0%"
    rec_str = f"{det.recall * 100:.1f}%" if det.recall is not None else "0.0%"
    f1_str = f"{det.f1 * 100:.1f}%" if det.f1 is not None else "0.0%"
    fpr_str = (
        f"{det.false_positive_rate * 100:.1f}%" if det.false_positive_rate is not None else "0.0%"
    )

    print("\n" + "=" * 72)
    print("  BENCHMARK EVALUATION RESULTS")
    print("=" * 72)
    print(f"  Total Cases Evaluated:       {summary['total_cases']}")
    print(f"  Passed Cases:                {summary['passed_cases']} ({pass_pct:.1f}%)")
    print("-" * 72)
    print("  DETECTION METRICS (Binary Classification):")
    print(f"    True Positives (TP):       {det.true_positives}")
    print(f"    True Negatives (TN):       {det.true_negatives}")
    print(f"    False Positives (FP):      {det.false_positives}")
    print(f"    False Negatives (FN):      {det.false_negatives}")
    print(f"    Precision:                 {prec_str}")
    print(f"    Recall (Sensitivity):      {rec_str}")
    print(f"    F1 Score:                  {f1_str}")
    print(f"    False Positive Rate (FPR): {fpr_str}")
    print("-" * 72)
    print("  OPERATIONAL RISK & DIAGNOSTIC METRICS:")
    print(f"    Degraded Windows Evaluated:{summary['degraded_count']}")
    esc_rate = summary["correct_risk_escalation_rate"]
    print(f"    Correct Risk Escalation:   {esc_rate * 100 if esc_rate is not None else 0.0:.1f}%")
    print(f"    Nominal Windows Evaluated: {summary['nominal_count']}")
    false_esc = summary["false_risk_escalation_rate"]
    print(
        f"    False Risk Escalation:     {false_esc * 100 if false_esc is not None else 0.0:.1f}%"
    )
    print("-" * 72)

    print("\n[4] Verifying Deterministic Reproducibility (Run 1 vs Run 2)...")
    results_repeat = harness.run_fleet_benchmark(cases, trajectories)
    identical = True
    for r1, r2 in zip(results, results_repeat, strict=False):
        if (
            r1.anomaly_score != r2.anomaly_score
            or r1.operational_state != r2.operational_state
            or r1.priority != r2.priority
            or r1.passed != r2.passed
        ):
            identical = False
            break

    print(f"  Determinism Check:           {'PASS (100% Bit-Identical)' if identical else 'FAIL'}")
    print("=" * 72)


if __name__ == "__main__":
    run_showcase()
