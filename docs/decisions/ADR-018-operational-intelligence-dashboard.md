# ADR-018: Operational Intelligence Dashboard Architecture

## Status
Accepted (P4.S1)

## Problem Statement
The existing Streamlit dashboard (pps/dashboard/app.py) is a raw telemetry viewer
with hardcoded thresholds and a built-in fake data generator. It does not expose the
Phase 2 intelligence pipeline (health, anomaly, diagnostic, risk) that constitutes
Aegis's core value proposition. Phase 4 requires an operator-facing operational
intelligence interface.

## Existing Implementation Summary
- Single-file Streamlit app with live polling and chart tabs
- Connects to PostgreSQL via TelemetryQueryService (correct boundary)
- Also contains a built-in random data generator (architectural concern)
- Hardcoded threshold checks in UI code (e.g., al > 75.0)
- No integration with HealthAssessmentService, AnomalyDetectionService,
  DiagnosticService, or OperationalRiskService
- No asset overview, no evidence chain, no diagnostic display

## Requirements
- Expose existing intelligence pipeline outputs to operators
- Asset overview with health, anomaly, diagnostic, and risk status
- Asset detail view with evidence-backed findings
- Honest unavailable/error states (no fabricated data)
- Reuse existing domain contracts and services
- Maintain Streamlit presentation layer (low-risk evolution)

## Options Considered

### Option A: Transform Existing Streamlit Dashboard (SELECTED)
- Remove fake data generator and hardcoded thresholds
- Wire intelligence services through query_service.repository
- Add asset overview and detail views
- Preserve existing layout conventions and connection handling
- **Risk**: Low. Single-file change, no new dependencies.

### Option B: Replace with React/TypeScript
- Would require new API layer, build tooling, deployment changes
- No existing requirement justifies the interaction model complexity
- **Risk**: High. 10x scope increase, delays Phase 4 by weeks.
- **Rejected**: No concrete requirement justifies this cost.

### Option C: Hybrid (Streamlit + React)
- Would create two competing dashboards with no clear migration path
- **Rejected**: Violates "do not implement two competing dashboards" principle.

## Decision
**Option A — Transform the existing Streamlit dashboard.**

The existing dashboard already uses TelemetryQueryService correctly and has a solid
Streamlit layout. The gap is intelligence integration, not presentation technology.
Transformation preserves all working infrastructure while adding the required
operational intelligence views.

## Code Impact
- pps/dashboard/app.py: Major rewrite of data flow and views
- No changes to domain contracts, intelligence services, or repository
- No new dependencies (Streamlit, pandas already present)
- No changes to CI/CD or deployment

## Verification Strategy
- Dashboard runs against PostgreSQL with seeded data
- Intelligence outputs match service unit test expectations
- Empty/error states display honestly
- Architecture boundary tests remain green
- No intelligence logic duplicated in UI

## Known Limitations
- Intelligence computed on-demand (not persisted); refresh recomputes
- Requires PostgreSQL with seeded device data for meaningful display
- No real-time push (uses Streamlit polling, consistent with existing design)

## Follow-up Work (P4.S2+)
- Consider caching intelligence results for fleet-scale performance
- Add historical intelligence trend views
- Evaluate whether persistent intelligence storage is needed