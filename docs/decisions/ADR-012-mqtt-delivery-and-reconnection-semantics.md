# ADR-012: MQTT Delivery & Reconnection Semantics

## Status
Accepted

## Context
In P1.S6, MQTT publishers utilized fire-and-forget publishing (QoS 0) followed by artificial sleep delays (`time.sleep(1.5)`) prior to script teardown to give the underlying network loop time to flush.
Furthermore, consumer subscription was unacknowledged with undefined broker reconnection semantics.

## Decision
1. Standardize ingestion topic subscription on **QoS 1 (At-Least-Once Delivery)**.
2. Upgrade publisher scripts (`simulator`, `mock_esp32_publisher`) to publish at QoS 1 and track `MQTTMessageInfo.wait_for_publish(timeout)` rather than arbitrary sleeps.
3. Configure consumer with automatic exponential reconnect delay (`min_delay=1s`, `max_delay=10s`).
4. Trigger opportunistic buffer draining (`pipeline.drain_buffer()`) upon MQTT reconnection to synchronize any pending backlog.

## Consequences
### Positive
- Guarantees at-least-once message delivery over lossy network links.
- Removes race conditions and artificial sleep delays from publisher teardown.
- Seamless automatic recovery during transient broker restarts.

### Negative / Trade-offs
- Slight network overhead for PUBACK acknowledgments in high-frequency bursts (negligible for target telemetry rates).
