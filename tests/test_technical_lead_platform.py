"""Unit tests for Watercare Services Data & Analytics Technical Lead Platform."""
from datetime import datetime, timezone, timedelta
import pytest

from watercare_asset.technical_lead_platform import (
    WaterQualityStatus,
    RiskClassification,
    WaterQualityObservation,
    DistrictMeteredAreaTelemetry,
    TaumataArowaiComplianceEngine,
    WatercareSemanticLayer,
    DataAssuranceGate,
)


@pytest.fixture
def compliance_engine():
    return TaumataArowaiComplianceEngine()


@pytest.fixture
def sample_compliant():
    return WaterQualityObservation(
        sample_id="SMP-AKL-001",
        zone_id="ZONE-NORTH-SHORE",
        observed_at=datetime(2026, 11, 16, 5, 0, tzinfo=timezone.utc),
        turbidity_ntu=0.15,
        free_available_chlorine_ppm=1.20,
        ph_level=7.4,
        e_coli_cfu_per_100ml=0,
    )


def test_evaluate_sample_compliant(compliance_engine, sample_compliant):
    status, reasons = compliance_engine.evaluate_sample(sample_compliant)
    assert status == WaterQualityStatus.COMPLIANT
    assert "compliant" in reasons[0].lower()


def test_evaluate_sample_ecoli_breach(compliance_engine):
    sample = WaterQualityObservation(
        sample_id="SMP-AKL-002",
        zone_id="ZONE-WAITAKERE",
        observed_at=datetime.now(timezone.utc),
        turbidity_ntu=0.20,
        free_available_chlorine_ppm=1.10,
        ph_level=7.2,
        e_coli_cfu_per_100ml=2, # Critical breach
    )
    status, reasons = compliance_engine.evaluate_sample(sample)
    assert status == WaterQualityStatus.BREACH
    assert any("e. coli" in r.lower() for r in reasons)


def test_evaluate_sample_turbidity_breach(compliance_engine):
    sample = WaterQualityObservation(
        sample_id="SMP-AKL-003",
        zone_id="ZONE-MANUKAU",
        observed_at=datetime.now(timezone.utc),
        turbidity_ntu=0.85, # Exceeds 0.50 NTU
        free_available_chlorine_ppm=1.00,
        ph_level=7.5,
        e_coli_cfu_per_100ml=0,
    )
    status, reasons = compliance_engine.evaluate_sample(sample)
    assert status == WaterQualityStatus.BREACH
    assert any("turbidity" in r.lower() for r in reasons)


def test_evaluate_sample_chlorine_warning_or_breach(compliance_engine):
    # Below statutory 0.20 ppm min
    sample = WaterQualityObservation(
        sample_id="SMP-AKL-004",
        zone_id="ZONE-CENTRAL",
        observed_at=datetime.now(timezone.utc),
        turbidity_ntu=0.10,
        free_available_chlorine_ppm=0.08,
        ph_level=7.0,
        e_coli_cfu_per_100ml=0,
    )
    status, reasons = compliance_engine.evaluate_sample(sample)
    assert status == WaterQualityStatus.BREACH
    assert any("chlorine" in r.lower() for r in reasons)


def test_audit_batch_aggregation(compliance_engine, sample_compliant):
    sample_breach = WaterQualityObservation(
        sample_id="SMP-AKL-005",
        zone_id="ZONE-EAST",
        observed_at=datetime.now(timezone.utc),
        turbidity_ntu=0.95,
        free_available_chlorine_ppm=1.0,
        ph_level=7.1,
        e_coli_cfu_per_100ml=0,
    )
    report = compliance_engine.audit_batch([sample_compliant, sample_breach])
    assert report.total_samples == 2
    assert report.compliant_samples == 1
    assert report.breach_samples == 1
    assert report.compliance_rate_pct == 50.0
    assert "SMP-AKL-005" in report.breach_sample_ids


def test_non_revenue_water_calculation_low_risk():
    telemetry = DistrictMeteredAreaTelemetry(
        dma_id="DMA-PONSONBY-01",
        timestamp=datetime.now(timezone.utc),
        inflow_lps=100.0,
        outflow_lps=96.0,
        average_pressure_kpa=450.0,
        minimum_night_flow_lps=12.0,
    )
    metrics = WatercareSemanticLayer.calculate_non_revenue_water(telemetry)
    assert metrics["loss_pct"] == 4.0
    assert metrics["risk_classification"] == RiskClassification.LOW
    assert metrics["is_leak_suspect"] is False
    assert metrics["inflow_mld"] == pytest.approx(8.64, 0.01)


