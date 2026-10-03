# Aegis Datasets

This directory contains real-world datasets used for Aegis telemetry integration.

## Structure

```text
datasets/
├── README.md ← this file
├── cmapss_fd001/
│ ├── manifest.yaml ← provenance, schema, mapping
│ └── train_FD001.txt ← raw data (gitignored)
└── <future-datasets>/
```

## Policy

- **Raw dataset files are NOT committed to Git.**
  They are too large and have their own distribution channels.
- Each dataset subdirectory contains a `manifest.yaml` with
  full provenance, download instructions, and Aegis mapping.
- To reproduce: read the manifest, download from the source URL,
  and place the file in the indicated location.

## Current Datasets

| Dataset | Source | Records | Status |
|---------|--------|---------|--------|
| C-MAPSS FD001 | NASA Prognostics CoE | ~20,631 | Active (P1.S9) |
