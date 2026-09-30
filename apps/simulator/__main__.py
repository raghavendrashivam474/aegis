"""Command-line entry point for running the Aegis Digital Asset Simulator with MQTT support."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import paho.mqtt.client as mqtt

from .config import ScenarioType, SimulationConfig
from .simulator import Simulator, TickResult

DEFAULT_STREAM = Path("data/telemetry_stream.jsonl")


def _parse_args() -> argparse.Namespace:
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
    parser.add_argument(
        "--mqtt", action="store_true", help="Publish telemetry envelopes to MQTT broker"
    )
    parser.add_argument(
        "--mqtt-host", type=str, default="localhost", help="MQTT Broker host address"
    )
    parser.add_argument("--mqtt-port", type=int, default=1883, help="MQTT Broker port")
    parser.add_argument(
        "--humidity", action="store_true", help="Include humidity sensor in digital twin topology"
    )
    parser.add_argument(
        "--wall-clock", action="store_true", help="Use real UTC wall-clock timestamps"
    )
    return parser.parse_args()


def _init_mqtt(args: argparse.Namespace) -> mqtt.Client | None:
    if not args.mqtt:
        return None

    if hasattr(mqtt, "CallbackAPIVersion"):
        client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id="aegis-simulator-producer",
        )
    else:
        client = mqtt.Client(client_id="aegis-simulator-producer")

    try:
        client.connect(args.mqtt_host, args.mqtt_port, 60)
        client.loop_start()
        print(f"Successfully connected to MQTT broker at {args.mqtt_host}:{args.mqtt_port}")
        return client
    except Exception as err:
        print(f"Failed to connect to MQTT broker: {err}")
        return None


def _print_header(config: SimulationConfig, args: argparse.Namespace) -> None:
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
    print(f"Humidity Sensor:     {config.include_humidity}")
    print(f"Wall-Clock Time:     {config.use_wall_clock}")
    if args.mqtt:
        print(f"MQTT Broker:         {args.mqtt_host}:{args.mqtt_port}")
        print("MQTT Topic Pattern:  aegis/telemetry/<device_id>")
    else:
        print(f"IPC Stream Sink:     {DEFAULT_STREAM}")
    print("==================================================")


def _dispatch_tick(
    result: TickResult,
    args: argparse.Namespace,
    client: mqtt.Client | None,
) -> None:
    if args.mqtt and client:
        for env in result.envelopes:
            topic = f"aegis/telemetry/{env.source_device_id}"
            payload_str = json.dumps(env.to_dict())
            client.publish(topic, payload_str)
    else:
        with DEFAULT_STREAM.open("a", encoding="utf-8") as f:
            for env in result.envelopes:
                f.write(json.dumps(env.to_dict()) + "\n")


def _print_observations(result: TickResult) -> None:
    for obs in result.observations:
        dev_id = obs.device_id
        sen_id = obs.sensor_id
        val = obs.value
        unit = obs.unit
        qual = obs.quality.value
        print(f"  {dev_id} | {sen_id:<28} | {val:>5} {unit:<10} | Quality: {qual}")


def main() -> int:
    args = _parse_args()

    if not args.mqtt and (args.reset_stream or args.live or args.ticks == 0):
        DEFAULT_STREAM.parent.mkdir(parents=True, exist_ok=True)
        DEFAULT_STREAM.write_text("", encoding="utf-8")

    scenario_enum = ScenarioType(args.scenario)
    use_humidity = args.humidity or args.live or args.mqtt or args.reset_stream
    use_wall = args.wall_clock or args.live or args.mqtt or args.reset_stream

    config = SimulationConfig(
        total_ticks=args.ticks,
        simulation_interval=args.interval,
        scenario=scenario_enum,
        seed=args.seed,
        include_humidity=use_humidity,
        use_wall_clock=use_wall,
    )

    _print_header(config, args)

    mqtt_client = _init_mqtt(args)
    if args.mqtt and mqtt_client is None:
        return 1

    sim = Simulator(config)
    sim.build_world()

    print("\nEmitting continuous live telemetry stream...\n")
    tick = 1
    try:
        while True:
            result = sim.run_tick(tick)
            ts = result.timestamp.strftime("%H:%M:%S")
            print(f"[{ts}] Tick #{tick}")

            _dispatch_tick(result, args, mqtt_client)
            _print_observations(result)

            tick += 1
            if args.ticks > 0 and tick > args.ticks:
                break

            time.sleep(config.simulation_interval)

    except KeyboardInterrupt:
        print("\n\n==================================================")
        print(" Simulation stopped cleanly by user (Ctrl+C)")
        print("==================================================")
    finally:
        if mqtt_client:
            mqtt_client.loop_stop()
            mqtt_client.disconnect()
            print("MQTT Connection terminated.")

    print("\n==================================================")
    print(" Simulation run completed successfully")
    print("==================================================")
    return 0


if __name__ == "__main__":
    sys.exit(main())
