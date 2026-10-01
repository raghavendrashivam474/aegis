# ruff: noqa: E501
# ruff: noqa: E402
"""
Aegis Telemetry Dashboard (Contract & Database Consumer).

Displays live streaming telemetry, and allows viewing historical data directly
from PostgreSQL or the legacy JSONL local ledger stream.
"""

from __future__ import annotations

import json
import math
import os
import random
import sys
import threading
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "packages") not in sys.path:
    sys.path.insert(0, str(ROOT / "packages"))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd
import streamlit as st
from contracts import ObservationPayload, TelemetryEnvelope
from domain import Observation, QualityFlag

from apps.backend.postgres_adapter import PostgresDeviceRegistry, PostgresTelemetryRepository
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


def _update_regime(state: dict) -> str:
    """Update regime ticks and select the next operational state."""
    state["regime_ticks_left"] -= 1
    if state["regime_ticks_left"] <= 0:
        roll = random.random()
        if roll < 0.70:
            state["regime"] = "NOMINAL"
            state["regime_ticks_left"] = random.randint(25, 45)
        elif roll < 0.82:
            state["regime"] = "THERMAL_LOAD"
            state["regime_ticks_left"] = random.randint(15, 25)
        elif roll < 0.92:
            state["regime"] = "CAVITATION"
            state["regime_ticks_left"] = random.randint(10, 20)
        else:
            state["regime"] = "PRESSURE_SURGE"
            state["regime_ticks_left"] = random.randint(8, 15)
    return str(state["regime"])


def _compute_motor_01_readings(regime: str, tick: int) -> tuple[float, float, float, float]:
    """Compute Motor 01 physical readings based on operational regime."""
    if regime == "THERMAL_LOAD":
        temp = round(78.0 + random.uniform(-1.0, 7.5), 2)
        vib = round(2.6 + random.uniform(0.1, 1.0), 2)
        press = round(5.1 + random.uniform(-0.2, 0.3), 2)
    elif regime == "CAVITATION":
        temp = round(64.0 + random.uniform(-1.5, 1.5), 2)
        vib = round(3.5 + random.uniform(0.2, 1.6), 2)
        press = round(2.4 + random.uniform(-0.4, 0.4), 2)
    elif regime == "PRESSURE_SURGE":
        temp = round(66.0 + random.uniform(-1.0, 2.5), 2)
        vib = round(2.8 + random.uniform(0.1, 0.8), 2)
        press = round(6.7 + random.uniform(0.2, 0.8), 2)
    else:  # NOMINAL
        temp = round(62.0 + 3.0 * math.sin(tick * 0.1) + random.gauss(0, 0.5), 2)
        vib = round(1.6 + 0.4 * math.sin(tick * 0.15) + random.gauss(0, 0.1), 2)
        press = round(4.8 + 0.3 * math.cos(tick * 0.08) + random.gauss(0, 0.1), 2)

    hum = round(52.0 + 4.0 * math.sin(tick * 0.05) + random.gauss(0, 0.6), 2)
    return temp, press, vib, hum


def _generate_sensor_readings(state: dict, tick: int) -> list[tuple[str, str, float, str]]:
    """Generate multi-asset readings across Motor-01, Motor-02, and ESP32."""
    regime = _update_regime(state)
    m1_temp, m1_press, m1_vib, m1_hum = _compute_motor_01_readings(regime, tick)

    # Motor 02 (coupled thermal and vibration curve)
    m2_temp = round(58.0 + (m1_temp - 60.0) * 0.6 + random.gauss(0, 0.4), 2)
    m2_press = round(4.2 + (m1_press - 4.8) * 0.5 + random.gauss(0, 0.1), 2)
    m2_vib = round(1.9 + (m1_vib - 1.6) * 0.7 + random.gauss(0, 0.1), 2)
    m2_hum = round(48.0 + 3.0 * math.cos(tick * 0.04) + random.gauss(0, 0.5), 2)

    # Physical ESP32 Node
    esp_temp = round(41.0 + (m1_temp - 60.0) * 0.3 + random.gauss(0, 0.3), 2)
    esp_hum = round(60.0 + 5.0 * math.sin(tick * 0.03) + random.gauss(0, 0.8), 2)
    esp_vib = round(0.8 + (m1_vib - 1.6) * 0.3 + random.gauss(0, 0.05), 2)

    return [
        ("device-motor-01", "sensor-temp-01", m1_temp, "celsius"),
        ("device-motor-01", "sensor-pressure-01", m1_press, "bar"),
        ("device-motor-01", "sensor-vibration-01", m1_vib, "mm/s"),
        ("device-motor-01", "sensor-humidity-01", m1_hum, "percent"),
        ("device-motor-02", "sensor-temp-02", m2_temp, "celsius"),
        ("device-motor-02", "sensor-pressure-02", m2_press, "bar"),
        ("device-motor-02", "sensor-vibration-02", m2_vib, "mm/s"),
        ("device-motor-02", "sensor-humidity-02", m2_hum, "percent"),
        ("device-esp32-01", "sensor-temp-device-esp32-01", esp_temp, "celsius"),
        ("device-esp32-01", "sensor-humidity-device-esp32-01", esp_hum, "percent"),
        ("device-esp32-01", "sensor-vibration-device-esp32-01", esp_vib, "mm/s"),
    ]


