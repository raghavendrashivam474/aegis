# ruff: noqa: E501
# ruff: noqa: E402
"""
Aegis Telemetry Dashboard (Contract & Database Consumer).

Displays live streaming telemetry, and allows viewing historical data directly
from PostgreSQL or the legacy JSONL local ledger stream.
"""

from __future__ import annotations

import json
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

from apps.backend.query_service import TelemetryQueryService

STREAM_FILE = Path("data/telemetry_stream.jsonl")

st.set_page_config(
    page_title="Aegis — Telemetry Dashboard",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)


def _format_time_label(iso_str: str) -> str:
    """Format ISO timestamp to HH:MM:SS.s for graph rendering."""
    try:
        # If datetime object is passed directly
        if isinstance(iso_str, datetime):
            return iso_str.strftime("%H:%M:%S.%f")[:-5]

        time_part = iso_str.split("T")[1].split("+")[0].split("Z")[0]
        if "." in time_part:
            hhmmss, ms = time_part.split(".")
            return f"{hhmmss}.{ms[:1]}"
        return f"{time_part}.0"
    except Exception:
        return str(iso_str)


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
                time_label = _format_time_label(envelope.sent_at_iso)
                source_type = envelope.metadata.get("source", "simulator")
                transport_type = envelope.metadata.get("transport", "ipc_file")

                for obs in envelope.observations:
                    records.append(
                        {
                            "time_label": time_label,
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


def _load_postgres_history(query_service: TelemetryQueryService, limit: int = 500) -> list[dict]:
    """Fetch structured history from PostgreSQL using the abstract repository port."""
    records: list[dict] = []
    try:
        # Fetch observations from all active simulator/esp32 devices
        for dev_id in ["device-motor-01", "device-motor-02", "device-esp32-01", "device-esp32-99"]:
            obs_list = query_service.get_device_history(device_id=dev_id, limit=limit)
            for obs in obs_list:
                time_label = _format_time_label(obs.timestamp)
                source_type = "physical" if "esp32" in dev_id else "simulator"
                transport_type = "mqtt" if "esp32" in dev_id else "ipc_file"

                records.append(
                    {
                        "time_label": time_label,
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
    st.markdown("**Sprint P1.S5 — Telemetry & Identity**")
    st.divider()

    # Toggle selection between Legacy Stream (JSONL) and Database Storage
    data_source = st.radio(
        "Data Source Ingestion Path",
        ["PostgreSQL Database", "Legacy JSONL Stream"],
        index=0,
    )

    auto_refresh = st.toggle("⚡ Live Polling", value=True)
    poll_rate = st.slider("Refresh Speed (sec)", 0.2, 2.0, 0.5, 0.1)

    if st.button("🗑️ Clear Local JSONL Ledger", use_container_width=True):
        if STREAM_FILE.exists():
            STREAM_FILE.write_text("", encoding="utf-8")
            st.rerun()

    st.divider()
    st.markdown("### 📋 Connection Status")

    # Construct and check default postgres query service
    qs = None
    db_connected = False
    try:
        qs = TelemetryQueryService.create_default()
        # Test connection by making a small call
        qs.repository._get_conn().close()
        db_connected = True
        st.success("🟢 PostgreSQL Connected")
    except Exception:
        st.error("🔴 PostgreSQL Disconnected")

    if STREAM_FILE.exists():
        st.success("🟢 Stream File Connected")
    else:
        st.warning("⚠️ Stream File Missing")

# Title and header
st.title("⚡ Aegis Persistent Telemetry Stream")
st.caption(
    "Consuming unified telemetry validated against Device Registries and persisted to Timeseries-ready storage"
)

# Load records based on UI toggle selection
if data_source == "PostgreSQL Database" and db_connected and qs:
    records = _load_postgres_history(qs)
else:
    records = _load_legacy_telemetry_stream()

if records:
    # Build dataframe
    window_records = records[-300:]
    df = pd.DataFrame(window_records)

    # Active producers metadata
    sources = df["source"].unique()
    devices = df["device_id"].unique()
    st.caption(
        f"**Active Registered Devices ({len(devices)}):** {', '.join(devices)} | **Origins:** {', '.join(sources)}"
    )

    # Display Metrics Row
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

    # Layout Tabs
    tab_temp, tab_vib, tab_press, tab_hum, tab_raw = st.tabs(
        [
            "🌡️ Temperature",
            "〰️ Vibration",
            "🎚️ Pressure",
            "💧 Humidity",
            "📜 Raw Observations Ledger",
        ]
    )

    with tab_temp:
        temp_df = df[df["sensor_id"].str.contains("temp")]
        if not temp_df.empty:
            pivot_temp = temp_df.pivot_table(
                index="time_label",
                columns="sensor_id",
                values="value",
                aggfunc="last",
            )
            st.line_chart(pivot_temp, height=350)

    with tab_vib:
        vib_df = df[df["sensor_id"].str.contains("vibration")]
        if not vib_df.empty:
            pivot_vib = vib_df.pivot_table(
                index="time_label",
                columns="sensor_id",
                values="value",
                aggfunc="last",
            )
            st.line_chart(pivot_vib, height=350)

    with tab_press:
        press_df = df[df["sensor_id"].str.contains("pressure")]
        if not press_df.empty:
            pivot_press = press_df.pivot_table(
                index="time_label",
                columns="sensor_id",
                values="value",
                aggfunc="last",
            )
            st.line_chart(pivot_press, height=350)

    with tab_hum:
        hum_df = df[df["sensor_id"].str.contains("humidity|hum", regex=True)]
        if not hum_df.empty:
            pivot_hum = hum_df.pivot_table(
                index="time_label",
                columns="sensor_id",
                values="value",
                aggfunc="last",
            )
            st.line_chart(pivot_hum, height=350)
        else:
            st.info("No ambient humidity observations registered currently.")

    with tab_raw:
        st.dataframe(df.tail(40), use_container_width=True)

else:
    st.info(
        "Waiting for telemetry observations... Confirm PostgreSQL Docker containers are online and run a producer:\n\n"
        "1. Start Infrastructure: `docker compose up -d`\n"
        "2. Seed Identity Registry: `python -m apps.backend.seed_devices`\n"
        "3. Ingest: `python -m apps.ingestion`\n"
        "4. Stream: `python -m apps.simulator --live` or Mock ESP32 node"
    )

if auto_refresh:
    time.sleep(poll_rate)
    st.rerun()
