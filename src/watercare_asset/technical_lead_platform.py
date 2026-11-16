"""Watercare Services Data & Analytics Technical Lead Platform.

Enterprise semantic layer, automated data assurance gates, Snowflake/dbt dimensional models,
and Taumata Arowai (Drinking Water Quality Standards) statutory compliance governance.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Sequence, Tuple


class WaterQualityStatus(str, Enum):
    COMPLIANT = "compliant"
    WARNING = "warning"
    BREACH = "breach"


class RiskClassification(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass(frozen=True)
class WaterQualityObservation:
    """Drinking water quality sensor reading across Auckland treatment/distribution networks."""
    sample_id: str
    zone_id: str
    observed_at: datetime
    turbidity_ntu: float         # Statutory threshold: <= 0.50 NTU (Taumata Arowai rule)
    free_available_chlorine_ppm: float  # Statutory threshold: 0.20 - 5.00 mg/L
    ph_level: float              # Optimal range: 6.5 - 8.5
    e_coli_cfu_per_100ml: int    # Statutory threshold: 0 CFU/100mL


@dataclass(frozen=True)
class DistrictMeteredAreaTelemetry:
    """DMA flow, pressure, and acoustic sensor telemetry for NRW leak detection."""
    dma_id: str
    timestamp: datetime
    inflow_lps: float            # Litres per second entering DMA
    outflow_lps: float           # Metered consumption leaving DMA
    average_pressure_kpa: float  # Distribution network pressure in kilopascals
    minimum_night_flow_lps: float # Key indicator of burst/unreported leaks


@dataclass
class QualityAssuranceReport:
    total_samples: int
    compliant_samples: int
    warning_samples: int
    breach_samples: int
    compliance_rate_pct: float
    breach_sample_ids: List[str] = field(default_factory=list)
    alerts: List[str] = field(default_factory=list)


class TaumataArowaiComplianceEngine:
    """New Zealand Water Services Act 2021 & Taumata Arowai Compliance Validator."""

    TURBIDITY_LIMIT_NTU = 0.50
    FAC_MIN_PPM = 0.20
    FAC_MAX_PPM = 5.00
    PH_MIN = 6.5
    PH_MAX = 8.5
    E_COLI_MAX = 0

    def evaluate_sample(self, sample: WaterQualityObservation) -> Tuple[WaterQualityStatus, List[str]]:
        reasons = []
        is_breach = False
        is_warning = False

        # 1. E. coli check (Immediate statutory breach)
        if sample.e_coli_cfu_per_100ml > self.E_COLI_MAX:
            is_breach = True
            reasons.append(f"E. coli detected: {sample.e_coli_cfu_per_100ml} CFU/100mL (statutory limit 0)")

        # 2. Turbidity check
        if sample.turbidity_ntu > self.TURBIDITY_LIMIT_NTU:
            is_breach = True
            reasons.append(f"Turbidity {sample.turbidity_ntu:.2f} NTU exceeds limit {self.TURBIDITY_LIMIT_NTU:.2f} NTU")
        elif sample.turbidity_ntu > (self.TURBIDITY_LIMIT_NTU * 0.85):
            is_warning = True
            reasons.append(f"Turbidity {sample.turbidity_ntu:.2f} NTU approaching statutory limit")

        # 3. Chlorine residual check
        if sample.free_available_chlorine_ppm < self.FAC_MIN_PPM:
            is_breach = True
            reasons.append(f"Chlorine {sample.free_available_chlorine_ppm:.2f} ppm below disinfection min {self.FAC_MIN_PPM:.2f} ppm")
        elif sample.free_available_chlorine_ppm > self.FAC_MAX_PPM:
            is_breach = True
            reasons.append(f"Chlorine {sample.free_available_chlorine_ppm:.2f} ppm exceeds aesthetic max {self.FAC_MAX_PPM:.2f} ppm")

        # 4. pH check
        if sample.ph_level < self.PH_MIN or sample.ph_level > self.PH_MAX:
            is_warning = True
            reasons.append(f"pH level {sample.ph_level:.2f} outside optimal range [{self.PH_MIN}-{self.PH_MAX}]")

        if is_breach:
            return WaterQualityStatus.BREACH, reasons
        if is_warning:
            return WaterQualityStatus.WARNING, reasons
        return WaterQualityStatus.COMPLIANT, ["All statutory Taumata Arowai parameters verified compliant"]

    def audit_batch(self, samples: Sequence[WaterQualityObservation]) -> QualityAssuranceReport:
        if not samples:
            return QualityAssuranceReport(0, 0, 0, 0, 100.0)

        compliant = 0
        warning = 0
        breach = 0
        breach_ids = []
        alerts = []

        for s in samples:
            status, reasons = self.evaluate_sample(s)
            if status == WaterQualityStatus.COMPLIANT:
                compliant += 1
            elif status == WaterQualityStatus.WARNING:
                warning += 1
                alerts.append(f"Zone {s.zone_id} [{s.sample_id}]: {'; '.join(reasons)}")
            else:
                breach += 1
                breach_ids.append(s.sample_id)
                alerts.append(f"CRITICAL BREACH Zone {s.zone_id} [{s.sample_id}]: {'; '.join(reasons)}")

        rate = round((compliant / len(samples)) * 100.0, 2)
        return QualityAssuranceReport(
            total_samples=len(samples),
            compliant_samples=compliant,
            warning_samples=warning,
            breach_samples=breach,
            compliance_rate_pct=rate,
            breach_sample_ids=breach_ids,
            alerts=alerts
        )


class WatercareSemanticLayer:
    """Watercare Enterprise Semantic Metrics & DMA Leakage Analytics."""

    @staticmethod
    def calculate_non_revenue_water(telemetry: DistrictMeteredAreaTelemetry) -> Dict[str, Any]:
        """Calculates Real vs Apparent loss metrics for Auckland Water distribution."""
        gross_loss_lps = max(0.0, telemetry.inflow_lps - telemetry.outflow_lps)
        loss_pct = round((gross_loss_lps / telemetry.inflow_lps * 100.0), 2) if telemetry.inflow_lps > 0 else 0.0

        # High minimum night flow (> 35% of inflow) indicates active pipe burst or background leakage
        is_leak_suspect = (telemetry.minimum_night_flow_lps / telemetry.inflow_lps > 0.35) if telemetry.inflow_lps > 0 else False
        
        # Hazard risk scoring
        if loss_pct > 25.0 or (is_leak_suspect and telemetry.average_pressure_kpa > 600.0):
            risk = RiskClassification.CRITICAL
        elif loss_pct > 15.0 or is_leak_suspect:
            risk = RiskClassification.HIGH
        elif loss_pct > 8.0:
            risk = RiskClassification.MEDIUM
        else:
            risk = RiskClassification.LOW

        return {
            "dma_id": telemetry.dma_id,
            "inflow_mld": round(telemetry.inflow_lps * 0.0864, 4), # LPS to Megalitres/Day
            "outflow_mld": round(telemetry.outflow_lps * 0.0864, 4),
            "gross_loss_lps": round(gross_loss_lps, 2),
            "loss_pct": loss_pct,
            "minimum_night_flow_ratio": round(telemetry.minimum_night_flow_lps / telemetry.inflow_lps, 3) if telemetry.inflow_lps > 0 else 0.0,
            "is_leak_suspect": is_leak_suspect,
            "risk_classification": risk
        }

    @staticmethod
    def generate_snowflake_dbt_semantic_model() -> str:
        """Returns verified dbt semantic model YAML schema for Watercare Snowflake Lakehouse."""
        return """version: 2
