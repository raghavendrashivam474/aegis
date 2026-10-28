"""
Aegis Operational Intelligence Dashboard (P4.S2).
Exposes fleet and asset intelligence through persisted snapshots.
Architecture:
    UI -> SnapshotQueryService -> SnapshotRepository -> PostgreSQL
    UI -> EvaluationService (triggers pipeline on demand)
    UI -> TelemetryQueryService -> TelemetryRepository -> PostgreSQL
    No intelligence computation in UI layer. Advisory only.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "packages") not in sys.path:
    sys.path.insert(0, str(ROOT / "packages"))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st

from apps.backend.evaluation_service import IntelligenceEvaluationService
from apps.backend.postgres_adapter import (
    PostgresConnectionPool,
    PostgresDeviceRegistry,
    PostgresSnapshotRepository,
    PostgresTelemetryRepository,
)
from apps.backend.query_service import TelemetryQueryService
from apps.backend.snapshot_query_service import SnapshotQueryService

# -- Connection Helpers ---------------------------------------------------


def _resolve_database_url() -> str:
    try:
        if "AEGIS_DATABASE_URL" in st.secrets:
            return str(st.secrets["AEGIS_DATABASE_URL"])
    except Exception:
        pass
    return os.getenv(
        "AEGIS_DATABASE_URL",
        "postgresql://aegis_admin:aegis_password@localhost:5434/aegis_db",
    )


@st.cache_resource
def _get_pool(db_url: str):
    try:
        return PostgresConnectionPool(db_url, min_size=1, max_size=5)
    except Exception:
        return None


@st.cache_resource
def _get_services(db_url: str):
    pool = _get_pool(db_url)
    if pool is None:
        return None
    try:
        telemetry_repo = PostgresTelemetryRepository(pool=pool)
        snapshot_repo = PostgresSnapshotRepository(pool=pool)
        registry = PostgresDeviceRegistry(pool=pool)
        query_svc = TelemetryQueryService(telemetry_repo)
        snapshot_qry = SnapshotQueryService(snapshot_repo)
        eval_svc = IntelligenceEvaluationService(telemetry_repo, snapshot_repo)
        return {
            "registry": registry,
            "query_svc": query_svc,
            "snapshot_qry": snapshot_qry,
            "eval_svc": eval_svc,
        }
    except Exception:
        return None


# -- Display Helpers ------------------------------------------------------


def _state_icon(state: str) -> str:
    return {
        "NORMAL": "\U0001f7e2",
        "DEGRADING": "\U0001f7e1",
        "CRITICAL": "\U0001f534",
        "UNKNOWN": "\u26aa",
    }.get(state, "\u26aa")


def _priority_icon(priority: str) -> str:
    return {
        "NONE": "\U0001f7e2",
        "LOW": "\U0001f535",
        "MEDIUM": "\U0001f7e1",
        "HIGH": "\U0001f7e0",
        "CRITICAL": "\U0001f534",
    }.get(priority, "\u26aa")


def _status_badge(status: str) -> str:
    badges = {
        "current": "\U0001f7e2 Current",
        "stale": "\U0001f7e1 Stale",
        "no_snapshot": "\u26aa No Data",
        "evaluation_failed": "\U0001f534 Failed",
        "partial_failure": "\U0001f7e0 Partial",
        "insufficient_evidence": "\u26aa Insufficient",
        "query_error": "\U0001f534 DB Error",
    }
    return badges.get(status, f"\u26aa {status}")


def _safe_val(obj, attr: str, fmt: str = "{}") -> str:
    if obj is None:
        return "\u2014"
    try:
        val = getattr(obj, attr)
        if hasattr(val, "value"):
            val = val.value
        return fmt.format(val)
    except Exception:
        return "\u2014"


# -- Sidebar --------------------------------------------------------------

st.set_page_config(page_title="Aegis Intelligence", layout="wide")
db_url = _resolve_database_url()
services = _get_services(db_url)

with st.sidebar:
    st.header("\U0001f6e1\ufe0f Aegis")
    if services:
        st.success("\U0001f7e2 PostgreSQL Connected")
        try:
            devices = services["registry"].list_devices()
            st.caption(f"{len(devices)} registered devices")
        except Exception:
            devices = []
            st.warning("Device registry unavailable")
    else:
        st.error("\U0001f534 PostgreSQL Disconnected")
        st.caption(
            "Start infrastructure:\n"
            "1. docker compose up -d\n"
            "2. python -m apps.backend.seed_devices\n"
            "3. Ingest telemetry data"
        )
        devices = []
    st.divider()
    auto_refresh = st.toggle("\u26a1 Auto-Refresh", value=False)
    if auto_refresh:
        poll_rate = st.slider("Interval (sec)", 5, 60, 15, 5)
    st.divider()
    st.caption("Advisory only. No autonomous actuation.")

# -- Main Content ---------------------------------------------------------

st.title("\U0001f6e1\ufe0f Aegis Operational Intelligence")
st.caption(
    "Intelligence from persisted evaluation snapshots. "
    "Pipeline: Health \u2192 Anomaly \u2192 Diagnostic \u2192 Risk."
)

if not devices:
    st.info(
        "No registered devices found. To populate the dashboard:\n\n"
        "1. Start infrastructure: docker compose up -d\n"
        "2. Seed device registry: python -m apps.backend.seed_devices\n"
        "3. Ingest telemetry: python -m apps.ingestion or run a simulator"
    )
    st.stop()

# -- Evaluate + Query Snapshots -------------------------------------------

device_ids = [dev.device_id for dev in devices]
device_asset_map = {dev.device_id: dev.asset_id for dev in devices}

with st.spinner("Loading fleet intelligence\u2026"):
    # Query existing snapshots
    snap_results = services["snapshot_qry"].get_fleet_snapshots(device_ids)

    # Evaluate devices that have no snapshot or stale snapshot
    devices_needing_eval = []
    for did in device_ids:
        qr = snap_results[did]
        if not qr.has_data or qr.status in ("stale", "no_snapshot", "evaluation_failed"):
            devices_needing_eval.append((did, device_asset_map[did]))

    if devices_needing_eval:
        eval_results = services["eval_svc"].evaluate_fleet(devices_needing_eval)
        # Re-query to get the fresh snapshots
        snap_results = services["snapshot_qry"].get_fleet_snapshots(device_ids)

# Build intelligence map from snapshots
intel_map = {}
for did in device_ids:
    qr = snap_results[did]
    if qr.has_data and qr.snapshot:
        snap = qr.snapshot
        intel_map[did] = {
            "health": snap.health,
            "anomaly": snap.anomaly,
            "diagnostic": snap.diagnostic,
            "finding": snap.finding,
            "errors": list(snap.errors),
            "status": qr.status,
            "freshness": qr.freshness,
            "evaluated_at": snap.evaluated_at,
        }
    else:
        intel_map[did] = {
            "health": None,
            "anomaly": None,
            "diagnostic": None,
            "finding": None,
            "errors": [],
            "status": qr.status,
            "freshness": None,
            "evaluated_at": None,
        }

# -- Tabs -----------------------------------------------------------------

tab_overview, tab_detail, tab_telemetry = st.tabs(
    ["\U0001f4ca Fleet Overview", "\U0001f50d Asset Intelligence", "\U0001f4dc Telemetry History"],
)

# -- Tab 1: Fleet Overview ------------------------------------------------

with tab_overview:
    st.subheader("Fleet Condition Summary")
    counts = {"NORMAL": 0, "DEGRADING": 0, "CRITICAL": 0, "UNKNOWN": 0}
    for intel in intel_map.values():
        h = intel.get("health")
        state = h.operational_state.value if h else "UNKNOWN"
        counts[state] = counts.get(state, 0) + 1
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("\U0001f7e2 Normal", counts["NORMAL"])
    c2.metric("\U0001f7e1 Degrading", counts["DEGRADING"])
    c3.metric("\U0001f534 Critical", counts["CRITICAL"])
    c4.metric("\u26aa Unknown", counts["UNKNOWN"])
    st.divider()
    st.subheader("Asset Intelligence Overview")
    rows = []
    for dev_id, intel in intel_map.items():
        h = intel.get("health")
        a = intel.get("anomaly")
        d = intel.get("diagnostic")
        f = intel.get("finding")
        errs = intel.get("errors", [])
        snap_status = intel.get("status", "unknown")
        rows.append(
            {
                "Device": dev_id,
                "Snapshot": _status_badge(snap_status),
                "State": f"{_state_icon(_safe_val(h, 'operational_state'))} {_safe_val(h, 'operational_state')}",
                "Health": _safe_val(h, "health_score", "{:.1f}/100"),
                "Anomaly": _safe_val(a, "status"),
                "Severity": _safe_val(a, "severity"),
                "Diagnostic": _safe_val(d, "status"),
                "Priority": f"{_priority_icon(_safe_val(f, 'priority'))} {_safe_val(f, 'priority')}",
                "Issues": "; ".join(errs) if errs else "\u2705",
            }
        )
    st.dataframe(rows, use_container_width=True, hide_index=True)

# -- Tab 2: Asset Intelligence Detail -------------------------------------

with tab_detail:
    st.subheader("Asset Intelligence Detail")
    selected = st.selectbox("Select Asset", device_ids)
    if selected and selected in intel_map:
        intel = intel_map[selected]
        h = intel.get("health")
        a = intel.get("anomaly")
        d = intel.get("diagnostic")
        f = intel.get("finding")
        errs = intel.get("errors", [])
        snap_status = intel.get("status", "unknown")
        freshness = intel.get("freshness")
        eval_at = intel.get("evaluated_at")

        # Status banner
        badge = _status_badge(snap_status)
        if snap_status == "current":
            st.success(f"{badge} | {freshness.reason if freshness else ''}")
        elif snap_status == "stale":
            st.warning(f"{badge} | {freshness.reason if freshness else ''}")
        elif snap_status in ("evaluation_failed", "query_error"):
            st.error(f"{badge}")
        else:
            st.info(f"{badge}")

        if errs:
            st.warning(f"\u26a0\ufe0f Pipeline issues: {'; '.join(errs)}")

        # Health
        st.markdown("#### \U0001fa7a Health Assessment")
        if h:
            hc = st.columns(4)
            state_label = f"{_state_icon(h.operational_state.value)} {h.operational_state.value}"
            hc[0].metric("State", state_label)
            hc[1].metric("Health Score", f"{h.health_score:.1f}/100")
            hc[2].metric("Confidence", f"{h.confidence:.0%}")
            hc[3].metric("Trend", h.trend.value)
            st.caption(f"Evaluated: {h.evaluated_at.isoformat()} | {h.evidence_summary}")
            if h.sensor_signals:
                with st.expander("Sensor Signal Evidence"):
                    for sig in h.sensor_signals:
                        flag = "\u26a0\ufe0f" if sig.insufficient_data else "\u2705"
                        st.markdown(
                            f"{flag} **{sig.sensor_id}**: "
                            f"baseline={sig.baseline_mean:.2f}\u00b1{sig.baseline_std:.2f}, "
                            f"current={sig.current_mean:.2f}, "
                            f"deviation={sig.deviation_score:.2f}\u03c3, "
                            f"trend={sig.trend.value}, "
                            f"quality={sig.data_quality:.0%} "
                            f"(n={sig.sample_count})"
                        )
        else:
            st.info("Health assessment unavailable.")
        st.divider()

        # Anomaly
        st.markdown("#### \U0001f514 Anomaly & Degradation Detection")
        if a:
            ac = st.columns(4)
            ac[0].metric("Status", a.status.value)
            ac[1].metric("Anomaly Score", f"{a.anomaly_score:.2f}")
            ac[2].metric("Severity", a.severity.value)
            ac[3].metric("Confidence", f"{a.confidence:.0%}")
            st.caption(f"Method: {a.detection_method} | {a.evaluated_at.isoformat()}")
            if a.evidence_list:
                with st.expander("Detection Evidence"):
                    for ev in a.evidence_list:
                        st.markdown(
                            f"- **{ev.sensor_id}**: {ev.deviation_sigma:.2f}\u03c3, "
                            f"persistence={ev.persistence_count}, "
                            f"contribution={ev.contribution_score:.2f} \u2014 {ev.reason}"
                        )
        else:
            st.info("Anomaly detection unavailable.")
        st.divider()

        # Diagnostic
        st.markdown("#### \U0001f52c Diagnostic Hypotheses")
        if d:
            dc = st.columns(3)
            dc[0].metric("Status", d.status.value)
            dc[1].metric("Overall Risk", d.overall_risk.value)
            dc[2].metric("Confidence", f"{d.confidence:.0%}")
            st.markdown(f"**Primary Finding:** {d.primary_finding}")
            st.caption(f"Limitations: {d.limitations}")
            if d.hypotheses:
                with st.expander("Hypotheses (advisory)"):
                    for hyp in d.hypotheses:
                        st.markdown(
                            f"- **{hyp.category.value}** "
                            f"(confidence: {hyp.confidence:.0%}, "
                            f"severity: {hyp.severity.value}): "
                            f"{hyp.description}"
                        )
        else:
            st.info("Diagnostic analysis unavailable.")
        st.divider()

        # Risk
        st.markdown("#### \u26a1 Operational Risk & Advisory")
        if f:
            fc = st.columns(3)
            fc[0].metric("Priority", f"{_priority_icon(f.priority.value)} {f.priority.value}")
            fc[1].metric("Risk Level", f.risk_level.value)
            fc[2].metric("Confidence", f"{f.confidence:.0%}")
            st.markdown(f"**Summary:** {f.summary}")
            st.markdown(f"**Recommended Action:** {f.recommended_next_action}")
            if f.lead_cycles_estimate is not None:
                st.caption(f"Lead cycles estimate: {f.lead_cycles_estimate}")
            st.caption(f"Limitations: {f.limitations}")
            if f.supporting_evidence:
                with st.expander("Evidence Chain"):
                    for ev in f.supporting_evidence:
                        st.markdown(f"- {ev}")
        else:
            st.info("Risk assessment unavailable.")

# -- Tab 3: Telemetry History (unchanged from P4.S1) ----------------------

with tab_telemetry:
    st.subheader("Telemetry History")
    qs = services.get("query_svc") if services else None
    if qs:
        sel_dev = st.selectbox("Device", device_ids, key="telem_dev")
        if sel_dev:
            try:
                obs = qs.get_device_history(device_id=sel_dev, limit=200)
                if obs:
                    import pandas as pd

                    records = [
                        {
                            "timestamp": o.timestamp,
                            "sensor_id": o.sensor_id,
                            "value": o.value,
                            "unit": o.unit,
                            "quality": (
                                o.quality.value if hasattr(o.quality, "value") else str(o.quality)
                            ),
                        }
                        for o in obs
                    ]
                    df = pd.DataFrame(records)
                    df["timestamp"] = pd.to_datetime(df["timestamp"])
                    df = df.sort_values("timestamp")
                    st.line_chart(
                        df,
                        x="timestamp",
                        y="value",
                        color="sensor_id",
                        height=400,
                    )
                    with st.expander("Raw Observations"):
                        st.dataframe(
                            df.tail(50),
                            use_container_width=True,
                            hide_index=True,
                        )
                else:
                    st.info(f"No telemetry observations for {sel_dev}.")
            except Exception as exc:
                st.error(f"Failed to load telemetry: {exc}")
    else:
        st.info("Database connection required for telemetry history.")

# -- Auto-refresh ---------------------------------------------------------

if auto_refresh:
    import time

    time.sleep(poll_rate)
    st.rerun()
