"""
Mock ESP32 Physical Edge Node (MQTT Publisher).

Simulates the exact payload and network behavior of the ESP32 firmware
for automated testing, development, and mentor demonstrations.
"""

from __future__ import annotations

import argparse
import json
import random
import time
from datetime import UTC, datetime

import paho.mqtt.client as mqtt


def main() -> int:
    parser = argparse.ArgumentParser(description="Mock ESP32 Telemetry Publisher")
    parser.add_argument("--host", type=str, default="localhost", help="MQTT Broker host")
    parser.add_argument("--port", type=int, default=1883, help="MQTT Broker port")
    parser.add_argument("--interval", type=float, default=1.0, help="Publish interval (seconds)")
    parser.add_argument("--count", type=int, default=0, help="Message count (0 = infinite)")
    parser.add_argument("--device-id", type=str, default="device-esp32-01", help="Device ID")
    parser.add_argument(
        "--topic",
        type=str,
        default="aegis/telemetry/device-esp32-01",
        help="Target MQTT topic",
    )

    args = parser.parse_args()

    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id=f"mock-{args.device_id}",
    )

    print("==================================================")
    print(" MOCK ESP32 EDGE NODE (MQTT PRODUCER)")
    print("==================================================")
    print(f"Broker:          {args.host}:{args.port}")
    print(f"Device ID:       {args.device_id}")
    print(f"Topic:           {args.topic}")
    print(f"Interval:        {args.interval}s")
    print("==================================================")

    try:
        client.connect(args.host, args.port, 60)
        client.loop_start()
    except Exception as err:
        print(f"Failed to connect to MQTT broker: {err}")
        return 1

    seq = 0
    try:
        while True:
            seq += 1
            now_iso = datetime.now(UTC).isoformat()

            temp_val = round(25.0 + random.uniform(-1.5, 3.5), 2)
            hum_val = round(52.0 + random.uniform(-3.0, 4.0), 2)
            vib_val = round(1.2 + random.uniform(-0.2, 0.4), 3)

            envelope = {
                "schema_version": "v1",
                "source_device_id": args.device_id,
                "sent_at_iso": now_iso,
                "observations": [
                    {
                        "observation_id": f"obs-esp-temp-{seq:04d}",
                        "sensor_id": f"sensor-temp-{args.device_id}",
                        "timestamp_iso": now_iso,
                        "value": temp_val,
                        "unit": "celsius",
                        "quality": "GOOD",
                        "metadata": {"device_id": args.device_id},
                    },
                    {
                        "observation_id": f"obs-esp-hum-{seq:04d}",
                        "sensor_id": f"sensor-humidity-{args.device_id}",
                        "timestamp_iso": now_iso,
                        "value": hum_val,
                        "unit": "percent",
                        "quality": "GOOD",
                        "metadata": {"device_id": args.device_id},
                    },
                    {
                        "observation_id": f"obs-esp-vib-{seq:04d}",
                        "sensor_id": f"sensor-vibration-{args.device_id}",
                        "timestamp_iso": now_iso,
                        "value": vib_val,
                        "unit": "mm/s",
                        "quality": "GOOD",
                        "metadata": {"device_id": args.device_id},
                    },
                ],
                "metadata": {
                    "source": "physical_esp32",
                    "transport": "mqtt",
                    "seq": seq,
                },
            }

            payload_str = json.dumps(envelope)
            client.publish(args.topic, payload_str)
            print(
                f"[{now_iso}] [TX] seq #{seq}: Temp={temp_val}°C, Hum={hum_val}%, Vib={vib_val}mm/s"
            )

            if args.count > 0 and seq >= args.count:
                break

            time.sleep(args.interval)

    except KeyboardInterrupt:
        print("\nPublisher stopped by user.")
    finally:
        client.loop_stop()
        client.disconnect()

    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
