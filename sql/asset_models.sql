CREATE OR REPLACE TABLE gold.dim_asset AS
SELECT
    a.asset_id,
    a.parent_id,
    a.asset_type,
    a.status,
    a.last_maintenance,
    a.criticality_likelihood * a.criticality_consequence AS criticality_score,
    CASE
        WHEN a.criticality_likelihood * a.criticality_consequence >= 20 THEN 'extreme'
        WHEN a.criticality_likelihood * a.criticality_consequence >= 12 THEN 'high'
        WHEN a.criticality_likelihood * a.criticality_consequence >= 6 THEN 'medium'
        ELSE 'low'
    END AS risk_band
FROM silver.asset_hierarchy a;

CREATE OR REPLACE VIEW gold.vw_maintenance_backlog AS
SELECT
    a.asset_id,
    a.asset_type,
    a.risk_band,
    count(w.work_order_id) AS open_work_orders
FROM gold.dim_asset a
LEFT JOIN silver.maintenance w
  ON w.asset_id = a.asset_id AND w.status IN ('open', 'in_progress', 'scheduled')
GROUP BY a.asset_id, a.asset_type, a.risk_band;

CREATE OR REPLACE VIEW gold.vw_asset_telemetry AS
SELECT
    t.asset_id,
    avg(t.flow_lps) AS avg_flow_lps,
    max(t.pressure_kpa) AS max_pressure_kpa,
    min(t.pressure_kpa) AS min_pressure_kpa,
    count(*) AS readings
FROM silver.telemetry t
GROUP BY t.asset_id;
