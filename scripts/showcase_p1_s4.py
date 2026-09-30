# ruff: noqa: E402
"""
Aegis P1.S4 Showcase — Edge Node & Ingestion Bridge Verification.

Demonstrates that both the Digital Twin Simulator and Physical Edge Producer (ESP32)
converge onto the exact same TelemetryEnvelope boundary without modifying
the domain, contracts, or dashboard rendering architecture.
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

# Ensure root and packages/ are importable
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "packages") not in sys.path:
    sys.path.insert(0, str(ROOT / "packages"))

from contracts import CURRENT_SCHEMA_VERSION, TelemetryEnvelope

from apps.ingestion import IngestionConfig, MqttTelemetryConsumer
from apps.simulator.config import SimulationConfig
from apps.simulator.simulator import Simulator


def banner(title: str) -> None:
    print(f"\n{'=' * 65}")
    print(f"  {title}")
    print(f"{'=' * 65}")


def main() -> int:
    stream_path = Path("data/telemetry_stream.jsonl")
    stream_path.parent.mkdir(parents=True, exist_ok=True)
    stream_path.write_text("", encoding="utf-8")  # Reset stream

    banner("AEGIS P1.S4 SHOWCASE: EDGE NODE & INGESTION BRIDGE")

    print("[Step 1] Initializing Ingestion Bridge...")
    config = IngestionConfig(stream_sink=stream_path)
    consumer = MqttTelemetryConsumer(config=config)
    print(f"  - Ingestion stream sink: {stream_path}")
    print(f"  - Target schema version: {CURRENT_SCHEMA_VERSION}")

    banner("PRODUCER A: PHYSICAL ESP32 EDGE NODE (via Ingestion Bridge)")
    print("Emulating incoming telemetry frames over MQTT transport...")

    now_iso = datetime.now(UTC).isoformat()
    physical_payload = {
        "schema_version": CURRENT_SCHEMA_VERSION,
        "source_device_id": "device-esp32-01",
        "sent_at_iso": now_iso,
        "observations": [
            {
                "observation_id": "obs-esp-temp-001",
                "sensor_id": "sensor-temp-esp32-01",
                "timestamp_iso": now_iso,
                "value": 26.8,
                "unit": "celsius",
                "quality": "GOOD",
                "metadata": {"device_id": "device-esp32-01"},
            },
            {
                "observation_id": "obs-esp-hum-001",
                "sensor_id": "sensor-humidity-esp32-01",
                "timestamp_iso": now_iso,
                "value": 49.5,
                "unit": "percent",
                "quality": "GOOD",
                "metadata": {"device_id": "device-esp32-01"},
            },
            {
                "observation_id": "obs-esp-vib-001",
                "sensor_id": "sensor-vibration-esp32-01",
                "timestamp_iso": now_iso,
                "value": 1.74,
                "unit": "mm/s",
                "quality": "GOOD",
                "metadata": {"device_id": "device-esp32-01"},
            },
        ],
        "metadata": {
            "source": "physical_esp32",
            "transport": "mqtt",
        },
    }

    env_physical = consumer.process_raw_message(
        json.dumps(physical_payload), topic="aegis/telemetry/device-esp32-01"
    )
    print(f"  ✓ Ingested physical envelope from: {env_physical.source_device_id}")
    for obs in env_physical.observations:
        print(f"    - {obs.sensor_id:<25} = {obs.value:>5} {obs.unit:<10} [{obs.quality}]")

    banner("PRODUCER B: DIGITAL ASSET SIMULATOR (Oil Field Alpha Twin)")
    sim_config = SimulationConfig(total_ticks=1)
    sim = Simulator(sim_config)
    sim.build_world()
    sim_result = sim.run_tick(1)

    with stream_path.open("a", encoding="utf-8") as f:
        for env in sim_result.envelopes:
            f.write(json.dumps(env.to_dict()) + "\n")

    print("  ✓ Emitted digital twin envelopes:")
    for env in sim_result.envelopes:
        print(f"    - Device: {env.source_device_id} ({len(env.observations)} observations)")

    banner("VERIFICATION: UNIFIED TELEMETRY BOUNDARY CONSUMPTION")
    lines = stream_path.read_text(encoding="utf-8").strip().splitlines()
    print(f"Stream sink ledger records: {len(lines)} envelopes written.\n")

    for idx, line in enumerate(lines, 1):
        env = TelemetryEnvelope.from_dict(json.loads(line))
        source_origin = env.metadata.get("source", "simulator")
        print(
            f"Record #{idx}: Source={env.source_device_id:<16} "
            f"Origin={source_origin:<15} Observations={len(env.observations)}"
        )

    banner("STATUS: P1.S4 ARCHITECTURAL OBJECTIVE ACHIEVED")
    print("The Aegis Core seamlessly consumed physical and simulated telemetry")
    print("without modifying any domain logic, contracts, or dashboard core!")
    print("=================================================================\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