def _persist_to_jsonl_stream(
    readings: list[tuple[str, str, float, str]], timestamp: datetime
) -> None:
    """Appends envelopes to the local JSONL stream file and keeps it bounded."""
    try:
        STREAM_FILE.parent.mkdir(parents=True, exist_ok=True)
        now_iso = timestamp.isoformat()

        # Group readings by device
        by_device: dict[str, list[ObservationPayload]] = {}
        for dev_id, sens_id, val, unit in readings:
            if dev_id not in by_device:
                by_device[dev_id] = []
            by_device[dev_id].append(
                ObservationPayload(
                    observation_id=str(uuid.uuid4()),
                    sensor_id=sens_id,
                    timestamp_iso=now_iso,
                    value=val,
                    unit=unit,
                )
            )

        new_lines = []
        for dev_id, obs_list in by_device.items():
            env = TelemetryEnvelope(
                schema_version="v1",
                source_device_id=dev_id,
                sent_at_iso=now_iso,
                observations=obs_list,
                metadata={
                    "source": "simulator" if "motor" in dev_id else "physical",
                    "transport": "live-stream",
                },
            )
            new_lines.append(json.dumps(env.to_dict()) + "\n")

        # Read existing, append, and rotate to last 300 lines
        existing = []
        if STREAM_FILE.exists():
            with STREAM_FILE.open("r", encoding="utf-8") as f:
                existing = f.readlines()

        total = (existing + new_lines)[-300:]
        with STREAM_FILE.open("w", encoding="utf-8") as f:
            f.writelines(total)
    except Exception:
        pass


def _persist_to_database(
    repo: PostgresTelemetryRepository | None,
    readings: list[tuple[str, str, float, str]],
    timestamp: datetime,
) -> None:
    """Persist generated readings as domain observations into PostgreSQL."""
    if repo is None:
        return
    try:
        batch = [
            Observation(
                observation_id=str(uuid.uuid4()),
                device_id=dev_id,
                sensor_id=sens_id,
                timestamp=timestamp,
                value=val,
                unit=unit,
                quality=QualityFlag.UNCERTAIN
                if ("vib" in sens_id and val > 4.2)
                else QualityFlag.GOOD,
                metadata={
                    "source": "simulator" if "motor" in dev_id else "physical",
                    "transport": "autonomous-cloud",
                },
            )
            for dev_id, sens_id, val, unit in readings
        ]
        repo.save_batch(batch)
    except Exception:
        pass


@st.cache_resource
def _start_autonomous_cloud_streamer(database_url: str) -> None:
    """Starts a singleton background daemon thread simulating realistic Oil & Gas industrial assets."""

    def _feeder_loop() -> None:
        state = {"regime": "NOMINAL", "regime_ticks_left": 30}
        repo = None
        try:
            repo = PostgresTelemetryRepository(database_url)
        except Exception:
            pass

        tick = 0
        while True:
            tick += 1
            now = datetime.now(UTC)
            readings = _generate_sensor_readings(state, tick)
            _persist_to_database(repo, readings, now)
            _persist_to_jsonl_stream(readings, now)
            time.sleep(1.0)

    feeder_thread = threading.Thread(
        target=_feeder_loop,
        daemon=True,
        name="AegisCloudAutonomousFeeder",
    )
    feeder_thread.start()


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
                    ts_dt = datetime.now(UTC)

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

    cloud_stream_toggle = st.toggle("🌐 Autonomous Live Feeder", value=True)

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

    if cloud_stream_toggle:
        _start_autonomous_cloud_streamer(DEFAULT_DB_URL)
        st.caption("⚡ Autonomous Dual Feeder Active")

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
            s_id = row["sensor_id"]
            val = float(row["value"])

            # Realistic Industrial Thresholds & Diagnostics
            if "temp" in s_id and val > 75.0:
                delta_label = "⚠️ Overheating"
                delta_color = "inverse"
            elif "pressure" in s_id and val < 3.0:
                delta_label = "⚠️ Low Suction"
                delta_color = "inverse"
            elif "pressure" in s_id and val > 6.2:
                delta_label = "⚠️ Overpressure"
                delta_color = "inverse"
            elif "vibration" in s_id and val > 2.5:
                delta_label = "⚠️ High Vib"
                delta_color = "inverse"
            elif "humidity" in s_id and val > 70.0:
                delta_label = "⚠️ High Hum"
                delta_color = "inverse"
            else:
                delta_label = "NORMAL"
                delta_color = "normal"

            src_tag = f"[{row['source']}]"
            st.metric(
                label=f"{row['device_id']} · {s_id} {src_tag}",
                value=val_str,
                delta=delta_label,
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
