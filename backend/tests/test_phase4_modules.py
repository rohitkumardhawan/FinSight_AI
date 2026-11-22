"""
FinSight AI — Phase 4 Advanced Modules Automated Test Suite
===========================================================
Tests for:
1. DCF Valuation Engine & POST /api/companies/{symbol}/dcf (including 422 validation)
2. Risk Intelligence Engine & GET /api/companies/{symbol}/risk
3. Institutional PDF Report Preview & GET /api/companies/{symbol}/report/preview
4. Institutional PDF Report Generator & GET /api/companies/{symbol}/report/pdf
"""

import sys
import os
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.main import app

client = TestClient(app)
TEST_SYMBOL = "ASIANPAINT.NS"


# ============================================================================
# 1. DCF VALUATION ENGINE TESTS
# ============================================================================

def test_dcf_default_calculation():
    """Verify POST /api/companies/{symbol}/dcf auto-seeds defaults and calculates DCF."""
    response = client.post(f"/api/companies/{TEST_SYMBOL}/dcf", json={})
    assert response.status_code == 200, f"DCF failed: {response.text}"
    
    data = response.json()
    assert data["symbol"] == TEST_SYMBOL
    assert "Asian Paints" in data["company_name"]
    assert data["currency"] == "INR"
    assert data["intrinsic_value"] > 0
    assert data["current_price"] > 0
    assert "upside_downside_pct" in data
    assert data["enterprise_value"] > 0
    assert data["equity_value"] > 0
    assert data["pv_cash_flows"] > 0
    assert data["pv_terminal_value"] > 0
    assert data["terminal_value"] > 0
    assert data["wacc"] > 0
    assert data["terminal_growth_rate"] > 0
    
    # Check 5-year projections
    assert len(data["projected_periods"]) == 5
    for p in data["projected_periods"]:
        assert p["year"] >= 1
        assert p["projected_fcf"] > 0
        assert 0 < p["discount_factor"] <= 1.0
        assert p["pv_fcf"] > 0

    # Check 5x5 sensitivity matrix
    matrix_data = data["sensitivity_matrix"]
    assert len(matrix_data["wacc_rates"]) == 5
    assert len(matrix_data["terminal_growth_rates"]) == 5
    assert len(matrix_data["matrix"]) == 5
    for row in matrix_data["matrix"]:
        assert len(row) == 5
        # Middle cell should be populated and close to intrinsic value
        assert row[2] is not None


def test_dcf_get_convenience_endpoint():
    """Verify GET /api/companies/{symbol}/dcf returns valid default DCF."""
    response = client.get(f"/api/companies/{TEST_SYMBOL}/dcf")
    assert response.status_code == 200
    data = response.json()
    assert data["symbol"] == TEST_SYMBOL
    assert data["intrinsic_value"] > 0


