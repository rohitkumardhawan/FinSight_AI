"""
Tests for Report Preview & Deterministic Executive Thesis Fallback:
1. Validates that GET /api/companies/{symbol}/report/preview returns HTTP 200.
2. Validates that the returned payload contains the complete structured report schema.
3. Validates that generate_executive_thesis incorporates verified Neon Postgres metrics
   (Revenue, OPM %, ROE %, Net Debt, DCF Intrinsic Value, and Risk Score) into the thesis.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from fastapi.testclient import TestClient
from app.main import app
from types import SimpleNamespace
from app.models.company import Company
from app.models.dataset import FinancialPeriod
from app.services.risk_engine import RiskIntelligenceResponse
from app.services.report_generator import generate_executive_thesis

client = TestClient(app)


def test_report_preview_endpoint_asianpaint():
    """Verify GET /api/companies/{symbol}/report/preview returns HTTP 200 with complete report schema."""
    response = client.get("/api/companies/ASIANPAINT.NS/report/preview")
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    
    data = response.json()
    assert data["symbol"] == "ASIANPAINT.NS"
    assert "company_name" in data
    assert "current_price" in data
    assert "dcf_intrinsic_value" in data
    assert "rating_stance" in data
    assert "thesis" in data and len(data["thesis"]) > 100
    assert "dcf_summary" in data
    assert "scenarios" in data
    assert "risk_summary" in data
    assert "financials_preview" in data
    assert isinstance(data["financials_preview"], list)


def test_deterministic_thesis_generation_with_metrics():
    """Verify generate_executive_thesis includes verified metrics without Gemini dependency."""
    company = Company(
        id=999,
        symbol="TEST.NS",
        ticker="TEST.NS",
        company_name="Test Industries Ltd",
        sector="Consumer Goods",
        currency="INR"
    )
    period = FinancialPeriod(
        company_id=999,
        fiscal_year=2025,
        statement_type="annual",
        fiscal_period="FY2025",
        metrics_json={
            "revenue": 355409000000.0,
            "opm_pct": 16.85,
            "roe_pct": 28.20,
            "net_debt": 12450000000.0
        }
    )
    dcf = SimpleNamespace(
        current_price=2850.0,
        intrinsic_value=3250.0,
        upside_downside_pct=14.04,
        historical_cagr=0.125,
        wacc=0.115,
        terminal_growth_rate=0.05,
        enterprise_value=320000000000.0,
        net_debt=12450000000.0
    )
    risk = SimpleNamespace(
        overall_score=28.0,
        risk_level="Low",
        pillars={
            "leverage_liquidity": {"debt_to_equity": 0.12, "interest_coverage": 24.5},
            "profitability_stability": {"opm_std_dev": 2.1},
            "valuation_stretch": {"current_pe": 52.4, "pe_stretch_multiple": 1.1},
            "earnings_quality": {"fcf_to_net_income": 1.05, "is_conversion_warning": False}
        },
        watchpoints=[]
    )

    # Calling with timeout_seconds=0.001 to ensure immediate fallback to deterministic thesis
    thesis = generate_executive_thesis(
        company=company,
        periods=[period],
        dcf=dcf,
        risk=risk,
        db=None,
        timeout_seconds=0.001
    )

    assert "Test Industries Ltd" in thesis
    assert "₹35,540.90 Cr" in thesis
    assert "16.85%" in thesis
    assert "28.20%" in thesis
    assert "₹1,245.00 Cr" in thesis
    assert "₹3,250.00" in thesis
    assert "28/100" in thesis
    assert "Low Risk" in thesis
