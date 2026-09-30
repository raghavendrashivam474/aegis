# ruff: noqa: E402
"""MQTT Telemetry Consumer and Stream Forwarder."""

from __future__ import annotations

import json
import logging
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

# Ensure packages/ is importable
_PACKAGES = str(Path(__file__).resolve().parents[2] / "packages")
if _PACKAGES not in sys.path:
    sys.path.insert(0, _PACKAGES)

import paho.mqtt.client as mqtt
from contracts import TelemetryEnvelope

from .config import IngestionConfig
from .decoder import TelemetryDecodeError, TelemetryDecoder

logger = logging.getLogger(__name__)


class MqttTelemetryConsumer:
    """
    Subscribes to MQTT telemetry topics, validates incoming contracts,
    and sinks them to the shared Aegis IPC stream or custom handler.
    """

    def __init__(
        self,
        config: IngestionConfig | None = None,
        on_envelope: Callable[[TelemetryEnvelope], None] | None = None,
    ) -> None:
        self.config = config or IngestionConfig()
        self._on_envelope = on_envelope or self._default_sink_handler
        self._client: mqtt.Client | None = None
        self._is_connected = False
        self.received_count = 0
        self.invalid_count = 0

    def _default_sink_handler(self, envelope: TelemetryEnvelope) -> None:
        """Append envelope to JSONL telemetry stream sink."""
        sink_path = self.config.stream_sink
        sink_path.parent.mkdir(parents=True, exist_ok=True)
        with sink_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(envelope.to_dict()) + "\n")

    def process_raw_message(
        self, payload: str | bytes, topic: str = ""
    ) -> TelemetryEnvelope | None:
        """
        Decode and process raw message without needing a live MQTT broker.
        Useful for testing and direct pipeline processing.
        """
        try:
            envelope = TelemetryDecoder.decode(payload)
            self._on_envelope(envelope)
            self.received_count += 1
            return envelope
        except TelemetryDecodeError as err:
            self.invalid_count += 1
            logger.warning("Dropped invalid message on topic '%s': %s", topic, err)
            return None

    def _on_connect(
        self,
        client: mqtt.Client,
        userdata: Any,
        flags: Any,
        rc: int | mqtt.ReasonCode,
        properties: Any = None,
    ) -> None:
        """Callback for MQTT broker connection established."""
        rc_code = rc.value if hasattr(rc, "value") else rc
        if rc_code == 0:
            self._is_connected = True
            logger.info(
                "Connected to MQTT broker at %s:%s",
                self.config.broker_host,
                self.config.broker_port,
            )
            client.subscribe(self.config.topic)
            logger.info("Subscribed to topic pattern: %s", self.config.topic)
        else:
            self._is_connected = False
            logger.error("Connection failed with result code %s", rc)

    def _on_disconnect(
        self,
        client: mqtt.Client,
        userdata: Any,
        flags: Any,
        rc: int | mqtt.ReasonCode,
        properties: Any = None,
    ) -> None:
        """Callback for MQTT broker disconnection."""
        self._is_connected = False
        logger.warning(
            "Disconnected from MQTT broker (rc: %s). Reconnection handled automatically.", rc
        )

    def _on_message(self, client: mqtt.Client, userdata: Any, msg: mqtt.MQTTMessage) -> None:
        """Callback when an MQTT message is received."""
        self.process_raw_message(msg.payload, topic=msg.topic)

    def start(self, blocking: bool = True) -> None:
        """Connect to broker and start message consumer loop."""
        if hasattr(mqtt, "CallbackAPIVersion"):
            self._client = mqtt.Client(
                callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
                client_id=self.config.client_id,
            )
        else:
            self._client = mqtt.Client(client_id=self.config.client_id)

        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect
        self._client.on_message = self._on_message

        logger.info(
            "Connecting to broker %s:%s...", self.config.broker_host, self.config.broker_port
        )
        self._client.connect(
            self.config.broker_host,
            self.config.broker_port,
            self.config.keepalive,
        )

        if blocking:
            self._client.loop_forever()
        else:
            self._client.loop_start()

    def stop(self) -> None:
        """Disconnect and stop the loop cleanly."""
        if self._client:
            self._client.loop_stop()
            self._client.disconnect()
            self._is_connected = False
            logger.info("MQTT Consumer stopped.")

    @property
    def is_connected(self) -> bool:
        return self._is_connected
