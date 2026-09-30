# Aegis Digital Asset Simulator (pps/simulator)

Independent simulation application that models industrial world topologies, applies multi-dimensional physical sensor dynamics (Ornstein-Uhlenbeck processes, rotational harmonics, fluid pulsation), validates domain invariants, and emits TelemetryEnvelope (v1) contract streams.

## Quick Start

Run infinite continuous simulation:
\\powershell
python -m apps.simulator --scenario degradation --interval 0.5
\
Run a fixed batch (e.g. 50 ticks):
\\powershell
python -m apps.simulator --ticks 50 --interval 0.5 --scenario normal
\
For detailed architecture and scenario documentation, see docs/phases/sprint3/README.md.
