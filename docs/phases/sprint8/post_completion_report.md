# Aegis Phase 1 — Sprint 8 (P1.S8) Post-Completion Report

**To:** Senior Development Lead, Aegis Core Team
**From:** Junior Development Engineer
**Subject:** Streamlit Cloud Deployment & Hosted Demonstration — Completion Report
**Sprint:** P1.S8
**Baseline Entering Sprint:** `v-P1.S7`
**Status:** ✅ Complete — All four Definition-of-Done gates passed
**Report Date:** October 2026

---

## 1. Executive Summary

Sprint P1.S8 delivered a **publicly deployable, cloud-hosted Aegis operational dashboard** on Streamlit Community Cloud, connected over SSL to a managed remote PostgreSQL instance (Neon Serverless), without modifying any domain contract, application-layer query boundary, or P1.S1–P1.S7 architectural invariant.

The sprint produced an additive deployment target rather than a replacement environment. Local Docker-based development, the P1.S7 hardening path, the `TelemetryQueryService` boundary, and the complete 79-test regression suite remain fully intact and green.

### Key Outcome Summary

| Dimension | Result |
|---|---|
| Hosted deployment target | Streamlit Community Cloud |
| Remote persistence | Neon Serverless PostgreSQL (SSL enforced) |
| Code changes to existing modules | 1 file (`apps/dashboard/app.py`) — surgical configuration resolver only |
| New files added | 5 (requirements, config, secrets gitignore, showcase, ADR, docs) |
| Domain / contract changes | **None** |
| Query boundary bypasses | **None** |
| Test regressions | **None** (79/79 passing, identical to P1.S7 baseline) |
| Secrets in version control | **None** |

---

## 2. Sprint Objective Recap

Per the P1.S8 brief:

> *"Can the Aegis operational interface be reliably deployed and demonstrated remotely while preserving the architecture and behavior already established locally?"*

The sprint explicitly disallowed:
- Rewriting the dashboard
- Bypassing `TelemetryQueryService`
- Replacing or removing Docker Compose
- Modifying telemetry contracts or domain architecture
- Introducing cloud-specific application logic

The sprint required:
- Public hosted dashboard access
- Secure remote-configuration-based database connectivity
- Preservation of local development workflow
- Reproducible deployment procedure

Both constraint sets were honored.

---

## 3. Target Topology Delivered

```
┌────────────────────────────────────────────────────────────────────────┐
│                   LOCAL DEVELOPMENT (Unchanged)                        │
│                                                                        │
│  Docker Compose                                                        │
│   ├── PostgreSQL (localhost:5434)                                      │
│   └── Mosquitto  (localhost:1883)                                      │
│                                                                        │
│  Simulator / ESP32 ─► Ingestion Pipeline ─► Local Postgres             │
│  Local Dashboard  ◄──── TelemetryQueryService ──── Local Postgres      │
│  pytest (79/79)   ◄──── Integration tests against local infra          │
└────────────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────────────┐
│                   HOSTED DEMONSTRATION (New)                           │
│                                                                        │
│  Streamlit Community Cloud                                             │
│   └── apps/dashboard/app.py                                            │
│          │                                                             │
│          ▼  (reads st.secrets["AEGIS_DATABASE_URL"])                   │
│   TelemetryQueryService  ◄──── unchanged application boundary          │
│          │                                                             │
│          ▼  (TLS / sslmode=require)                                    │
│   Neon Serverless PostgreSQL (ap-southeast-1)                          │
│          ▲                                                             │
│          │  (seeded via existing apps.backend.seed_devices)            │
│   Local engineer workstation (one-off seeding and migration)           │
└────────────────────────────────────────────────────────────────────────┘
```

The MQTT broker, ingestion service, and simulator remain outside the hosted dashboard runtime, consistent with brief §15 and §18.

---

## 4. Implementation Breakdown

### 4.1 Feasibility Inspection (First Phase)

Before any code modification, a six-question feasibility audit was executed per brief §11:

