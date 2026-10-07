"""
P3 Evaluation — Metric Calculation

Pure functions for computing detection, lead time, diagnostic,
and operational risk metrics from EvaluationResult collections.
"""

import statistics
from typing import Any

from packages.evaluation.models import DetectionMetrics, EvaluationResult, GroundTruthLabel


def compute_detection_metrics(
    results: list[EvaluationResult],
) -> DetectionMetrics:
    """Compute TP/TN/FP/FN from evaluation results."""
    metrics = DetectionMetrics()

    for res in results:
        gt = res.case.ground_truth
        if gt == GroundTruthLabel.UNKNOWN:
            continue

        is_pred_positive = (
            "DEGRADATION" in res.anomaly_status.upper()
            or "ANOMALY" in res.anomaly_status.upper()
            or res.anomaly_score > 0.6
        )

        if gt in (GroundTruthLabel.DEGRADING, GroundTruthLabel.FAILURE_BOUND):
            if is_pred_positive:
                metrics.true_positives += 1
            else:
                metrics.false_negatives += 1
        elif gt == GroundTruthLabel.NOMINAL:
            if is_pred_positive:
                metrics.false_positives += 1
            else:
                metrics.true_negatives += 1

    return metrics


def compute_lead_time_statistics(lead_times: list[int]) -> dict[str, float | None]:
    """Compute summary statistics for detection lead times (in cycles)."""
    if not lead_times:
        return {
            "count": 0,
            "mean": None,
            "median": None,
            "min": None,
            "max": None,
        }

    return {
        "count": len(lead_times),
        "mean": float(statistics.mean(lead_times)),
        "median": float(statistics.median(lead_times)),
        "min": float(min(lead_times)),
        "max": float(max(lead_times)),
    }


def compute_fleet_summary(results: list[EvaluationResult]) -> dict[str, Any]:
    """Compute aggregate benchmark summary including detection, diagnosis and risk."""
    detection = compute_detection_metrics(results)

    total_evaluated = len(results)
    total_passed = sum(1 for r in results if r.passed)

    degraded_cases = [
        r
        for r in results
        if r.case.ground_truth in (GroundTruthLabel.DEGRADING, GroundTruthLabel.FAILURE_BOUND)
    ]
    correct_risk_escalations = sum(
        1 for r in degraded_cases if r.priority.upper() in ("HIGH", "CRITICAL")
    )

    nominal_cases = [r for r in results if r.case.ground_truth == GroundTruthLabel.NOMINAL]
    false_escalations = sum(1 for r in nominal_cases if r.priority.upper() in ("HIGH", "CRITICAL"))

    esc_rate = (correct_risk_escalations / len(degraded_cases)) if degraded_cases else None
    false_rate = (false_escalations / len(nominal_cases)) if nominal_cases else None

    return {
        "total_cases": total_evaluated,
        "passed_cases": total_passed,
        "pass_rate": (total_passed / total_evaluated) if total_evaluated > 0 else 0.0,
        "true_positives": detection.true_positives,
        "true_negatives": detection.true_negatives,
        "false_positives": detection.false_positives,
        "false_negatives": detection.false_negatives,
        "precision": detection.precision,
        "recall": detection.recall,
        "f1": detection.f1,
        "false_positive_rate": detection.false_positive_rate,
        "degraded_count": len(degraded_cases),
        "correct_risk_escalation_rate": esc_rate,
        "nominal_count": len(nominal_cases),
        "false_risk_escalation_rate": false_rate,
    }
