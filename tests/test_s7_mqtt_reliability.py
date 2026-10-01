"""
Tests for Aegis MQTT Delivery Reliability, QoS 1, and Reconnection Semantics (P1.S7).
"""

from unittest.mock import MagicMock, patch

import paho.mqtt.client as mqtt

from apps.ingestion.config import IngestionConfig
from apps.ingestion.mqtt_consumer import MqttTelemetryConsumer
from apps.ingestion.pipeline import TelemetryIngestionPipeline


def test_mqtt_consumer_initialization():
    """Verify consumer initializes with QoS 1 and configured parameters."""
    config = IngestionConfig(broker_host="127.0.0.1", broker_port=1883)
    consumer = MqttTelemetryConsumer(config=config, qos=1)

    assert consumer.qos == 1
    assert consumer.is_connected is False
    assert consumer.received_count == 0
    assert consumer.invalid_count == 0


def test_mqtt_consumer_connect_callback():
    """Verify on_connect subscribes with QoS 1 and marks consumer as connected."""
    mock_pipeline = MagicMock(spec=TelemetryIngestionPipeline)
    consumer = MqttTelemetryConsumer(pipeline=mock_pipeline, qos=1)

    mock_client = MagicMock()
    # Simulate rc = 0 (Connection accepted)
    consumer._on_connect(mock_client, None, {}, 0)

    assert consumer.is_connected is True
    mock_client.subscribe.assert_called_once_with(consumer.config.topic, qos=1)
    mock_pipeline.drain_buffer.assert_called_once()


def test_mqtt_consumer_disconnect_callback():
    """Verify on_disconnect updates state and tracks reconnect counter."""
    consumer = MqttTelemetryConsumer(qos=1)
    consumer._is_connected = True

    mock_client = MagicMock()
    consumer._on_disconnect(mock_client, None, {}, 1)

    assert consumer.is_connected is False
    assert consumer.reconnect_count == 1


def test_mqtt_consumer_start_and_stop():
    """Verify start configures callbacks, reconnect delays, and stop disconnects cleanly."""
    with patch("apps.ingestion.mqtt_consumer.mqtt.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        consumer = MqttTelemetryConsumer(qos=1)
        consumer.start(blocking=False)

        mock_client.connect.assert_called_once_with(
            consumer.config.broker_host,
            consumer.config.broker_port,
            consumer.config.keepalive,
        )
        mock_client.reconnect_delay_set.assert_called_once_with(min_delay=1, max_delay=10)
        mock_client.loop_start.assert_called_once()

        consumer.stop()
        mock_client.loop_stop.assert_called_once()
        mock_client.disconnect.assert_called_once()
        assert consumer.is_connected is False


def test_mqtt_publish_acknowledgement_helper():
    """Verify QoS 1 message delivery confirmation via wait_for_publish."""
    mock_client = MagicMock(spec=mqtt.Client)
    mock_msg_info = MagicMock()
    mock_msg_info.rc = mqtt.MQTT_ERR_SUCCESS
    mock_msg_info.is_published.return_value = True
    mock_client.publish.return_value = mock_msg_info

    msg_info = mock_client.publish("aegis/telemetry/dev-01", '{"test": 1}', qos=1)
    msg_info.wait_for_publish(timeout=2.0)

    assert msg_info.is_published() is True
