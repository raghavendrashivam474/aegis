"""
P3 Evaluation — Evaluation Case Generation

Constructs standardized EvaluationCase instances from dataset trajectories.
Maps lifecycle windows to explicit ground-truth expectations.
"""

from packages.evaluation.models import EvaluationCase, GroundTruthLabel


def generate_engine_evaluation_cases(
    engine_id: str,
    total_cycles: int,
    nominal_cutoff_ratio: float = 0.3,
    degradation_lead_cycles: int = 30,
    min_window_size: int = 10,
) -> list[EvaluationCase]:
    """Generate evaluation cases across an engine's lifecycle.

    Rules:
    - Early window (1 to cutoff): GroundTruth = NOMINAL
    - Late window (T_max - lead to T_max): GroundTruth = DEGRADING
    - Sub-minimum window (< min_window_size): GroundTruth = UNKNOWN
    """
    cases: list[EvaluationCase] = []

    if total_cycles < min_window_size:
        cases.append(
            EvaluationCase(
                engine_id=engine_id,
                window_start=1,
                window_end=total_cycles,
                ground_truth=GroundTruthLabel.UNKNOWN,
                notes="Trajectory shorter than minimum window",
            )
        )
        return cases

    # 1. Nominal case (early life)
    early_end = max(min_window_size, int(total_cycles * nominal_cutoff_ratio))
    cases.append(
        EvaluationCase(
            engine_id=engine_id,
            window_start=1,
            window_end=early_end,
            ground_truth=GroundTruthLabel.NOMINAL,
            notes=f"Early lifecycle window (1-{early_end} of {total_cycles})",
        )
    )

    # 2. Degrading case (late life / failure bound)
    late_start = max(1, total_cycles - degradation_lead_cycles)
    cases.append(
        EvaluationCase(
            engine_id=engine_id,
            window_start=late_start,
            window_end=total_cycles,
            ground_truth=GroundTruthLabel.DEGRADING,
            notes=f"Late lifecycle window ({late_start}-{total_cycles} of {total_cycles})",
        )
    )

    return cases


def generate_fleet_evaluation_cases(
    engine_trajectories: list[tuple[str, int]],
    nominal_cutoff_ratio: float = 0.3,
    degradation_lead_cycles: int = 30,
) -> list[EvaluationCase]:
    """Generate evaluation cases for a list of (engine_id, total_cycles)."""
    fleet_cases: list[EvaluationCase] = []
    for engine_id, total_cycles in engine_trajectories:
        fleet_cases.extend(
            generate_engine_evaluation_cases(
                engine_id=engine_id,
                total_cycles=total_cycles,
                nominal_cutoff_ratio=nominal_cutoff_ratio,
                degradation_lead_cycles=degradation_lead_cycles,
            )
        )
    return fleet_cases