models:
  - name: fct_watercare_dma_analytics
    description: "Gold star-schema mart for Auckland DMA flow, pressure and Non-Revenue Water leakage analytics."
    columns:
      - name: dma_key
        description: "Surrogate key for District Metered Area"
        tests:
          - unique
          - not_null
      - name: observed_date
        description: "Date of telemetry aggregation"
        tests:
          - not_null
      - name: inflow_mld
        description: "Total inflow in Megalitres per day"
      - name: nrw_loss_percentage
        description: "Calculated Non-Revenue Water loss percentage"
      - name: leak_anomaly_flag
        description: "Boolean flag triggered by acoustic telemetry anomaly detection"
"""


class DataAssuranceGate:
    """Pre-Gold validation gate for SCADA ingestion latency, volume deviation, and null safety."""

    def __init__(self, max_allowed_latency_minutes: int = 60, max_null_ratio: float = 0.02):
        self.max_allowed_latency = max_allowed_latency_minutes
        self.max_null_ratio = max_null_ratio

    def validate_ingestion_batch(self, records: Sequence[Dict[str, Any]], current_time: datetime) -> Dict[str, Any]:
        if not records:
            return {"valid": False, "reason": "Empty batch rejected"}

        null_counts: Dict[str, int] = {}
        max_latency_found = 0.0

        for r in records:
            for k, v in r.items():
                if v is None:
                    null_counts[k] = null_counts.get(k, 0) + 1
            
            ts = r.get("timestamp") or r.get("observed_at")
            if isinstance(ts, datetime):
                # Normalize timezones
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                curr = current_time if current_time.tzinfo else current_time.replace(tzinfo=timezone.utc)
                latency_mins = max(0.0, (curr - ts).total_seconds() / 60.0)
                if latency_mins > max_latency_found:
                    max_latency_found = latency_mins

        total_records = len(records)
        violations = []

        # Check null ratios
        for k, count in null_counts.items():
            ratio = count / total_records
            if ratio > self.max_null_ratio:
                violations.append(f"Column '{k}' has null ratio {ratio:.3f} > threshold {self.max_null_ratio:.3f}")

        # Check latency SLA
        if max_latency_found > self.max_allowed_latency:
            violations.append(f"Batch maximum ingestion latency {max_latency_found:.1f} mins exceeds SLA {self.max_allowed_latency} mins")

        return {
            "valid": len(violations) == 0,
            "total_records": total_records,
            "max_latency_minutes": round(max_latency_found, 1),
            "violations": violations
        }