def test_dcf_custom_overrides():
    """Verify POST /api/companies/{symbol}/dcf respects custom user parameters."""
    payload = {
        "growth_rate": 0.12,
        "wacc": 0.13,
        "terminal_growth_rate": 0.04,
        "projection_years": 7
    }
    response = client.post(f"/api/companies/{TEST_SYMBOL}/dcf", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["growth_rate"] == 0.12
    assert data["wacc"] == 0.13
    assert data["terminal_growth_rate"] == 0.04
    assert data["projection_years"] == 7
    assert len(data["projected_periods"]) == 7


def test_dcf_validation_wacc_spread_422():
    """Verify HTTP 422 is raised when wacc <= terminal_growth + 0.01."""
    # Test case 1: Spread is exactly 0.5% (<= 1%)
    invalid_payload_1 = {
        "wacc": 0.045,
        "terminal_growth_rate": 0.040
    }
    r1 = client.post(f"/api/companies/{TEST_SYMBOL}/dcf", json=invalid_payload_1)
    assert r1.status_code == 422
    assert "WACC must be at least 1% greater than terminal growth rate" in r1.json()["detail"]

    # Test case 2: WACC is equal to terminal growth rate
    invalid_payload_2 = {
        "wacc": 0.04,
        "terminal_growth_rate": 0.04
    }
    r2 = client.post(f"/api/companies/{TEST_SYMBOL}/dcf", json=invalid_payload_2)
    assert r2.status_code == 422

    # Test case 3: WACC is less than terminal growth rate
    invalid_payload_3 = {
        "wacc": 0.03,
        "terminal_growth_rate": 0.04
    }
    r3 = client.post(f"/api/companies/{TEST_SYMBOL}/dcf", json=invalid_payload_3)
    assert r3.status_code == 422


# ============================================================================
# 2. RISK INTELLIGENCE ENGINE TESTS
# ============================================================================

def test_risk_intelligence_endpoint():
    """Verify GET /api/companies/{symbol}/risk returns 4 pillars and watchpoints."""
    response = client.get(f"/api/companies/{TEST_SYMBOL}/risk")
    assert response.status_code == 200, f"Risk intelligence failed: {response.text}"
    
    data = response.json()
    assert data["symbol"] == TEST_SYMBOL
    assert 0 <= data["overall_score"] <= 100
    assert data["risk_level"] in ["Low", "Moderate", "Elevated", "High"]
    
    pillars = data["pillars"]
    assert "leverage_liquidity" in pillars
    assert "profitability_stability" in pillars
    assert "valuation_stretch" in pillars
    assert "earnings_quality" in pillars

    # Pillar 1 check
    p1 = pillars["leverage_liquidity"]
    assert p1["debt_to_equity"] is not None
    assert p1["interest_coverage"] is not None
    assert p1["pillar_score"] >= 0

    # Pillar 2 check
    p2 = pillars["profitability_stability"]
    assert p2["opm_std_dev"] >= 0
    assert isinstance(p2["historical_opms"], list)

    # Pillar 3 check
    p3 = pillars["valuation_stretch"]
    assert p3["dcf_intrinsic_value"] > 0
    assert p3["pe_stretch_multiple"] is not None

    # Pillar 4 check
    p4 = pillars["earnings_quality"]
    assert "is_conversion_warning" in p4
    assert p4["pillar_score"] >= 0

    # Watchpoints check
    watchpoints = data["watchpoints"]
    assert len(watchpoints) == 3
    for wp in watchpoints:
        assert wp["category"]
        assert wp["title"]
        assert wp["description"]
        assert wp["severity"] in ["Low", "Moderate", "Elevated", "High"]


# ============================================================================
# 3. REPORT PREVIEW TESTS
# ============================================================================

def test_report_preview_endpoint():
    """Verify GET /api/companies/{symbol}/report/preview returns structured JSON preview."""
    response = client.get(f"/api/companies/{TEST_SYMBOL}/report/preview")
    assert response.status_code == 200, f"Preview failed: {response.text}"
    
    data = response.json()
    assert data["symbol"] == TEST_SYMBOL
    assert data["company_name"]
    assert data["currency"] == "INR"
    assert data["current_price"] > 0
    assert data["dcf_intrinsic_value"] > 0
    assert data["rating_stance"] in ["OVERWEIGHT / BUY", "NEUTRAL / HOLD", "UNDERWEIGHT / SELL"]
    assert len(data["thesis"]) > 100
    assert len(data["financials_preview"]) >= 3
    assert data["dcf_summary"]["enterprise_value"]
    assert data["risk_summary"]["overall_score"] >= 0


# ============================================================================
# 4. REPORT PDF GENERATOR TESTS
# ============================================================================

def test_report_pdf_download():
    """Verify GET /api/companies/{symbol}/report/pdf streams valid ReportLab PDF."""
    response = client.get(f"/api/companies/{TEST_SYMBOL}/report/pdf")
    assert response.status_code == 200, f"PDF download failed: {response.text}"
    
    # Check headers
    assert "application/pdf" in response.headers.get("content-type", "")
    content_disp = response.headers.get("content-disposition", "")
    assert "FinSight_ASIANPAINT_NS_Research_Report.pdf" in content_disp or "attachment" in content_disp
    
    # Check binary content
    pdf_bytes = response.content
    assert len(pdf_bytes) > 2000, f"PDF content unexpectedly small: {len(pdf_bytes)} bytes"
    assert pdf_bytes.startswith(b"%PDF-"), "File does not start with standard PDF magic bytes '%PDF-'"
