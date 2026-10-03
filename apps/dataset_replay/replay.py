from __future__ import annotations
import json
import logging
import sys
import time
from pathlib import Path

# Fix python import path to see packages/
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "packages") not in sys.path:
    sys.path.insert(0, str(ROOT / "packages"))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import paho.mqtt.client as mqtt
from contracts import TelemetryEnvelope
from apps.dataset_replay.config import DatasetReplayConfig
from apps.dataset_replay.adapter import CmapssAdapter

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("aegis.dataset_replay.replay")

class CmapssReplayEngine:
    """Manages publishing historical C-MAPSS telemetry streams over MQTT to Aegis."""

    def __init__(self, config: DatasetReplayConfig | None = None) -> None:
        self.config = config or DatasetReplayConfig()
        self.adapter = CmapssAdapter(self.config)
        self.client: mqtt.Client | None = None
        self._connected = False

    def connect(self) -> None:
        """Establish connection with the MQTT broker."""
        if hasattr(mqtt, "CallbackAPIVersion"):
            self.client = mqtt.Client(
                callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
                client_id=self.config.client_id
            )
        else:
            self.client = mqtt.Client(client_id=self.config.client_id)

        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect

        logger.info("Connecting to broker at %s:%d...", self.config.mqtt_host, self.config.mqtt_port)
        self.client.connect(self.config.mqtt_host, self.config.mqtt_port, keepalive=60)
        self.client.loop_start()

        attempts = 0
        while not self._connected and attempts < 10:
            time.sleep(0.5)
            attempts += 1

        if not self._connected:
            raise ConnectionError("Failed to connect to the broker.")

    def _on_connect(self, client, userdata, flags, rc, *args, **kwargs) -> None:
        rc_code = rc.value if hasattr(rc, "value") else rc
        if rc_code == 0:
            self._connected = True
            logger.info("MQTT Connection established.")
        else:
            logger.error("MQTT Connection failed with result code %s", rc)

    def _on_disconnect(self, client, userdata, *args, **kwargs) -> None:
        self._connected = False
        logger.warning("Disconnected from MQTT broker.")

    def publish_envelope(self, envelope: TelemetryEnvelope) -> None:
        """Serialize and publish an individual envelope to the broker."""
        if not self.client or not self._connected:
            raise RuntimeError("Engine is not connected to MQTT broker.")

        payload_str = json.dumps(envelope.to_dict())
        topic = f"aegis/telemetry/{envelope.source_device_id}"
        
        info = self.client.publish(topic, payload_str, qos=1)
        info.wait_for_publish()

    def start_replay(
        self,
        limit_units: list[int] | None = None,
        delay_seconds: float = 0.1,
        max_records: int = 0
    ) -> int:
        """Parse historical log and replay envelopes in real-time."""
        if not self._connected:
            self.connect()

        logger.info("Starting historical stream replay...")
        logger.info("  Delay: %s sec | Max Records: %s", delay_seconds, max_records if max_records > 0 else "Unlimited")
        
        count = 0
        try:
            for envelope in self.adapter.iter_envelopes(limit_units=limit_units):
                self.publish_envelope(envelope)
                count += 1
                
                if count % 10 == 0:
                    logger.info("Published %d historical envelopes...", count)

                if max_records > 0 and count >= max_records:
                    logger.info("Reached defined processing limit of %d records.", max_records)
                    break

                if delay_seconds > 0:
                    time.sleep(delay_seconds)

            logger.info("Replay sequence finished. Transmitted %d records.", count)
            return count
        except KeyboardInterrupt:
            logger.info("Replay interrupted by user.")
            return count
        except Exception as err:
            logger.exception("Fatal error during telemetry replay: %s", err)
            return count

    def disconnect(self) -> None:
        """Gracefully disconnect the loop."""
        if self.client:
            self.client.loop_stop()
            self.client.disconnect()
            self._connected = False
            logger.info("MQTT Replay engine stopped.")
