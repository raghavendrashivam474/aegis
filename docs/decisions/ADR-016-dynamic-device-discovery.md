# ADR-016: Dynamic Device Discovery from Registry Boundary

## Status
Accepted

## Context
Hardcoding UI device dropdowns breaks digital twin topology extensibility when new assets or edge devices are provisioned.

## Decision
The presentation tier discovers active devices dynamically by calling `PostgresDeviceRegistry.list_devices()` or querying distinct active identifiers through `TelemetryQueryService`.

## Consequences
- Zero frontend code changes required when provisioning new edge devices or physical sensors.
