# ruff: noqa: E402
"""
Showcase script for Aegis Digital Asset Simulator.

Demonstrates world creation, normal operation, degradation transitions,
and clean mapping to the telemetry interchange format.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "packages") not in sys.path:
    sys.path.insert(0, str(ROOT / "packages"))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from apps.simulator.config import ScenarioType, SimulationConfig
from apps.simulator.simulator import Simulator


def _print_hierarchy(sim: Simulator) -> None:
    world_model = sim.build_world()
    print("Assets:")
    for asset in world_model.world.assets:
        print(f"  ✓ {asset.name} (ID: {asset.asset_id})")
        for device in asset.devices:
            print(f"    └── Device: {device.name} (ID: {device.device_id})")
            for sensor in device.sensors:
                print(f"          └── Sensor: {sensor.name} (ID: {sensor.sensor_id})")


def _run_normal_phase(sim: Simulator) -> None:
    print("\n--------------------------------------------------------")
    print(" LIVE SIMULATION — TICK 1 TO 5 (NORMAL)")
    print("--------------------------------------------------------")

    for tick in range(1, 6):
        res = sim.run_tick(tick)
        print(f"\nT+{tick:02d} [{res.timestamp.strftime('%H:%M:%S')}]")
        for obs in res.observations:
            name = obs.metadata.get("asset", "")
            sen = obs.sensor_id
            val = obs.value
            unit = obs.unit
            qual = obs.quality.value
            print(f"  {name:<10} | {sen:<20} | {val:>5} {unit:<10} | Quality: {qual}")


def _run_degradation_phase(sim: Simulator) -> None:
    print("\n--------------------------------------------------------")
    print(" SCENARIO TRANSITION — TICK 6 TO 10 (DEGRADATION)")
    print("--------------------------------------------------------")

    for tick in range(6, 11):
        res = sim.run_tick(tick)
        print(f"\nT+{tick:02d} [{res.timestamp.strftime('%H:%M:%S')}] - DEGRADATION ACTIVE")
        for obs in res.observations:
            is_high = ("temp" in obs.sensor_id and obs.value > 75.0) or (
                "vibration" in obs.sensor_id and obs.value > 2.5
            )
            warn = "⚠️  ABNORMAL " if is_high else "   "
            name = obs.metadata.get("asset", "")
            sen = obs.sensor_id
            val = obs.value
            unit = obs.unit
            qual = obs.quality.value
            print(f"  {warn}{name:<10} | {sen:<20} | {val:>5} {unit:<10} | Quality: {qual}")


def _verify_telemetry_and_repo(sim: Simulator, config: SimulationConfig) -> None:
    print("\n--------------------------------------------------------")
    print(" TELEMETRY CONTRACT & REPOSITORY VERIFICATION")
    print("--------------------------------------------------------")

    last_res = sim.run_tick(10)
    print("Telemetry Mapping validation for final Tick #10:")
    for envelope in last_res.envelopes:
        print(f"\n  Device Envelope ID: {envelope.source_device_id}")
        print(f"  Schema Version:     {envelope.schema_version}")
        print(f"  Observations count: {len(envelope.observations)}")
        for payload in envelope.observations:
            sid = payload.sensor_id
            val = payload.value
            unit = payload.unit
            qual = payload.quality
            print(f"    - ID: {payload.observation_id:<24} {sid:<20} {val:>5} {unit:<10} {qual}")

    repo = sim.repository
    persisted_world = repo.get(config.world_id)
    print(f"\n  Repository: World '{persisted_world.world.name}' successfully retrieved.")
    print("  ✓ Successful mapping and persistence verified.")


def main() -> int:
    config = SimulationConfig(
        scenario=ScenarioType.DEGRADATION,
        degradation_start_tick=6,
        total_ticks=10,
        seed=42,
    )

    sim = Simulator(config)

    print("========================================================")
    print(" AEGIS — DIGITAL WORLD SIMULATION SHOWCASE")
    print("========================================================")
    print(f"World: {config.world_name}")
    print(f"Seed:  {config.seed}")
    print("\nGenerating asset hierarchy...")

    _print_hierarchy(sim)
    _run_normal_phase(sim)
    _run_degradation_phase(sim)
    _verify_telemetry_and_repo(sim, config)

    print("\n========================================================")
    print(" Simulation completed successfully")
    print("========================================================\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
