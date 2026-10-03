# P1.S9 — Requirements

| Requirement ID | Name | Description |
|----------------|------|-------------|
| **R-S9-01** | Dataset Source | Aegis shall support ingestion of one selected real-world historical dataset (NASA C-MAPSS FD001). |
| **R-S9-02** | Producer Compatibility | The dataset producer shall emit telemetry through the existing Aegis telemetry boundary. |
| **R-S9-03** | Contract Preservation | Existing telemetry contracts shall remain backward compatible and unchanged. |
| **R-S9-04** | Validation Preservation | Dataset telemetry shall pass through the existing validation/registration mechanisms. |
| **R-S9-05** | Persistence Preservation | Dataset observations shall reach PostgreSQL through the existing persistence boundary. |
| **R-S9-06** | Query Preservation | Dataset observations shall be retrievable through TelemetryQueryService. |
| **R-S9-07** | Dashboard Compatibility | The existing dashboard shall be capable of displaying dataset-derived observations without modification. |
| **R-S9-08** | Provenance | Dataset source and mapping provenance shall be formally documented. |
| **R-S9-09** | Historical Time | Original observation timestamps shall be preserved as event time. |
| **R-S9-10** | Reproducibility | Dataset replay shall be deterministic and reproducible. |
