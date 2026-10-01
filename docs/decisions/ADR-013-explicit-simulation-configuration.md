# ADR-013: Explicit Simulation Configuration Flags

## Status
Accepted

## Context
During P1.S6, implicit environment variables (`AEGIS_SIM_HUMIDITY`, etc.) caused accidental cross-test state bleed and non-deterministic fixture behavior.

## Decision
All simulator behavior variants (such as `include_humidity` and `use_wall_clock`) are declared as explicit, strongly-typed fields on `SimulationConfig` rather than hidden global environment state.

## Consequences
- 100% deterministic unit and integration test fixtures.
- Zero test pollution across execution runs.