| # | Question | Finding |
|---|---|---|
| Q1 | Can the app start in a clean environment? | Yes — `sys.path` resolution in `app.py` is self-contained |
| Q2 | Does it depend on local-only services? | Only via a defaulted env var — no hardcoded coupling |
| Q3 | Does the dashboard need MQTT at runtime? | **No** — zero MQTT imports in `apps/dashboard/app.py` |
| Q4 | Can PG config accept a remote connection? | Yes — standard DSN string, `sslmode` is DSN-parameterized |
| Q5 | Which env vars already support this? | `AEGIS_DATABASE_URL` — already consistent across all consumers |
| Q6 | What actually prevents deployment? | Three small gaps: no `requirements.txt`, no `.streamlit/` scaffolding, no remote DB |

This confirmed the dashboard was **architecturally deployment-ready**. No structural changes were required — only configuration scaffolding and remote infrastructure provisioning.

### 4.2 Changes to Existing Code

**One file modified: `apps/dashboard/app.py`**

The only functional change was the introduction of a tiered database URL resolver that respects Streamlit's native secret management without introducing environment branching logic:

```python
def _resolve_database_url() -> str:
    """Resolve database URL from st.secrets, environment, or default fallback."""
    try:
        if "AEGIS_DATABASE_URL" in st.secrets:
            return str(st.secrets["AEGIS_DATABASE_URL"])
    except Exception:
        pass
    return os.getenv(
        "AEGIS_DATABASE_URL",
        "postgresql://aegis_admin:aegis_password@localhost:5434/aegis_db",
    )


DEFAULT_DB_URL = _resolve_database_url()
```

**Resolution precedence:**
1. `st.secrets["AEGIS_DATABASE_URL"]` — Streamlit Cloud production
2. `os.getenv("AEGIS_DATABASE_URL")` — Local development, CI, env-based overrides
3. Local Docker default DSN — Offline developer convenience

All downstream UI code, query service invocations, chart rendering, metric cards, and sidebar logic were preserved verbatim. The emoji glyphs in the sidebar were also normalized to proper UTF-8 as a side benefit, correcting latent mojibake from the P1.S6 commit.

### 4.3 New Files Created

| File | Purpose |
|---|---|
| `requirements.txt` | Minimal Streamlit Cloud dependency manifest: `streamlit`, `pandas`, `psycopg[binary,pool]` |
| `.streamlit/config.toml` | Headless server mode + Aegis dark operational theme |
| `.streamlit/secrets.toml` | **gitignored** — local test harness for Streamlit secret resolution |
| `.gitignore` (updated) | Added `.streamlit/secrets.toml` exclusion rule |
| `scripts/showcase_p1_s8.py` | 4-gate deployment verification harness |
| `docs/decisions/ADR-017-hosted-deployment-and-secret-configuration.md` | Architectural rationale per brief §27 |
| `docs/phases/sprint8/requirements.md` | REQ-S8-01 through REQ-S8-07 traceability matrix |
| `docs/phases/sprint8/deployment.md` | Reproducible deployment runbook |
| `docs/phases/sprint8/scenarios.md` | Scenario-based verification evidence |
| `docs/phases/sprint8/post_completion_report.md` | Short-form internal report |

### 4.4 Remote Infrastructure Provisioned

A Neon Serverless PostgreSQL instance (`ap-southeast-1`) was provisioned on the free tier. The existing, unmodified Aegis migration path (`apps.backend.migrations`) was executed against the remote DSN:

```
INFO: Applying database migrations on ep-spring-night-...neon.tech/neondb?sslmode=require
INFO: Database migrations applied successfully.
INFO: Registered device 'device-motor-01' with 4 sensors.
INFO: Registered device 'device-motor-02' with 4 sensors.
INFO: Registered device 'device-esp32-01' with 3 sensors.
INFO: Registered device 'device-esp32-99' with 1 sensors.
```

The idempotent `CREATE TABLE IF NOT EXISTS` schema and `ON CONFLICT DO UPDATE` upserts worked identically against Neon as against local Postgres — a direct benefit of the P1.S5 persistence architecture.

A one-off demonstration seed of 880 realistic timeseries observations (80 points × 11 sensors across temperature, pressure, vibration, humidity) was written to the remote database through the standard `PostgresTelemetryRepository.save_batch()` interface — **no raw SQL, no custom cloud-specific adapter**.

---

## 5. Problems Encountered & Resolutions

### 5.1 Problem — Integration Tests Failed After Setting Remote DSN

