# ADR-017: Cloud-Neutral Persistence Configuration and Hosted Deployment Topology

## Status
Accepted (P1.S8)

## Context
Aegis required a publicly accessible deployment of its operational telemetry dashboard on Streamlit Cloud to facilitate remote demonstration and stakeholder review. 

The application was previously developed against local Docker services (PostgreSQL on port 5434 and Mosquitto MQTT broker on port 1883). Moving to a hosted environment introduced constraints:
1. Streamlit Cloud is an application runtime environment, not a multi-container host. Docker Compose and Mosquitto cannot run inside the Streamlit container.
2. Hardcoded local connection strings or environment-only configuration would break Streamlit Cloud's native secret management (`st.secrets`).
3. Local development workflows, unit test suites (79 passing tests), and offline Docker Compose infrastructure had to remain completely unharmed.
4. The dashboard must strictly respect the `TelemetryQueryService` application boundary and avoid embedding raw SQL queries.

## Decision
1. **Tiered Configuration Resolver**:
   Implemented `_resolve_database_url()` in `apps/dashboard/app.py` with hierarchical fallback:
   - Priority 1: `st.secrets["AEGIS_DATABASE_URL"]` (Streamlit Cloud production secrets)
   - Priority 2: `os.getenv("AEGIS_DATABASE_URL")` (Local development / CI overrides)
   - Priority 3: `postgresql://aegis_admin:aegis_password@localhost:5434/aegis_db` (Local Docker default)

2. **Hosted Persistence Topology**:
   Provisioned a remote PostgreSQL instance (Neon Serverless PostgreSQL with SSL enforced). The remote instance executes the standard, idempotent Aegis schema migrations (`apps.backend.migrations`) and device registry seed profiles (`apps.backend.seed_devices`).

3. **Presentation & Transport Decoupling**:
   Confirmed that the operational dashboard is purely a telemetry and world model consumer that interacts solely with `TelemetryQueryService` and `PostgresDeviceRegistry`. MQTT brokers and ingestion runners remain transport/edge concerns and are not exposed directly to Streamlit Cloud.

4. **Secret Isolation**:
   Excluded `.streamlit/secrets.toml` and `.env` in `.gitignore`. Committed an isolated `requirements.txt` declaring only runtime dashboard dependencies (`streamlit`, `pandas`, `psycopg[binary,pool]`).

## Consequences
### Positive
- The dashboard is deployable to Streamlit Cloud with zero architectural drift or code duplication.
- Local development via `docker compose up` remains 100% intact.
- Strict isolation of database credentials prevents secret leakage to version control.
- All 79 existing tests pass without modification.

### Negative / Limitations
- Live streaming from an edge device to the cloud dashboard requires either pointing the local ingestion service to the remote database URL or running edge adapters against an internet-accessible persistence endpoint.
