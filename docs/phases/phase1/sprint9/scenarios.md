# P1.S9 — Scenarios

## Scenario A — Normal Dataset Record
- **Given:** A valid historical dataset row
- **When:** Passed through the CmapssAdapter
- **Then:** Generates a TelemetryEnvelope that passes ingestion validation and persists in PostgreSQL.

## Scenario B — Invalid Dataset Record
- **Given:** A malformed row or corrupted numeric value
- **When:** Parsed by the adapter
- **Then:** Discarded cleanly at source without impacting system operation.

## Scenario C — Unknown Device Rejection
- **Given:** A dataset envelope referencing an unmapped device ID
- **When:** Ingested by the pipeline
- **Then:** Rejected permanently by DeviceRegistry validation.

## Scenario D — Invalid Sensor Mapping
- **Given:** A dataset observation mapping to an unregistered sensor ID
- **When:** Ingested by the pipeline
- **Then:** Rejected permanently by sensor association validation.

## Scenario E — Timestamp Preservation
- **Given:** An observation with event timestamp T
- **When:** Persisted via the pipeline
- **Then:** Retains the exact historical timestamp T in PostgreSQL, distinct from ingestion wall-clock time.

## Scenario F — End-to-End Replay
- **Given:** A historical C-MAPSS log stream
- **When:** Streamed over MQTT via the Replay Engine
- **Then:** Reaches PostgreSQL, becomes fully queryable through TelemetryQueryService.

## Scenario G — Existing Producers Still Work
- **Given:** Active simulator, ESP32 mock, and C-MAPSS dataset producers running concurrently
- **When:** Pushed to the ingestion pipeline
- **Then:** All three streams ingest, persist, and co-exist cleanly in database tables.