**Symptom:** Two tests in `tests/test_s5_integration.py` and `tests/test_s6_unified_world.py` began failing after setting `$env:AEGIS_DATABASE_URL` to the remote Neon URL for seeding.

```
FAILED tests/test_s5_integration.py::test_tc_s5_27_end_to_end_mqtt_to_postgres_delivery
FAILED tests/test_s6_unified_world.py::test_fr_s6_01_unified_producer_flow
```

**Root cause:** Both tests inherit `DB_URL` from the ambient `AEGIS_DATABASE_URL` environment variable (lines 31 and 26 respectively). The MQTT consumer thread assertions assume sub-second Postgres roundtrips consistent with local Docker. The ~200ms internet latency to Neon caused `time.sleep(1.0)` windows to expire before persistence commits were visible to the subsequent `repo.get_observations()` assertion.

**Mitigation:** No code change required. The environment variable was reset for test execution:
```
$env:AEGIS_DATABASE_URL = "postgresql://aegis_admin:aegis_password@localhost:5434/aegis_db"
```
All 79 tests then passed in 6.57 seconds. The incident validated a deliberate architectural decision — **integration tests must remain local for determinism**. This is captured in ADR-017.

**Lesson documented:** The ADR explicitly states that running `pytest` against the cloud database would also risk corrupting demonstration data via test teardown fixtures.

### 5.2 Problem — `QualityFlag.SUSPECT` Attribute Error During Seeding

**Symptom:** First seeding attempt failed with:
```
AttributeError: type object 'QualityFlag' has no attribute 'SUSPECT'
```

**Root cause:** I assumed the enum included a `SUSPECT` member. Inspection of `packages/domain/entities.py` showed the actual members are `GOOD`, `UNCERTAIN`, `BAD`, and `CALIBRATION`.

**Mitigation:** Corrected the seed script to use `QualityFlag.UNCERTAIN`. This reinforced the brief's principle (§10) of **always inspecting authoritative sources before assuming behavior**.

### 5.3 Problem — `.streamlit/config.toml` UTF-8 BOM Parse Failure

**Symptom:** Streamlit failed to start locally:
```
toml.decoder.TomlDecodeError: Found invalid character in key name: '['.
```

**Root cause:** PowerShell's `Out-File -Encoding utf8` emits a UTF-8 **Byte Order Mark** (`EF BB BF`) at the start of files. The `toml` parser does not tolerate a BOM before the first `[section]` header.

**Mitigation:** Rewrote the file using Python's `open(..., encoding='utf-8')`, which produces clean BOM-free UTF-8 by default. The problem never surfaces on Linux-based Streamlit Cloud runners, but it would have blocked any Windows-based reviewer from running the dashboard locally.

**Preventive action:** All subsequent file writes in the sprint used Python-based writers rather than `Out-File` to avoid encoding regressions.

### 5.4 Problem — Port 8501 Blocked by Zombie Streamlit Process

**Symptom:** `Port 8501 is not available` after a prior Streamlit instance did not release the port on `Ctrl+C`.

**Root cause:** Streamlit's `uvicorn` runtime occasionally retains a half-closed listener on Windows.

**Mitigation:** Used `Get-NetTCPConnection -LocalPort 8501` + `Stop-Process -Force` to clean up. Documented as an environmental note; no architectural implication.

### 5.5 Problem — `psycopg_pool.ConnectionPool.__del__` Garbage-Collection Warning

**Symptom:** During the full test suite run, a non-fatal `PytestUnraisableExceptionWarning` surfaced from `ConnectionPool.__del__`:
```
RuntimeError: cannot join current thread
```

**Root cause:** A connection pool was being garbage-collected during interpreter shutdown; `__del__` cannot join its own worker threads at that stage. This originates from the P1.S7 pooling implementation and is unrelated to S8.

**Mitigation:** No action taken — the warning is advisory, all 79 tests still pass, and modifying P1.S7 hardening logic merely to silence the warning would violate brief §27 ("Do not undo P1.S7 mechanisms"). Logged as a candidate micro-cleanup for a future hardening sprint.

### 5.6 Problem — Ruff Lint Violations in Initial Showcase Script

