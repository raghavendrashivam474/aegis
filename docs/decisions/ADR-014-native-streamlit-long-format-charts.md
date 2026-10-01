# ADR-014: Native Streamlit Long-Format Time-Series Visualization

## Status
Accepted

## Context
Initial dashboard implementations attempted sparse matrix pivoting of multi-sensor telemetry, creating missing timestamps and rendering artifacts.

## Decision
Utilize Streamlit's native long-format charting (`st.line_chart(df, x="timestamp", y="value", color="sensor_id")`), perfectly matching PostgreSQL's relational schema output.

## Consequences
- Direct, zero-copy visualization from query service records to charts.
- Resilient rendering across dynamic sensor topologies.
