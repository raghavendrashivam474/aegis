# P1.S9 — Mapping Specification

The C-MAPSS FD001 dataset columns are mapped directly into Aegis telemetry payloads as follows:

- **unit_number** → device_id (dynamically formatted as engine-XXX)
- **time_in_cycles** → observation.timestamp (Deterministic 1-minute increments starting from 2026-01-01T00:00:00Z)
- **sensor_1 to sensor_21** → Mapped to scoped sensor IDs under engine-XXX using physical models:
  - sensor-t2-inlet-engine-XXX (Temperature, K)
  - sensor-t24-lpc-engine-XXX (Temperature, K)
  - sensor-t30-hpc-engine-XXX (Temperature, K)
  - sensor-t50-lpt-engine-XXX (Temperature, K)
  - sensor-p2-inlet-engine-XXX (Pressure, psi)
  - sensor-p15-bypass-engine-XXX (Pressure, psi)
  - sensor-p30-hpc-engine-XXX (Pressure, psi)
  - sensor-nf-fan-engine-XXX (Rotational Speed, rpm)
  - sensor-nc-core-engine-XXX (Rotational Speed, rpm)
  - sensor-epr-engine-XXX (Engine Pressure Ratio, ratio)
  - sensor-ps30-engine-XXX (Static Pressure, psi)
  - sensor-phi-engine-XXX (Fuel Flow Ratio, ratio)
  - sensor-nrf-engine-XXX (Corrected Fan Speed, rpm)
  - sensor-nrc-engine-XXX (Corrected Core Speed, rpm)
  - sensor-bpr-engine-XXX (Bypass Ratio, ratio)
  - sensor-farb-engine-XXX (Burner Fuel-Air Ratio, ratio)
  - sensor-htbleed-engine-XXX (Bleed Enthalpy, kJ/kg)
  - sensor-nf-dmd-engine-XXX (Demanded Fan Speed, rpm)
  - sensor-pcnfr-dmd-engine-XXX (Demanded Corrected Fan Speed, rpm)
  - sensor-w31-engine-XXX (Coolant Flow, lbm/s)
  - sensor-w32-engine-XXX (Coolant Flow, lbm/s)