**Symptom:** First-draft `scripts/showcase_p1_s8.py` failed `ruff check .`:
- `E402` — module-level import after `sys.path` manipulation
- `UP015` — unnecessary `"r"` mode on `open()` calls
- `E501` — one line exceeded 100 characters

**Mitigation:** Added `# ruff: noqa: E402` (consistent with the existing pattern used in `apps/dashboard/app.py` and `apps/ingestion/mqtt_consumer.py`), removed redundant `"r"` arguments, and broke the long `print(...)` across two f-string fragments. Final `ruff check .` output: `All checks passed!`

### 5.7 Problem — Ruff Formatter Panic on First Run

**Symptom:** `ruff format --check .` crashed with:
```
thread 'main' panicked at crates\ruff_annotate_snippets\src\renderer\source_map.rs:185:13:
Annotation range `0..8705` is beyond the end of buffer `8703`
```

**Root cause:** Mixed CRLF/LF line endings in files written via PowerShell `@"..."@` here-strings and `Out-File`. The byte offset calculated with CRLF-expanded assumptions overran the LF-normalized buffer.

**Mitigation:** Ran `ruff format .` (without `--check`), which rewrote the two offending files with consistent line endings. Subsequent `ruff format --check .` returned `92 files already formatted`.

---

## 6. Architectural Decisions

### ADR-017 — Hosted Deployment & Secret Configuration

The complete rationale is captured in `docs/decisions/ADR-017-hosted-deployment-and-secret-configuration.md`. The key architectural choices:

1. **Tiered secret resolver over environment branching** — The dashboard does not know or care *which* platform it runs on. It resolves a DSN. This preserves the brief's §17 directive: *"Avoid `if STREAMLIT_CLOUD: ...` branching."*

2. **Dashboard remains a read-only consumer** — The hosted dashboard does not ingest, publish, or validate. It queries. This preserves the brief's §18 directive: *"Do not automatically connect Streamlit Cloud directly to Mosquitto."*

3. **Local tests continue to run against local Docker** — Integration tests are not re-pointed at remote infrastructure. This preserves determinism, protects demo data, and preserves offline development per brief §28.

4. **Deployment is additive, not replacing** — Docker Compose, Mosquitto, the ingestion service, and the simulator remain exactly as they were in P1.S7. The cloud deployment is a new target, not a migration.

---

## 7. Definition-of-Done Verification

### Gate 1 — Working Capability ✅
A reviewer with the Streamlit Cloud URL can open the Aegis dashboard in a browser and interact with the operational interface. The dashboard displays live metric cards and multi-tab charts for Temperature, Vibration, Pressure, and Humidity across 11 sensors on 3 active devices.

### Gate 2 — Verification ✅

**Local test suite (local Docker baseline):**
```
79 passed, 1 warning in 6.57s
```

**Ruff lint:** `All checks passed!`
**Ruff format:** `92 files already formatted`

**Showcase script output (both local Docker and remote Neon reachable):**
```
======================================================================
  AEGIS P1.S8 — HOSTED STREAMLIT CLOUD DEPLOYMENT SHOWCASE
======================================================================

[1/4] Checking Streamlit Cloud Scaffolding...
  ✓ requirements.txt declared (isolated dependencies)
  ✓ apps/dashboard/app.py validated as clean entrypoint
  ✓ .gitignore safeguards .streamlit/secrets.toml and .env

[2/4] Verifying Architecture & Query Boundary Compliance...
  ✓ Zero direct SQL in presentation layer
  ✓ Dashboard strictly consumes TelemetryQueryService and PostgresDeviceRegistry

[3/4] Verifying Local Docker PostgreSQL Pipeline...
  ✓ Local Docker DB reachable: 4 registered devices found

[4/4] Verifying Remote Cloud PostgreSQL Connection...
  ✓ Remote DB connected successfully!
  ✓ Registered devices: 4
    - device-motor-01 (Motor-01): 3 sample observations retrieved
    - device-motor-02 (Motor-02): 3 sample observations retrieved
    - device-esp32-01 (Physical ESP32 Edge Node 01): 3 sample observations retrieved
    - device-esp32-99 (Ingestion Test Node 99): 0 sample observations retrieved

======================================================================
  AEGIS P1.S8 HOSTED DEPLOYMENT VERIFICATION COMPLETE — ALL GATES PASS
======================================================================
```

