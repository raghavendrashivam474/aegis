"""
P3 Evaluation — Data Models

Defines ground-truth labels, evaluation results, and benchmark
aggregation structures used by the fleet evaluation harness.

These models are evaluation-only. They do not modify or extend
the production intelligence domain models.
"""

from dataclasses import dataclass
from enum import Enum


class GroundTruthLabel(Enum):
    """Ground-truth lifecycle label for an engine trajectory window."""

    NOMINAL = "NOMINAL"
    DEGRADING = "DEGRADING"
    FAILURE_BOUND = "FAILURE_BOUND"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class EvaluationCase:
    """A single evaluation case: one engine, one window, one ground truth."""

    engine_id: str
    window_start: int
    window_end: int
    ground_truth: GroundTruthLabel
    notes: str = ""


@dataclass(frozen=True)
class EvaluationResult:
    """The outcome of running one evaluation case through the Aegis pipeline."""

    case: EvaluationCase
    operational_state: str
    anomaly_status: str
    anomaly_score: float
    diagnostic_status: str
    priority: str
    confidence: float
    passed: bool
    reason: str = ""


@dataclass
class DetectionMetrics:
    """Aggregate detection metrics across a fleet evaluation run."""

    true_positives: int = 0
    true_negatives: int = 0
    false_positives: int = 0
    false_negatives: int = 0

    @property
    def precision(self) -> float | None:
        denom = self.true_positives + self.false_positives
        return self.true_positives / denom if denom > 0 else None

    @property
    def recall(self) -> float | None:
        denom = self.true_positives + self.false_negatives
        return self.true_positives / denom if denom > 0 else None

    @property
    def f1(self) -> float | None:
        p, r = self.precision, self.recall
        if p is None or r is None or (p + r) == 0:
            return None
        return 2 * p * r / (p + r)

    @property
    def false_positive_rate(self) -> float | None:
        denom = self.false_positives + self.true_negatives
        return self.false_positives / denom if denom > 0 else None
