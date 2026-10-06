"""
Aegis Phase 2 Sprint 3 — Explainable Root-Cause Diagnostic Showcase.
Demonstrates:
1. Operational State & Health Assessment (P2.S1)
2. Multivariate Statistical Anomaly & Degradation Detection (P2.S2)
3. Structured Evidence, Context Extraction & Deterministic Hypotheses (P2.S3)
4. Full Evaluation on NASA C-MAPSS FD001 Turbofan Engine-001 Lifecycle
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
from intelligence.anomaly_service import AnomalyDetectionService
from intelligence.diagnostic_service import DiagnosticService
from intelligence.health_service import HealthAssessmentService


def print_banner(text: str) -> None:
    print("\n" + "=" * 80)
    print(f"  {text}")
    print("=" * 80)


def print_diagnostic_card(health, anomaly, diag) -> None:
    print("\n┌──────────────────────────────────────────────────────────────────────────────┐")
    print(f"│ ASSET:  {health.asset_id:<24s}  DEVICE: {health.device_id:<32s}│")
    print("├──────────────────────────────────────────────────────────────────────────────┤")
    print(f"│ Operational State:  {health.operational_state.value:<16s}  Health Score:    {health.health_score:6.2f} / 100         │")
    print(f"│ Anomaly Status:     {anomaly.status.value:<16s}  Anomaly Score:   {anomaly.anomaly_score:6.2f} / 1.00          │")
    print(f"│ Diagnostic Status:  {diag.status.value:<16s}  Overall Risk:    {diag.overall_risk.value:<16s} │")
    print(f"│ Diagnostic Conf.:   {diag.confidence * 100:5.1f}%            Affected Sensors:{diag.context.affected_sensors:2d} / {diag.context.total_sensors:<2d}              │")
    print("├──────────────────────────────────────────────────────────────────────────────┤")
    print(f"│ Primary Finding:    {diag.primary_finding:<56s}│")
    print("├──────────────────────────────────────────────────────────────────────────────┤")
    print(f"│ Limitations:        {diag.limitations:<56s}│")
    print("└──────────────────────────────────────────────────────────────────────────────┘")

    print("\n  Diagnostic Hypotheses Ranking:")
    for idx, hyp in enumerate(diag.hypotheses, 1):
        print(f"    [{idx}] Category: {hyp.category.value} (Confidence: {hyp.confidence * 100:.0f}%, Severity: {hyp.severity.value})")
        print(f"        Description: {hyp.description}")
        if hyp.supporting_evidence:
            print("        Supporting Evidence:")
            for s in hyp.supporting_evidence[:3]:
                print(f"          + {s}")
        if hyp.contradicting_evidence:
            print("        Contradicting / Attenuating Signals:")
            for c in hyp.contradicting_evidence[:2]:
                print(f"          - {c}")

    print("\n  Top Structured Signal Evidence:")
    for e in diag.evidence[:5]:
        flag = "🔴" if e.deviation_sigma >= 3.0 else ("🟡" if e.deviation_sigma >= 1.5 else "🟢")
        print(f"    • {flag} {e.sensor_id:30s} | Dev: {e.deviation_sigma:5.2f}σ | Trend: {e.trend.value:10s} | Persist: {e.persistence_count:2d}c")


def run_showcase() -> None:
    print_banner("AEGIS INTELLIGENCE LAYER — P2.S1 + P2.S2 + P2.S3 DIAGNOSTIC SHOWCASE")

    # 1. Nominal Asset Demo
    print_banner("1. NOMINAL ASSET EVALUATION (Centrifugal Pump P-101)")
    repo_healthy = InMemoryTelemetryRepository()
    base_ts = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
    for c in range(1, 60):
        ts = base_ts + timedelta(minutes=c)
        repo_healthy.save_observation(Observation(uuid.uuid4().hex, "pump-101", "temp-p101", ts, 45.0 + ((c%2)*0.2), "C", QualityFlag.GOOD))
        repo_healthy.save_observation(Observation(uuid.uuid4().hex, "pump-101", "vib-p101", ts, 1.2 + ((c%3)*0.05), "mm/s", QualityFlag.GOOD))
        repo_healthy.save_observation(Observation(uuid.uuid4().hex, "pump-101", "press-p101", ts, 6.0 + ((c%2)*0.1), "bar", QualityFlag.GOOD))

    h_nom = HealthAssessmentService(repo_healthy).assess("pump-101", "asset-cooling-pump")
    a_nom = AnomalyDetectionService(repo_healthy).detect("pump-101", "asset-cooling-pump")
    d_nom = DiagnosticService().diagnose(h_nom, a_nom)
    print_diagnostic_card(h_nom, a_nom, d_nom)

    # 2. Isolated Sensor Anomaly
    print_banner("2. ISOLATED SENSOR ANOMALY (Blower B-202)")
    repo_single = InMemoryTelemetryRepository()
    for c in range(1, 60):
        ts = base_ts + timedelta(minutes=c)
        temp_val = 85.0 if c > 50 else 40.0
        repo_single.save_observation(Observation(uuid.uuid4().hex, "blower-202", "temp-b202", ts, temp_val, "C", QualityFlag.GOOD))
        repo_single.save_observation(Observation(uuid.uuid4().hex, "blower-202", "vib-b202", ts, 1.0, "mm/s", QualityFlag.GOOD))
        repo_single.save_observation(Observation(uuid.uuid4().hex, "blower-202", "press-b202", ts, 5.0, "bar", QualityFlag.GOOD))

    h_single = HealthAssessmentService(repo_single).assess("blower-202", "asset-blower")
    a_single = AnomalyDetectionService(repo_single).detect("blower-202", "asset-blower")
    d_single = DiagnosticService().diagnose(h_single, a_single)
    print_diagnostic_card(h_single, a_single, d_single)

    # 3. Real NASA C-MAPSS FD001 Turbofan Engine 001 Run-to-Failure Lifecycle
    print_banner("3. NASA C-MAPSS FD001 RUN-TO-FAILURE DIAGNOSIS (Engine-001)")
    adapter = CmapssAdapter()
    envelopes = list(adapter.iter_envelopes(limit_units=[1]))

    # Early Stage (Cycles 1-45)
    repo_early = InMemoryTelemetryRepository()
    for env in envelopes[:45]:
        for p in env.observations:
            repo_early.save_observation(ObservationMapper.to_domain(p, env.source_device_id))
    h_early = HealthAssessmentService(repo_early).assess("engine-001", "turbofan-fleet")
    a_early = AnomalyDetectionService(repo_early).detect("engine-001", "turbofan-fleet")
    d_early = DiagnosticService().diagnose(h_early, a_early)
    print("\n>>> [STAGE 1] Early Operating Phase (Cycles 1-45):")
    print_diagnostic_card(h_early, a_early, d_early)

    # Late Stage (Cycles 1-120 near failure)
    repo_late = InMemoryTelemetryRepository()
    for env in envelopes:
        for p in env.observations:
            repo_late.save_observation(ObservationMapper.to_domain(p, env.source_device_id))
    h_late = HealthAssessmentService(repo_late).assess("engine-001", "turbofan-fleet")
    a_late = AnomalyDetectionService(repo_late).detect("engine-001", "turbofan-fleet")
    d_late = DiagnosticService().diagnose(h_late, a_late)
    print("\n>>> [STAGE 2] Late Degradation Phase Near End-of-Life (Cycle 120):")
    print_diagnostic_card(h_late, a_late, d_late)

    print("\n" + "=" * 80)
    print("  SHOWCASE CONCLUSION: P2.S3 DETERMINISTIC DIAGNOSIS FULLY OPERATIONAL")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    run_showcase()
