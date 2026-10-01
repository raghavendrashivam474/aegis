# ADR-015: Additive MQTT Transport Layer

## Status
Accepted

## Context
The introduction of network-based MQTT pub/sub raised the question of whether to deprecate the local file-based JSONL IPC stream.

## Decision
Retain JSONL stream recording as an additive offline ledger and debug fallback (`--reset-stream` / `--live`) alongside the primary MQTT transport.

## Consequences
- Offline development and standalone simulator demos remain fully supported without requiring Docker.
