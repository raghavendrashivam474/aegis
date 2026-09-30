# Aegis Telemetry Dashboard (pps/dashboard)

Streamlit-based live telemetry subscriber UI that reads deserialized TelemetryEnvelope contracts from the IPC stream file (data/telemetry_stream.jsonl).

## Quick Start

Launch the dashboard:
\\powershell
streamlit run apps/dashboard/app.py
\
For detailed architecture and Producer/Consumer stream docs, see docs/phases/sprint3/README.md.
