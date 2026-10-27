"""
Aegis Operational Intelligence Dashboard (P4.S1).
Exposes the full intelligence pipeline (Health, Anomaly, Diagnostic, Risk)
through an operator-facing Streamlit interface.

Architecture:
    UI -> TelemetryQueryService -> TelemetryRepository -> PostgreSQL
    UI -> Intelligence Services (pure computation over repository)
    No domain logic in UI. No hardcoded thresholds. No fabricated data.
    Advisory only â€” no autonomous actuation.
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
from intelligence.anomaly_service import AnomalyDetectionService
from intelligence.diagnostic_service import DiagnosticService
from intelligence.health_service import HealthAssessmentService
from intelligence.risk_service import OperationalRiskService

from apps.backend.postgres_adapter import PostgresDeviceRegistry
from apps.backend.query_service import TelemetryQueryService

# â”€â”€ Connection Helpers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


def _resolve_database_url() -> str:
    """Resolve database URL from st.secrets, environment, or default."""
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
def _get_query_service(db_url: str) -> TelemetryQueryService | None:
    try:
        return TelemetryQueryService.create_default(db_url)
    except Exception:
        return None


@st.cache_resource
def _get_registry(db_url: str) -> PostgresDeviceRegistry | None:
    try:
        return PostgresDeviceRegistry(db_url)
    except Exception:
        return None


# â”€â”€ Intelligence Pipeline â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


@st.cache_data(ttl=30)
def _compute_asset_intelligence(device_id: str, db_url: str) -> dict:
    """Run the full intelligence pipeline for a single asset.

    Each stage is independent: a failure in one does not prevent
    the others from being attempted where possible.
    """
    result: dict = {
        "device_id": device_id,
        "health": None,
        "anomaly": None,
        "diagnostic": None,
        "finding": None,
        "errors": [],
    }
    try:
        qs = TelemetryQueryService.create_default(db_url)
        repo = qs.repository
    except Exception as exc:
        result["errors"].append(f"Repository unavailable: {exc}")
        return result

    asset_id = device_id

    # P2.S1 â€” Health Assessment
    try:
        result["health"] = HealthAssessmentService(repo).assess(device_id, asset_id)
    except Exception as exc:
        result["errors"].append(f"Health: {exc}")

    # P2.S2 â€” Anomaly & Degradation Detection
    try:
        result["anomaly"] = AnomalyDetectionService(repo).detect(device_id, asset_id)
    except Exception as exc:
        result["errors"].append(f"Anomaly: {exc}")

    # P2.S3 â€” Diagnostic (requires health + anomaly)
    if result["health"] and result["anomaly"]:
        try:
            result["diagnostic"] = DiagnosticService().diagnose(
                result["health"],
                result["anomaly"],
            )
        except Exception as exc:
            result["errors"].append(f"Diagnostic: {exc}")

    # P2.S4 â€” Risk Prioritization (requires all upstream)
    if result["health"] and result["anomaly"] and result["diagnostic"]:
        try:
            result["finding"] = OperationalRiskService().evaluate(
                result["health"],
                result["anomaly"],
                result["diagnostic"],
            )
        except Exception as exc:
            result["errors"].append(f"Risk: {exc}")

    return result


# â”€â”€ Display Helpers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


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


def _safe_val(obj, attr: str, fmt: str = "{}") -> str:
    """Safely extract a nested attribute value for display."""
    if obj is None:
        return "\u2014"
    try:
        val = getattr(obj, attr)
        if hasattr(val, "value"):
            val = val.value
        return fmt.format(val)
    except Exception:
        return "\u2014"


# â”€â”€ Page Configuration â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

st.set_page_config(
    page_title="Aegis \u2014 Operational Intelligence",
    page_icon="\U0001f6e1\ufe0f",
    layout="wide",
    initial_sidebar_state="expanded",
)

# â”€â”€ Sidebar â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

db_url = _resolve_database_url()
qs = _get_query_service(db_url)
registry = _get_registry(db_url)

with st.sidebar:
    st.title("\U0001f6e1\ufe0f Aegis")
    st.markdown("**Operational Intelligence**")
    st.divider()

    st.markdown("### Connection Status")
    devices: list = []
    if qs and registry:
        try:
            devices = registry.list_devices()
            st.success(f"\U0001f7e3 PostgreSQL ({len(devices)} devices)")
        except Exception:
            st.error("\U0001f534 PostgreSQL query failed")
    else:
        st.error("\U0001f534 PostgreSQL Disconnected")
        st.caption(
            "Start infrastructure:\n"
            "1. `docker compose up -d`\n"
            "2. `python -m apps.backend.seed_devices`\n"
            "3. Ingest telemetry data"
        )

    st.divider()
    auto_refresh = st.toggle("\u26a1 Auto-Refresh", value=False)
    if auto_refresh:
        poll_rate = st.slider("Interval (sec)", 5, 60, 15, 5)

    st.divider()
    st.caption("Advisory only. No autonomous actuation.")

# â”€â”€ Main Content â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

st.title("\U0001f6e1\ufe0f Aegis Operational Intelligence")
st.caption(
    "Intelligence pipeline: Health \u2192 Anomaly \u2192 Diagnostic \u2192 Risk. "
    "All values derived from existing services, not hardcoded thresholds."
)

if not devices:
    st.info(
        "No registered devices found. To populate the dashboard:\n\n"
        "1. Start infrastructure: `docker compose up -d`\n"
        "2. Seed device registry: `python -m apps.backend.seed_devices`\n"
        "3. Ingest telemetry: `python -m apps.ingestion` or run a simulator\n\n"
        "The dashboard will display intelligence once telemetry data is available."
    )
    st.stop()

# Compute intelligence for all registered devices
with st.spinner("Computing fleet intelligence\u2026"):
    intel_map = {
        dev.device_id: _compute_asset_intelligence(dev.device_id, db_url) for dev in devices
    }

# â”€â”€ Tabs â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

tab_overview, tab_detail, tab_telemetry = st.tabs(
    ["\U0001f4ca Fleet Overview", "\U0001f50d Asset Intelligence", "\U0001f4dc Telemetry History"],
)

# â”€â”€ Tab 1: Fleet Overview â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

with tab_overview:
    st.subheader("Fleet Condition Summary")

    counts = {"NORMAL": 0, "DEGRADING": 0, "CRITICAL": 0, "UNKNOWN": 0}
    for intel in intel_map.values():
        h = intel.get("health")
        if h:
            state = h.operational_state.value
        else:
            state = "UNKNOWN"
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

        rows.append(
            {
                "Device": dev_id,
                "State": (
                    f"{_state_icon(_safe_val(h, 'operational_state'))} "
                    f"{_safe_val(h, 'operational_state')}"
                ),
                "Health": _safe_val(h, "health_score", "{:.1f}/100"),
                "Anomaly": _safe_val(a, "status"),
                "Severity": _safe_val(a, "severity"),
                "Diagnostic": _safe_val(d, "status"),
                "Priority": (
                    f"{_priority_icon(_safe_val(f, 'priority'))} {_safe_val(f, 'priority')}"
                ),
                "Issues": "; ".join(errs) if errs else "\u2705",
            },
        )

    st.dataframe(rows, use_container_width=True, hide_index=True)

# â”€â”€ Tab 2: Asset Intelligence Detail â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

with tab_detail:
    st.subheader("Asset Intelligence Detail")
    device_ids = [dev.device_id for dev in devices]
    selected = st.selectbox("Select Asset", device_ids)

    if selected and selected in intel_map:
        intel = intel_map[selected]
        h = intel.get("health")
        a = intel.get("anomaly")
        d = intel.get("diagnostic")
        f = intel.get("finding")
        errs = intel.get("errors", [])

        if errs:
            st.warning(f"\u26a0\ufe0f Pipeline issues: {'; '.join(errs)}")

        # â”€â”€ Health â”€â”€
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
            st.info("Health assessment unavailable. Insufficient telemetry data.")

        st.divider()

        # â”€â”€ Anomaly â”€â”€
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
                            f"persistence={ev.persistence_count} cycles, "
                            f"contribution={ev.contribution_score:.2f} \u2014 {ev.reason}"
                        )
        else:
            st.info("Anomaly detection unavailable.")

        st.divider()

        # â”€â”€ Diagnostic â”€â”€
        st.markdown("#### \U0001f52c Diagnostic Hypotheses")
        if d:
            dc = st.columns(3)
            dc[0].metric("Status", d.status.value)
            dc[1].metric("Overall Risk", d.overall_risk.value)
            dc[2].metric("Confidence", f"{d.confidence:.0%}")
            st.markdown(f"**Primary Finding:** {d.primary_finding}")
            st.caption(f"Limitations: {d.limitations}")

            if d.hypotheses:
                with st.expander("Hypotheses (advisory \u2014 not confirmed root causes)"):
                    for hyp in d.hypotheses:
                        st.markdown(
                            f"- **{hyp.category.value}** "
                            f"(confidence: {hyp.confidence:.0%}, "
                            f"severity: {hyp.severity.value}): "
                            f"{hyp.description}"
                        )
                        for se in hyp.supporting_evidence:
                            st.caption(f"  \u21b3 {se}")
        else:
            st.info("Diagnostic analysis unavailable. Requires health + anomaly results.")

        st.divider()

        # â”€â”€ Risk â”€â”€
        st.markdown("#### \u26a1 Operational Risk & Advisory")
        if f:
            fc = st.columns(3)
            fc[0].metric(
                "Priority",
                f"{_priority_icon(f.priority.value)} {f.priority.value}",
            )
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
            st.info("Risk assessment unavailable. Requires complete pipeline.")

# â”€â”€ Tab 3: Telemetry History â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

with tab_telemetry:
    st.subheader("Telemetry History")
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

# â”€â”€ Auto-refresh â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

if auto_refresh:
    import time

    time.sleep(poll_rate)
    st.rerun()