**Cloud-independence verification (local Docker explicitly shut down):**
With `docker compose down` executed, the showcase correctly reported `Local DB Check skipped or failed` while the remote Neon connectivity gate continued passing — proving the hosted deployment has **zero runtime dependency on the local development environment**.

### Gate 3 — Concrete Showcase ✅
A mentor can be handed the Streamlit Cloud URL alone. No local Docker, no local Python environment, no MQTT broker, and no additional orchestration is required on the reviewer's machine. The hosted dashboard is self-sufficient.

### Gate 4 — Documentation ✅
Delivered:
- ADR-017 (architectural rationale)
- `docs/phases/sprint8/requirements.md` (requirement traceability)
- `docs/phases/sprint8/deployment.md` (reproducible runbook)
- `docs/phases/sprint8/scenarios.md` (verification matrix)
- `docs/phases/sprint8/post_completion_report.md` (short-form report)
- This long-form report

---

## 8. What Was Explicitly NOT Done (Per Brief §28)

The following were deliberately **not** attempted, in strict accordance with the brief:

- ❌ Rewrite of the dashboard
- ❌ Creation of a second cloud-specific dashboard
- ❌ Bypassing `TelemetryQueryService`
- ❌ Any SQL placed directly in Streamlit
- ❌ Exposure of PostgreSQL credentials in source
- ❌ Commits of `.streamlit/secrets.toml` or `.env`
- ❌ Replacement or removal of Docker Compose
- ❌ Removal of Mosquitto or the simulator
- ❌ Modification of telemetry contracts or domain architecture
- ❌ Changes to P1.S7 hardening behavior
- ❌ Introduction of real-world dataset ingestion (reserved for P1.S9)
- ❌ Microservices, Kubernetes, or cloud orchestration layers
- ❌ Disabling or skipping any test to make deployment pass

---

## 9. Known Limitations

1. **Live telemetry ingestion to the cloud dashboard requires one of two options**:
   - Pointing a locally running `apps.ingestion` process at the remote Neon DSN, or
   - Running an edge adapter against an internet-reachable persistence endpoint

   For P1.S8, the hosted dashboard displays **persistent historical telemetry seeded from a one-off local run**. Continuous real-time streaming to the cloud is architecturally supported but operationally out of scope for this sprint.

2. **Neon Serverless free tier auto-suspends** idle instances after inactivity. The first dashboard load after a long idle period incurs ~1–2 seconds of cold-start latency as the compute instance resumes. This is a Neon operational characteristic, not an Aegis architectural issue.

3. **Integration tests are local-only by design**. See §5.1 and ADR-017.

---

## 10. P1.S9 Handoff Readiness

Sprint P1.S8 leaves the Aegis platform cleanly positioned for **P1.S9 — Real-World Dataset Integration**:

- The hosted dashboard is already consuming the existing `TelemetryQueryService` boundary.
- A real dataset producer introduced in S9 will flow through the same unmodified MQTT → ingestion → persistence pipeline.
- The dataset's observations will appear in the hosted dashboard automatically once persisted — no additional cloud deployment work will be required.
- The telemetry contracts, domain model, device registry, and ingestion pipeline are untouched and ready to receive new producer sources.

---

## 11. Final Baseline

| Baseline | P1.S7 | P1.S8 | Delta |
|---|---|---|---|
| Tests | 79 passing | 79 passing | 0 |
| Ruff lint | Clean | Clean | 0 |
| Ruff format | Clean | Clean | 0 |
| Domain contracts | Stable | Stable | 0 |
| Query boundary | Enforced | Enforced | 0 |
| Local Docker workflow | Working | Working | 0 |
| ADRs | 16 | 17 | +1 |
| Deployment targets | Local only | Local + Streamlit Cloud | +1 |

---

## 12. Closing Statement

Sprint P1.S8 was executed under the governing principle:

> *"Deploy the Aegis we have built. Do not build a different Aegis just because it is being deployed."*

The architectural, security, and testing invariants protected across P1.S1–P1.S7 are intact. The deployment is additive, reproducible, and documented. The hosted dashboard is reachable, operational, and demonstrably decoupled from the local development environment.

The platform is ready for senior review and for P1.S9 handoff.

**— Submitted for review.**