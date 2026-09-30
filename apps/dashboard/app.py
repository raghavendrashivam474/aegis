# ruff: noqa: E402
"""
Aegis Telemetry Dashboard (Contract Consumer).

Pure subscriber UI that reads deserialized TelemetryEnvelope contracts
emitted by independent producers (Simulator, Physical ESP32 via MQTT Ingestion Bridge).
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "packages") not in sys.path:
    sys.path.insert(0, str(ROOT / "packages"))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd
import streamlit as st
from contracts import TelemetryEnvelope

STREAM_FILE = Path("data/telemetry_stream.jsonl")

st.set_page_config(
    page_title="Aegis — Telemetry Dashboard",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)


def _format_time_label(iso_str: str) -> str:
    """Format ISO timestamp to clean HH:MM:SS.s for X-axis pivoting."""
    try:
        time_part = iso_str.split("T")[1].split("+")[0].split("Z")[0]
        if "." in time_part:
            hhmmss, ms = time_part.split(".")
            return f"{hhmmss}.{ms[:1]}"
        return f"{time_part}.0"
    except Exception:
        return iso_str


def _load_telemetry_stream() -> list[dict]:
    """Read and deserialize TelemetryEnvelope contracts from stream ledger."""
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


with st.sidebar:
    st.title("🛡️ Aegis Dashboard")
    st.markdown("**Decoupled Telemetry Consumer**")
    st.divider()

    auto_refresh = st.toggle("⚡ Live Polling", value=True)
    poll_rate = st.slider("Refresh Speed (sec)", 0.2, 2.0, 0.5, 0.1)

    if st.button("🗑️ Clear Stream Ledger", use_container_width=True):
        if STREAM_FILE.exists():
            STREAM_FILE.write_text("", encoding="utf-8")
            st.rerun()

    st.divider()
    st.markdown("### 📋 Contract Stream Info")
    st.caption(f"Source Path: {STREAM_FILE}")
    if STREAM_FILE.exists():
        st.success("🟢 Stream Sink Connected")
    else:
        st.warning("⚠️ Stream File Not Found")

st.title("⚡ Aegis Live Telemetry Stream")
st.caption(
    "Consuming unified TelemetryEnvelope (v1) contracts from "
    "Simulator and Physical ESP32 Edge Nodes"
)

records = _load_telemetry_stream()

if records:
    window_records = records[-300:]
    df = pd.DataFrame(window_records)

    # Active producers summary
    sources = df["source"].unique()
    devices = df["device_id"].unique()
    dev_str = ", ".join(devices)
    src_str = ", ".join(sources)
    st.caption(f"**Active Producers ({len(devices)}):** {dev_str} | **Origins:** {src_str}")

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
            "🎛️ Pressure",
            "💧 Humidity (Physical)",
            "📜 Raw Envelopes Ledger",
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
            st.caption("Multi-source thermal dynamics (Digital Twins & Physical Edge)")

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
            st.caption("Multi-frequency mechanical harmonics + physical vibration")

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
            st.caption("Hydraulic pulsation with bidirectional load wander")

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
            st.caption("Ambient environmental humidity monitored by physical node")
        else:
            st.info(
                "No physical humidity observations received yet. "
                "Connect ESP32 edge node to stream humidity."
            )

    with tab_raw:
        st.dataframe(df.tail(40), use_container_width=True)

else:
    st.info(
        "Waiting for telemetry... Run either producer:\n\n"
        "1. Simulator: `python -m apps.simulator --live`\n"
        "2. Ingestion Bridge: `python -m apps.ingestion` "
        "(and publish from ESP32 or test publisher)"
    )

if auto_refresh:
    time.sleep(poll_rate)
    st.rerun()