def test_non_revenue_water_calculation_critical_burst():
    telemetry = DistrictMeteredAreaTelemetry(
        dma_id="DMA-EPSOM-02",
        timestamp=datetime.now(timezone.utc),
        inflow_lps=120.0,
        outflow_lps=80.0,
        average_pressure_kpa=650.0,
        minimum_night_flow_lps=55.0, # 45.8% minimum night flow!
    )
    metrics = WatercareSemanticLayer.calculate_non_revenue_water(telemetry)
    assert metrics["loss_pct"] == pytest.approx(33.33, 0.05)
    assert metrics["risk_classification"] == RiskClassification.CRITICAL
    assert metrics["is_leak_suspect"] is True


def test_snowflake_dbt_semantic_model():
    yaml_schema = WatercareSemanticLayer.generate_snowflake_dbt_semantic_model()
    assert "fct_watercare_dma_analytics" in yaml_schema
    assert "nrw_loss_percentage" in yaml_schema
    assert "unique" in yaml_schema


def test_data_assurance_gate_pass():
    gate = DataAssuranceGate(max_allowed_latency_minutes=60, max_null_ratio=0.05)
    now = datetime.now(timezone.utc)
    batch = [
        {"sample_id": "S1", "val": 10.0, "timestamp": now - timedelta(minutes=15)},
        {"sample_id": "S2", "val": 12.0, "timestamp": now - timedelta(minutes=10)},
    ]
    res = gate.validate_ingestion_batch(batch, now)
    assert res["valid"] is True
    assert res["total_records"] == 2
    assert len(res["violations"]) == 0


def test_data_assurance_gate_null_violation():
    gate = DataAssuranceGate(max_allowed_latency_minutes=60, max_null_ratio=0.10)
    now = datetime.now(timezone.utc)
    batch = [
        {"sample_id": "S1", "val": None, "timestamp": now},
        {"sample_id": "S2", "val": None, "timestamp": now},
        {"sample_id": "S3", "val": 15.0, "timestamp": now},
    ]
    res = gate.validate_ingestion_batch(batch, now)
    assert res["valid"] is False
    assert any("null ratio" in v.lower() for v in res["violations"])


def test_data_assurance_gate_latency_sla_violation():
    gate = DataAssuranceGate(max_allowed_latency_minutes=30)
    now = datetime.now(timezone.utc)
    batch = [
        {"sample_id": "S1", "val": 10.0, "timestamp": now - timedelta(minutes=95)},
    ]
    res = gate.validate_ingestion_batch(batch, now)
    assert res["valid"] is False
    assert any("latency" in v.lower() for v in res["violations"])


def test_evaluate_sample_ph_warning(compliance_engine):
    sample = WaterQualityObservation(
        sample_id="SMP-AKL-006",
        zone_id="ZONE-SOUTH",
        observed_at=datetime.now(timezone.utc),
        turbidity_ntu=0.20,
        free_available_chlorine_ppm=1.00,
        ph_level=6.2, # Below 6.5
        e_coli_cfu_per_100ml=0,
    )
    status, reasons = compliance_engine.evaluate_sample(sample)
    assert status == WaterQualityStatus.WARNING
    assert any("ph" in r.lower() for r in reasons)


def test_audit_empty_batch(compliance_engine):
    report = compliance_engine.audit_batch([])
    assert report.total_samples == 0
    assert report.compliance_rate_pct == 100.0


def test_zero_inflow_dma():
    telemetry = DistrictMeteredAreaTelemetry(
        dma_id="DMA-OFFLINE-01",
        timestamp=datetime.now(timezone.utc),
        inflow_lps=0.0,
        outflow_lps=0.0,
        average_pressure_kpa=0.0,
        minimum_night_flow_lps=0.0,
    )
    metrics = WatercareSemanticLayer.calculate_non_revenue_water(telemetry)
    assert metrics["loss_pct"] == 0.0
    assert metrics["is_leak_suspect"] is False


def test_data_assurance_empty_batch():
    gate = DataAssuranceGate()
    res = gate.validate_ingestion_batch([], datetime.now(timezone.utc))
    assert res["valid"] is False
    assert "empty batch" in res["reason"].lower()


def test_chlorine_excess_breach(compliance_engine):
    sample = WaterQualityObservation(
        sample_id="SMP-AKL-007",
        zone_id="ZONE-EAST",
        observed_at=datetime.now(timezone.utc),
        turbidity_ntu=0.10,
        free_available_chlorine_ppm=5.50, # Exceeds 5.0 ppm limit
        ph_level=7.2,
        e_coli_cfu_per_100ml=0,
    )
    status, reasons = compliance_engine.evaluate_sample(sample)
    assert status == WaterQualityStatus.BREACH
    assert any("exceeds aesthetic max" in r.lower() for r in reasons)
