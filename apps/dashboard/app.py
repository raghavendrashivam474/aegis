# ruff: noqa: E501
# ruff: noqa: E402
"""
Aegis Telemetry Dashboard (Contract & Database Consumer).

Displays live streaming telemetry, and allows viewing historical data directly
from PostgreSQL or the legacy JSONL local ledger stream.
"""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "packages") not in sys.path:
    sys.path.insert(0, str(ROOT / "packages"))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd
import streamlit as st
from contracts import TelemetryEnvelope

from apps.backend.postgres_adapter import PostgresDeviceRegistry
from apps.backend.query_service import TelemetryQueryService

STREAM_FILE = Path("data/telemetry_stream.jsonl")


def _resolve_database_url() -> str:
    """Resolve database URL from st.secrets, environment, or default fallback."""
    try:
        if "AEGIS_DATABASE_URL" in st.secrets:
            return str(st.secrets["AEGIS_DATABASE_URL"])
    except Exception:
        pass
    return os.getenv(
        "AEGIS_DATABASE_URL",
        "postgresql://aegis_admin:aegis_password@localhost:5434/aegis_db",
    )


DEFAULT_DB_URL = _resolve_database_url()

st.set_page_config(
    page_title="Aegis - Telemetry Dashboard",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)


def _load_legacy_telemetry_stream() -> list[dict]:
    """Read and deserialize legacy JSONL stream envelopes."""
    if not STREAM_FILE.exists():
        return []

    records: list[dict] = []
    try:
        with STREAM_FILE.open("r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                data = json.loads(line)
                envelope = TelemetryEnvelope.from_dict(data)
                source_type = envelope.metadata.get("source", "simulator")
                transport_type = envelope.metadata.get("transport", "ipc_file")

                try:
                    ts_dt = datetime.fromisoformat(envelope.sent_at_iso)
                except Exception:
                    ts_dt = datetime.now()

                for obs in envelope.observations:
                    records.append(
                        {
                            "timestamp": ts_dt,
                            "sent_at_iso": envelope.sent_at_iso,
                            "device_id": envelope.source_device_id,
                            "sensor_id": obs.sensor_id,
                            "value": obs.value,
                            "unit": obs.unit,
                            "quality": obs.quality,
                            "schema_version": envelope.schema_version,
                            "source": source_type,
                            "transport": transport_type,
                        }
                    )
    except (json.JSONDecodeError, OSError):
        pass

    return records


def _load_postgres_history(
    query_service: TelemetryQueryService,
    registry: PostgresDeviceRegistry,
    limit: int = 500,
) -> list[dict]:
    """Fetch structured history from PostgreSQL using application query boundaries."""
    records: list[dict] = []
    try:
        devices = registry.list_devices()
        for dev in devices:
            obs_list = query_service.get_device_history(device_id=dev.device_id, limit=limit)
            for obs in obs_list:
                source_type = "physical" if "esp32" in dev.device_id else "simulator"
                transport_type = "mqtt"

                records.append(
                    {
                        "timestamp": obs.timestamp,
                        "sent_at_iso": obs.timestamp.isoformat(),
                        "device_id": obs.device_id,
                        "sensor_id": obs.sensor_id,
                        "value": obs.value,
                        "unit": obs.unit,
                        "quality": obs.quality.value,
                        "schema_version": "v1",
                        "source": source_type,
                        "transport": transport_type,
                    }
                )
    except Exception as err:
        st.sidebar.error(f"PostgreSQL Connection Error: {err}")
    return records


# Sidebar Setup
with st.sidebar:
    st.title("🛡️ Aegis Dashboard")
    st.markdown("**Operational World Telemetry**")
    st.divider()

    data_source = st.radio(
        "Data Source Ingestion Path",
        ["PostgreSQL Database", "Legacy JSONL Stream"],
        index=0,
    )

    auto_refresh = st.toggle("⚡ Live Polling", value=True)
    poll_rate = st.slider("Refresh Speed (sec)", 0.2, 2.0, 0.5, 0.1)

    if st.button("🗑️ Clear Local JSONL Ledger"):
        if STREAM_FILE.exists():
            STREAM_FILE.write_text("", encoding="utf-8")
            st.rerun()

    st.divider()
    st.markdown("### 📋 Connection Status")

    qs = None
    registry = None
    db_connected = False
    try:
        qs = TelemetryQueryService.create_default(DEFAULT_DB_URL)
        registry = PostgresDeviceRegistry(DEFAULT_DB_URL)
        with qs.repository._get_conn() as conn:
            pass
        db_connected = True
        st.success("🟢 PostgreSQL Connected")
    except Exception:
        st.error("🔴 PostgreSQL Disconnected")

    if STREAM_FILE.exists():
        st.success("🟢 Stream File Connected")
    else:
        st.warning("⚠️ Stream File Missing")

st.title("⚡ Aegis Unified Operational World Telemetry")
st.caption(
    "Consuming live & historical telemetry through transport, validation, and storage boundaries."
)

if data_source == "PostgreSQL Database" and db_connected and qs and registry:
    records = _load_postgres_history(qs, registry)
else:
    records = _load_legacy_telemetry_stream()

if records:
    df = pd.DataFrame(records)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df.sort_values("timestamp")
    df = df.tail(400)

    sources = df["source"].unique()
    devices = df["device_id"].unique()
    device_summary = ", ".join(str(d) for d in devices)
    source_summary = ", ".join(str(s) for s in sources)
    st.caption(
        f"**Active Registered Devices ({len(devices)}):** {device_summary} | **Origins:** {source_summary}"
    )

    latest_df = df.groupby("sensor_id").last().reset_index()
    cols = st.columns(min(len(latest_df), 6))

    for idx, row in latest_df.iterrows():
        col_target = cols[idx % len(cols)]
        with col_target:
            val_str = f"{row['value']} {row['unit']}"
            is_warn = ("temp" in row["sensor_id"] and row["value"] > 75.0) or (
                "vibration" in row["sensor_id"] and row["value"] > 2.5
            )
            delta_color = "inverse" if is_warn else "normal"
            src_tag = f"[{row['source']}]"
            st.metric(
                label=f"{row['device_id']} · {row['sensor_id']} {src_tag}",
                value=val_str,
                delta="⚠️ High" if is_warn else "GOOD",
                delta_color=delta_color,
            )

    st.divider()

    tab_temp, tab_vib, tab_press, tab_hum, tab_raw = st.tabs(
        [
            "🌡️ Temperature",
            "〰️ Vibration",
            "🎚️ Pressure",
            "💧 Humidity",
            "📜 Raw Observations Ledger",
        ]
    )

    def _render_chart(sub_df: pd.DataFrame, title: str) -> None:
        if sub_df.empty:
            st.info(f"No {title.lower()} observations registered currently.")
            return
        st.line_chart(
            sub_df,
            x="timestamp",
            y="value",
            color="sensor_id",
            height=350,
        )

    with tab_temp:
        _render_chart(df[df["sensor_id"].str.contains("temp")], "Temperature")

    with tab_vib:
        _render_chart(df[df["sensor_id"].str.contains("vibration")], "Vibration")

    with tab_press:
        _render_chart(df[df["sensor_id"].str.contains("pressure")], "Pressure")

    with tab_hum:
        _render_chart(df[df["sensor_id"].str.contains("humidity|hum", regex=True)], "Humidity")

    with tab_raw:
        st.dataframe(df.tail(50))

else:
    st.info(
        "Waiting for telemetry observations... Ensure PostgreSQL Docker containers are online and run a producer:\n\n"
        "1. Start Infrastructure: docker compose up -d\n"
        "2. Seed Identity Registry: python -m apps.backend.seed_devices\n"
        "3. Ingest: python -m apps.ingestion\n"
        "4. Stream: python -m apps.simulator --mqtt --live or Mock ESP32 node"
    )

if auto_refresh:
    time.sleep(poll_rate)
    st.rerun()
