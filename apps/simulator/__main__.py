"""Command-line entry point for running the Aegis Digital Asset Simulator."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from .config import ScenarioType, SimulationConfig
from .simulator import Simulator

DEFAULT_STREAM = Path("data/telemetry_stream.jsonl")


def main() -> int:
    parser = argparse.ArgumentParser(description="Aegis Digital Asset Simulator")
    parser.add_argument(
        "--ticks",
        type=int,
        default=0,
        help="Total ticks to run (0 = run indefinitely until Ctrl+C)",
    )
    parser.add_argument(
        "--interval", type=float, default=0.5, help="Simulation tick interval in seconds"
    )
    parser.add_argument(
        "--scenario",
        type=str,
        choices=["normal", "degradation"],
        default="normal",
        help="Simulation scenario mode",
    )
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility")
    parser.add_argument("--live", action="store_true", help="Run with live delay between ticks")
    parser.add_argument(
        "--reset-stream", action="store_true", help="Clear existing telemetry stream file"
    )

    args = parser.parse_args()

    if args.reset_stream or args.live or args.ticks == 0:
        DEFAULT_STREAM.parent.mkdir(parents=True, exist_ok=True)
        DEFAULT_STREAM.write_text("", encoding="utf-8")

    scenario_enum = ScenarioType(args.scenario)
    config = SimulationConfig(
        total_ticks=args.ticks,
        simulation_interval=args.interval,
        scenario=scenario_enum,
        seed=args.seed,
    )

    ticks_desc = "INFINITE (Press Ctrl+C to stop)" if args.ticks == 0 else str(args.ticks)

    print("==================================================")
    print(" AEGIS DIGITAL ASSET SIMULATOR (PRODUCER)")
    print("==================================================")
    print(f"World ID:            {config.world_id}")
    print(f"World Name:          {config.world_name}")
    print(f"Assets Count:        {len(config.assets)}")
    print(f"Scenario:            {config.scenario.name}")
    print(f"Random Seed:         {config.seed}")
    print(f"Ticks Mode:          {ticks_desc}")
    print(f"Tick Interval:       {config.simulation_interval}s")
    print(f"IPC Stream Sink:     {DEFAULT_STREAM}")
    print("==================================================")

    sim = Simulator(config)
    sim.build_world()

    print("\nEmitting continuous live telemetry stream...\n")

    tick = 1
    try:
        while True:
            result = sim.run_tick(tick)
            ts = result.timestamp.strftime("%H:%M:%S")
            print(f"[{ts}] Tick #{tick}")

            # Write Telemetry Envelope JSON payloads to stream sink
            with DEFAULT_STREAM.open("a", encoding="utf-8") as f:
                for env in result.envelopes:
                    f.write(json.dumps(env.to_dict()) + "\n")

            for obs in result.observations:
                dev_id = obs.device_id
                sen_id = obs.sensor_id
                val = obs.value
                unit = obs.unit
                qual = obs.quality.value
                print(f"  {dev_id} | {sen_id:<20} | {val:>5} {unit:<10} | Quality: {qual}")

            tick += 1
            if args.ticks > 0 and tick > args.ticks:
                break

            time.sleep(config.simulation_interval)

    except KeyboardInterrupt:
        print("\n\n==================================================")
        print(" Simulation stopped cleanly by user (Ctrl+C)")
        print("==================================================")
        return 0

    print("\n==================================================")
    print(" Batch simulation completed successfully")
    print("==================================================")
    return 0


if __name__ == "__main__":
    sys.exit(main())
