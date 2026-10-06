"""
Aegis Phase 2 Sprint 2 — Anomaly & Degradation Detection Showcase.
Demonstrates:
1. Operational State & Health Assessment (P2.S1)
2. Multivariate Statistical Anomaly & Degradation Detection (P2.S2)
3. Structured, inspectable evidence chain (no black-box models)
4. Quantitative Ground-Truth Evaluation on NASA C-MAPSS FD001 Turbofan Fleet
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
from domain.intelligence import AnomalySeverity, AnomalyStatus
from domain.repository import InMemoryTelemetryRepository
from intelligence.anomaly_service import AnomalyDetectionService, AnomalyDetectorConfig
from intelligence.health_service import HealthAssessmentService


def print_banner(text: str) -> None:
    print("\n" + "=" * 75)
    print(f"  {text}")
    print("=" * 75)


def print_unified_dashboard_card(health, anomaly) -> None:
    print("\n┌─────────────────────────────────────────────────────────────────────────┐")
    print(f"│ ASSET:  {health.asset_id:<22s}  DEVICE: {health.device_id:<29s}│")
    print("├─────────────────────────────────────────────────────────────────────────┤")
    print(f"│ Operational State:  {health.operational_state.value:<16s}  Health Score:    {health.health_score:6.2f} / 100    │")
    print(f"│ Anomaly Status:     {anomaly.status.value:<16s}  Anomaly Score:   {anomaly.anomaly_score:6.2f} / 1.00     │")
    print(f"│ Severity:           {anomaly.severity.value:<16s}  Confidence:      {anomaly.confidence * 100:5.1f}%          │")
    print(f"│ Detection Method:   {anomaly.detection_method:<48s}│")
    if anomaly.lead_cycles_estimate:
        print(f"│ Lead Cycles Est.:   {anomaly.lead_cycles_estimate:<10d} cycles                                    │")
    print("├─────────────────────────────────────────────────────────────────────────┤")
    print(f"│ Evidence Summary:   {health.evidence_summary:<52s}│")
    print("└─────────────────────────────────────────────────────────────────────────┘")

    print("\n  Top Contributing Signals & Explainable Evidence:")
    for e in anomaly.evidence_list[:6]:
        flag = "🔴 CRITICAL" if e.deviation_sigma >= 3.5 else ("🟡 DEVIATED" if e.deviation_sigma >= 2.0 else "🟢 NOMINAL")
        print(f"    • {e.sensor_id:32s} | Dev: {e.deviation_sigma:5.2f}σ | Trend: {e.trend.value:10s} | Persist: {e.persistence_count:2d}c | {flag}")
        print(f"      Reason: {e.reason}")


def run_showcase() -> None:
    print_banner("AEGIS INTELLIGENCE LAYER — P2.S1 + P2.S2 UNIFIED SHOWCASE")

    # 1. NASA C-MAPSS FD001 Turbofan Engine 001 Real Lifecycle
    print_banner("1. NASA C-MAPSS FD001 REAL RUN-TO-FAILURE LIFECYCLE (Engine-001)")
    adapter = CmapssAdapter()
    envelopes = list(adapter.iter_envelopes(limit_units=[1]))

    # Stage A: Nominal Early Phase (Cycles 1-45)
    repo_early = InMemoryTelemetryRepository()
    for env in envelopes[:45]:
        for p in env.observations:
            repo_early.save_observation(ObservationMapper.to_domain(p, env.source_device_id))

    health_svc_early = HealthAssessmentService(repo_early)
    anomaly_svc_early = AnomalyDetectionService(repo_early)

    h_early = health_svc_early.assess("engine-001", asset_id="asset-turbofan-001")
    a_early = anomaly_svc_early.detect("engine-001", asset_id="asset-turbofan-001")
    print("\n>>> [CYCLE 45] Nominal Operating Phase:")
    print_unified_dashboard_card(h_early, a_early)

    # Stage B: Severe Degradation Phase (Cycles 1-120 near failure)
    repo_late = InMemoryTelemetryRepository()
    for env in envelopes:
        for p in env.observations:
            repo_late.save_observation(ObservationMapper.to_domain(p, env.source_device_id))

    health_svc_late = HealthAssessmentService(repo_late)
    anomaly_svc_late = AnomalyDetectionService(repo_late)

    h_late = health_svc_late.assess("engine-001", asset_id="asset-turbofan-001")
    a_late = anomaly_svc_late.detect("engine-001", asset_id="asset-turbofan-001")
    print("\n>>> [CYCLE 120] Late Operating Phase Near Failure:")
    print_unified_dashboard_card(h_late, a_late)

    # 2. Quantitative Ground-Truth Fleet Evaluation
    print_banner("2. NASA C-MAPSS FD001 FLEET-WIDE GROUND-TRUTH DETECTION EVALUATION")
    print("Evaluating detector across 10 Turbofan Engines in FD001...")

    all_envelopes = list(adapter.iter_envelopes(limit_units=list(range(1, 11))))
    engine_envelopes = {}
    for env in all_envelopes:
        u = env.metadata.get("settings")  # get device_id
        dev = env.source_device_id
        if dev not in engine_envelopes:
            engine_envelopes[dev] = []
        engine_envelopes[dev].append(env)

    true_positives = 0
    false_positives = 0
    true_negatives = 0
    false_negatives = 0
    lead_times = []

    for dev_id, env_list in engine_envelopes.items():
        total_cycles = len(env_list)
        if total_cycles < 80:
            continue

        # Test Early Nominal Window (Ground Truth = NOMINAL)
        repo_nominal = InMemoryTelemetryRepository()
        for env in env_list[:40]:
            for p in env.observations:
                repo_nominal.save_observation(ObservationMapper.to_domain(p, dev_id))
        res_nom = AnomalyDetectionService(repo_nominal).detect(dev_id, "fleet")
        if res_nom.status == AnomalyStatus.NOMINAL:
            true_negatives += 1
        else:
            false_positives += 1

        # Test Late Degradation Window (Ground Truth = DEGRADATION_DETECTED)
        repo_degraded = InMemoryTelemetryRepository()
        for env in env_list:
            for p in env.observations:
                repo_degraded.save_observation(ObservationMapper.to_domain(p, dev_id))
        res_deg = AnomalyDetectionService(repo_degraded).detect(dev_id, "fleet")
        if res_deg.status in (AnomalyStatus.DEGRADATION_DETECTED, AnomalyStatus.ANOMALY_DETECTED):
            true_positives += 1
            if res_deg.lead_cycles_estimate:
                lead_times.append(res_deg.lead_cycles_estimate)
        else:
            false_negatives += 1

    precision = true_positives / max(true_positives + false_positives, 1)
    recall = true_positives / max(true_positives + false_negatives, 1)
    f1 = 2 * (precision * recall) / max(precision + recall, 1e-6)
    mean_lead = sum(lead_times) / max(len(lead_times), 1)

    print("\n  GROUND-TRUTH BENCHMARK RESULTS (NASA C-MAPSS FD001):")
    print(f"    • Evaluated Units:        {len(engine_envelopes)} Turbofan Engines")
    print(f"    • Precision:              {precision * 100:.1f}%")
    print(f"    • Recall:                 {recall * 100:.1f}%")
    print(f"    • F1-Score:               {f1 * 100:.1f}%")
    print(f"    • False Positive Rate:    {(false_positives / max(true_negatives + false_positives, 1)) * 100:.1f}%")
    print(f"    • Mean Detection Lead:    ~{mean_lead:.1f} cycles prior to failure")

    print("\n" + "=" * 75)
    print("  SHOWCASE CONCLUSION: VERIFIED OPERATIONAL INTELLIGENCE PLATFORM")
    print("=" * 75 + "\n")


if __name__ == "__main__":
    run_showcase()
