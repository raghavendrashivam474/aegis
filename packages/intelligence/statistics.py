"""
Aegis Intelligence — Pure Statistical Functions.
No side effects, no I/O, no framework dependencies.
All functions operate on plain lists of floats.
Fully deterministic given the same inputs.
"""
from __future__ import annotations

import math

from domain.intelligence import TrendDirection


def compute_mean(values: list[float]) -> float:
    """Arithmetic mean. Returns 0.0 for empty input."""
    if not values:
        return 0.0
    return sum(values) / len(values)


def compute_std(values: list[float], mean: float | None = None) -> float:
    """Sample standard deviation (Bessel-corrected). Returns 0.0 for n < 2."""
    if len(values) < 2:
        return 0.0
    if mean is None:
        mean = compute_mean(values)
    variance = sum((v - mean) ** 2 for v in values) / (len(values) - 1)
    return math.sqrt(variance)


def compute_trend(
    values: list[float],
    slope_threshold: float = 0.001,
) -> TrendDirection:
    """
    Determine trend direction via simple linear regression slope.

    The slope is normalized against the signal magnitude so that
    the threshold is relative, not absolute.

    Returns UNKNOWN if fewer than 3 data points.
    """
    n = len(values)
    if n < 3:
        return TrendDirection.UNKNOWN

    mean_val = compute_mean(values)

    # Normalize threshold relative to signal magnitude
    if abs(mean_val) < 1e-10:
        normalized_threshold = slope_threshold
    else:
        normalized_threshold = slope_threshold * abs(mean_val)

    # Simple linear regression: y = a + b*x, where x = 0, 1, 2, ...
    x_mean = (n - 1) / 2.0
    numerator = sum((i - x_mean) * (v - mean_val) for i, v in enumerate(values))
    denominator = sum((i - x_mean) ** 2 for i in range(n))

    if abs(denominator) < 1e-10:
        return TrendDirection.STABLE

    slope = numerator / denominator

    if abs(slope) < normalized_threshold:
        return TrendDirection.STABLE
    elif slope > 0:
        return TrendDirection.INCREASING
    else:
        return TrendDirection.DECREASING


def compute_deviation_score(
    current_mean: float,
    baseline_mean: float,
    baseline_std: float,
    epsilon: float = 1e-6,
) -> float:
    """
    Compute how many standard deviations the current mean is from baseline.
    Always returns a non-negative value.
    """
    return abs(current_mean - baseline_mean) / max(baseline_std, epsilon)


def compute_sensor_health(
    deviation_score: float,
    weight: float = 15.0,
) -> float:
    """
    Convert a deviation score to a 0–100 health contribution.
    A deviation of 0 → 100, deviation of 2σ with weight 15 → 70.
    """
    return max(0.0, 100.0 - (deviation_score * weight))

