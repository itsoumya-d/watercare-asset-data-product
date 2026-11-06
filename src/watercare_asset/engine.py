from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import date
from typing import Iterable, Mapping, Sequence


@dataclass(frozen=True)
class Asset:
    asset_id: str
    parent_id: str | None
    asset_type: str
    criticality_likelihood: int
    criticality_consequence: int
    status: str = "active"
    last_maintenance: date | None = None


@dataclass(frozen=True)
class WorkOrder:
    work_order_id: str
    asset_id: str
    priority: int
    status: str
    created: date
    completed: date | None = None


@dataclass(frozen=True)
class Telemetry:
    asset_id: str
    observed: date
    flow_lps: float
    pressure_kpa: float


def validate_hierarchy(assets: Sequence[Asset]) -> list[str]:
    issues: list[str] = []
    by_id = {asset.asset_id: asset for asset in assets}
    if len(by_id) != len(assets):
        issues.append("duplicate_asset_id")
    for asset in assets:
        if asset.parent_id and asset.parent_id not in by_id:
            issues.append(f"orphan:{asset.asset_id}->{asset.parent_id}")
        if asset.parent_id == asset.asset_id:
            issues.append(f"self_parent:{asset.asset_id}")
    for asset in assets:
        seen = {asset.asset_id}
        current = asset.parent_id
        while current:
            if current in seen:
                issues.append(f"cycle:{asset.asset_id}")
                break
            seen.add(current)
            current = by_id.get(current).parent_id if by_id.get(current) else None
    return sorted(set(issues))


def children_index(assets: Sequence[Asset]) -> dict[str | None, list[str]]:
    index: dict[str | None, list[str]] = defaultdict(list)
    for asset in assets:
        index[asset.parent_id].append(asset.asset_id)
    return {parent: sorted(children) for parent, children in index.items()}


def descendants(assets: Sequence[Asset], root_id: str) -> list[str]:
    index = children_index(assets)
    out: list[str] = []
    queue = deque(index.get(root_id, []))
    while queue:
        current = queue.popleft()
        out.append(current)
        queue.extend(index.get(current, []))
    return out


def criticality_score(asset: Asset) -> int:
    likelihood = max(1, min(5, asset.criticality_likelihood))
    consequence = max(1, min(5, asset.criticality_consequence))
    return likelihood * consequence


def risk_band(score: int) -> str:
    if score >= 20:
        return "extreme"
    if score >= 12:
        return "high"
    if score >= 6:
        return "medium"
    return "low"


def maintenance_backlog(assets: Sequence[Asset], orders: Sequence[WorkOrder]) -> dict[str, int]:
    by_asset = {asset.asset_id: asset for asset in assets}
    backlog: dict[str, int] = defaultdict(int)
    for order in orders:
        if order.status.lower() in {"open", "in_progress", "scheduled"} and order.asset_id in by_asset:
            backlog[order.asset_id] += 1
    return dict(sorted(backlog.items()))


def overdue_assets(assets: Sequence[Asset], as_of: date, days: int = 365) -> list[str]:
    out = []
    for asset in assets:
        if asset.last_maintenance is None or (as_of - asset.last_maintenance).days > days:
            out.append(asset.asset_id)
    return sorted(out)


def telemetry_summary(rows: Sequence[Telemetry]) -> dict[str, dict[str, float]]:
    grouped: dict[str, list[Telemetry]] = defaultdict(list)
    for row in rows:
        grouped[row.asset_id].append(row)
    out = {}
    for asset_id, values in grouped.items():
        out[asset_id] = {
            "avg_flow_lps": round(sum(v.flow_lps for v in values) / len(values), 2),
            "max_pressure_kpa": round(max(v.pressure_kpa for v in values), 2),
            "min_pressure_kpa": round(min(v.pressure_kpa for v in values), 2),
            "readings": float(len(values)),
        }
    return dict(sorted(out.items()))


def lineage_edges() -> list[tuple[str, str]]:
    return [
        ("source.gis_assets", "bronze.assets"),
        ("source.work_orders", "bronze.work_orders"),
        ("source.scada_telemetry", "bronze.telemetry"),
        ("bronze.assets", "silver.asset_hierarchy"),
        ("bronze.work_orders", "silver.maintenance"),
        ("bronze.telemetry", "silver.telemetry"),
        ("silver.asset_hierarchy", "gold.dim_asset"),
        ("silver.maintenance", "gold.fct_maintenance"),
        ("silver.telemetry", "gold.fct_asset_telemetry"),
    ]


def asset_portfolio(assets: Sequence[Asset], orders: Sequence[WorkOrder]) -> dict[str, object]:
    scores = {asset.asset_id: criticality_score(asset) for asset in assets}
    bands = defaultdict(int)
    for score in scores.values():
        bands[risk_band(score)] += 1
    backlog = maintenance_backlog(assets, orders)
    return {
        "assets": len(assets),
        "risk_bands": dict(sorted(bands.items())),
        "backlog_assets": len(backlog),
        "open_work_orders": sum(backlog.values()),
        "top_risk": sorted(scores.items(), key=lambda item: item[1], reverse=True)[:5],
    }
