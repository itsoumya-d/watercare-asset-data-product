from datetime import date

from watercare_asset.engine import (
    Asset,
    Telemetry,
    WorkOrder,
    asset_portfolio,
    children_index,
    criticality_score,
    descendants,
    lineage_edges,
    maintenance_backlog,
    overdue_assets,
    risk_band,
    telemetry_summary,
    validate_hierarchy,
)

A = Asset("A1", None, "network", 4, 5)
B = Asset("B1", "A1", "pump_station", 3, 4, last_maintenance=date(2025, 1, 1))
C = Asset("C1", "B1", "pump", 2, 3, last_maintenance=date(2026, 10, 1))
D = Asset("D1", "A1", "treatment_plant", 5, 5)


def test_valid_hierarchy():
    assert validate_hierarchy([A, B, C, D]) == []


def test_orphan():
    assert any("orphan" in issue for issue in validate_hierarchy([B]))


def test_self_parent():
    assert "self_parent:A1" in validate_hierarchy([Asset("A1", "A1", "x", 1, 1)])


def test_cycle():
    a = Asset("A", "B", "x", 1, 1)
    b = Asset("B", "A", "x", 1, 1)
    assert "cycle:A" in validate_hierarchy([a, b])


def test_duplicate_id():
    assert "duplicate_asset_id" in validate_hierarchy([A, A])


def test_children_index():
    assert children_index([A, B, C, D])["A1"] == ["B1", "D1"]


def test_descendants():
    assert descendants([A, B, C, D], "A1") == ["B1", "D1", "C1"]


def test_descendants_leaf():
    assert descendants([A, B, C, D], "C1") == []


def test_criticality_score():
    assert criticality_score(A) == 20


def test_criticality_clamps_low():
    assert criticality_score(Asset("x", None, "x", 0, 0)) == 1


def test_criticality_clamps_high():
    assert criticality_score(Asset("x", None, "x", 9, 9)) == 25


def test_risk_extreme():
    assert risk_band(20) == "extreme"


def test_risk_high():
    assert risk_band(12) == "high"


def test_risk_medium():
    assert risk_band(6) == "medium"


def test_risk_low():
    assert risk_band(1) == "low"


def test_backlog():
    orders = [WorkOrder("W1", "A1", 1, "open", date(2026, 1, 1)), WorkOrder("W2", "A1", 2, "completed", date(2026, 1, 1), date(2026, 1, 2))]
    assert maintenance_backlog([A], orders) == {"A1": 1}


def test_backlog_unknown_asset_ignored():
    assert maintenance_backlog([A], [WorkOrder("W1", "Z9", 1, "open", date(2026, 1, 1))]) == {}


def test_overdue_missing_date():
    assert overdue_assets([Asset("A", None, "x", 1, 1, last_maintenance=None)], date(2026, 11, 6)) == ["A"]


def test_overdue_old_date():
    assert overdue_assets([B], date(2026, 11, 6)) == ["B1"]


def test_not_overdue():
    assert overdue_assets([C], date(2026, 11, 6)) == []


def test_telemetry_summary():
    rows = [Telemetry("A1", date(2026, 11, 1), 10, 200), Telemetry("A1", date(2026, 11, 2), 30, 300)]
    assert telemetry_summary(rows)["A1"]["avg_flow_lps"] == 20


def test_telemetry_max_pressure():
    rows = [Telemetry("A1", date(2026, 11, 1), 10, 200), Telemetry("A1", date(2026, 11, 2), 30, 300)]
    assert telemetry_summary(rows)["A1"]["max_pressure_kpa"] == 300


def test_telemetry_count():
    assert telemetry_summary([Telemetry("A1", date(2026, 11, 1), 10, 200)])["A1"]["readings"] == 1


def test_telemetry_empty():
    assert telemetry_summary([]) == {}


def test_lineage_edges():
    assert ("silver.asset_hierarchy", "gold.dim_asset") in lineage_edges()


def test_lineage_count():
    assert len(lineage_edges()) == 9


def test_portfolio_assets():
    assert asset_portfolio([A, B, C, D], [])["assets"] == 4


def test_portfolio_risk_band():
    assert asset_portfolio([A, B, C, D], [])["risk_bands"]["extreme"] == 2


def test_portfolio_backlog():
    orders = [WorkOrder("W1", "A1", 1, "open", date(2026, 1, 1))]
    assert asset_portfolio([A], orders)["open_work_orders"] == 1


def test_portfolio_top_risk():
    assert asset_portfolio([A, B, C, D], [])["top_risk"][0][0] in {"A1", "D1"}
