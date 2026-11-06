# Watercare asset data product

Water utility asset hierarchy, criticality, maintenance backlog, telemetry and
lineage data product built for Watercare’s Domain Architect — Data role.

## Pain point

Asset data is split across GIS, SCADA, work-order and maintenance systems. The
hard part is a trustworthy asset hierarchy, explainable criticality and a
maintenance backlog that can be defended to operations.

## Formula

- criticality = likelihood (1–5) × consequence (1–5)
- risk = extreme ≥20, high ≥12, medium ≥6, otherwise low
- backlog = open/in-progress/scheduled work orders per asset
- overdue = no maintenance date or older than 365 days
- telemetry = average flow, min/max pressure and reading count

## Verification

- 30 pytest tests.
- SQL gold dimensions, backlog view and telemetry view.
- GitHub Actions CI.

This is a reference implementation, not a live SCADA/GIS integration.
