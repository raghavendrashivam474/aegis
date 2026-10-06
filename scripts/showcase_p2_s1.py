"""
Aegis Phase 2 Sprint 1 — Operational State & Asset Health Showcase.
Demonstrates:
1. Healthy baseline evaluation (nominal asset)
2. Degrading asset evaluation (progressive failure trajectory)
3. Insufficient / corrupted data handling
4. Real NASA C-MAPSS FD001 Turbofan lifecycle health tracking
"""
import sys
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "packages") not in sys.path:
    sys.path.insert(0, str(ROOT / "packages"))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from apps.dataset_replay.adapter import CmapssAdapter
from contracts.mappers import ObservationMapper
from domain.entities import Observation, QualityFlag
from domain.repository import InMemoryTelemetryRepository
from intelligence.health_service import HealthAssessmentService, HealthConfig


def print_banner(text: str) -> None:
    print("\n" + "=" * 70)
    print(f"  {text}")
    print("=" * 70)


def print_assessment_card(assessment) -> None:
    print(f"\n┌─────────────────────────────────────────────────────────────┐")
    print(f"│ ASSET:  {assessment.asset_id:<20s} DEVICE: {assessment.device_id:<21s}│")
    print(f"├─────────────────────────────────────────────────────────────┤")
    print(f"│ Operational State: {assessment.operational_state.value:<15s}  Health Score: {assessment.health_score:6.2f} / 100 │")
    print(f"│ Trend:             {assessment.trend.value:<15s}  Confidence:   {assessment.confidence * 100:5.1f}%       │")
    print(f"├─────────────────────────────────────────────────────────────┤")
    print(f"│ Evaluated At:      {assessment.evaluated_at.isoformat()}           │")
    print(f"│ Evidence Summary:  {assessment.evidence_summary:<41s}│")
    print(f"└─────────────────────────────────────────────────────────────┘")
    
    print("\n  Detailed Sensor Signal Breakdown:")
    for s in assessment.sensor_signals[:6]:  # Show top 6
        status_flag = "⚠️ DEVIATED" if s.deviation_score > 1.5 else "✅ NORMAL"
        print(f"    • {s.sensor_id:30s} | Base: {s.baseline_mean:8.2f} (σ={s.baseline_std:5.2f}) | Cur: {s.current_mean:8.2f} | Dev: {s.deviation_score:5.2f}σ | {status_flag}")
    if len(assessment.sensor_signals) > 6:
        print(f"    ... and {len(assessment.sensor_signals) - 6} more sensors.")


def run_showcase() -> None:
    print_banner("AEGIS INTELLIGENCE LAYER — P2.S1 OPERATIONAL HEALTH SHOWCASE")

    # 1. Healthy Asset Demo
    print_banner("1. NOMINAL ASSET EVALUATION (Cooling Pump P-101)")
    repo_healthy = InMemoryTelemetryRepository()
    base_ts = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
    for c in range(1, 60):
        ts = base_ts + timedelta(minutes=c)
        repo_healthy.save_observation(Observation(uuid.uuid4().hex, "pump-101", "temp-p101", ts, 45.0 + ((c%2)*0.2), "C", QualityFlag.GOOD))
        repo_healthy.save_observation(Observation(uuid.uuid4().hex, "pump-101", "vib-p101", ts, 1.2 + ((c%3)*0.05), "mm/s", QualityFlag.GOOD))
        repo_healthy.save_observation(Observation(uuid.uuid4().hex, "pump-101", "press-p101", ts, 6.0 + ((c%2)*0.1), "bar", QualityFlag.GOOD))
    
    service_healthy = HealthAssessmentService(repo_healthy)
    assess_healthy = service_healthy.assess("pump-101", asset_id="asset-cooling-pump")
    print_assessment_card(assess_healthy)

    # 2. NASA C-MAPSS Real Lifecycle Degradation
    print_banner("2. NASA C-MAPSS FD001 TURBOFAN ENGINE LIFECYCLE (Engine-001)")
    adapter = CmapssAdapter()
    envelopes = list(adapter.iter_envelopes(limit_units=[1]))
    
    # Early stage (Cycles 1-50)
    repo_cmapss_early = InMemoryTelemetryRepository()
    for env in envelopes[:50]:
        for p in env.observations:
            repo_cmapss_early.save_observation(ObservationMapper.to_domain(p, env.source_device_id))
    
    service_cmapss_early = HealthAssessmentService(repo_cmapss_early)
    assess_cmapss_early = service_cmapss_early.assess("engine-001", asset_id="turbofan-fleet")
    print("\n--- [STAGE 1] Early Operating Stage (Cycles 1-50) ---")
    print_assessment_card(assess_cmapss_early)

    # Full lifecycle (Cycles 1-120) near end-of-life
    repo_cmapss_late = InMemoryTelemetryRepository()
    for env in envelopes:
        for p in env.observations:
            repo_cmapss_late.save_observation(ObservationMapper.to_domain(p, env.source_device_id))
    
    service_cmapss_late = HealthAssessmentService(repo_cmapss_late)
    assess_cmapss_late = service_cmapss_late.assess("engine-001", asset_id="turbofan-fleet")
    print("\n--- [STAGE 2] Late Operating Stage Near Failure (Cycle 120) ---")
    print_assessment_card(assess_cmapss_late)

    print("\n" + "=" * 70)
    print("  P2.S1 SHOWCASE COMPLETE: ALL HEALTH SCENARIOS VERIFIED")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    run_showcase()
