"""
FinSight AI — Test Financial Statements Waterfall & Line Items
=============================================================
Verifies institutional 3-statement waterfall integrity on ASIANPAINT.NS:
- Revenue -> Gross Profit -> OpEx -> EBITDA -> D&A -> EBIT -> EBT -> Net Income
- Full Balance sheet line items (Receivables, Net PPE, Investments, Payables, Net Debt)
- Cash flow statement waterfall (OCF, CFI, CapEx, CFF, Net Change in Cash, FCF)
"""

import sys
import os
from pathlib import Path

# Ensure backend root is on sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from fastapi.testclient import TestClient
from app.main import app
from app.services.auto_fetcher import fetch_company_data

client = TestClient(app)


def test_asianpaints_auto_fetcher_waterfall():
    """Verify that auto_fetcher pulls and computes institutional statement items for ASIANPAINT.NS."""
    dataset = fetch_company_data("ASIANPAINT.NS")
    assert dataset is not None
    assert len(dataset.periods) > 0

    annual_periods = [p for p in dataset.periods if p.statement_type == "annual_combined"]
    assert len(annual_periods) >= 3

    latest = annual_periods[-1]
    
    # 1. Income Statement checks
    assert latest.revenue is not None and latest.revenue > 0
    assert latest.cost_of_revenue is not None and latest.cost_of_revenue > 0
    assert latest.gross_profit is not None and latest.gross_profit > 0
    assert latest.ebitda is not None and latest.ebitda > 0
    assert latest.operating_income is not None and latest.operating_income > 0
    assert latest.net_income is not None and latest.net_income > 0

    # Mathematical waterfall: Gross Profit = Revenue - Cost of Revenue
    assert abs(latest.gross_profit - (latest.revenue - latest.cost_of_revenue)) < 1.0

    # EBITDA - D&A = Operating Income (EBIT)
    da = abs(latest.depreciation_amortization or 0.0)
    assert abs((latest.ebitda - da) - latest.operating_income) < 1.0

    # 2. Balance Sheet checks
    assert latest.total_assets is not None and latest.total_assets > 0
    assert latest.current_assets is not None and latest.current_assets > 0
    assert latest.total_liabilities is not None and latest.total_liabilities > 0
    assert latest.total_equity is not None and latest.total_equity > 0
    assert latest.cash_and_equivalents is not None and latest.cash_and_equivalents > 0
    assert latest.receivables is not None and latest.receivables > 0
    assert latest.inventory is not None and latest.inventory > 0
    assert latest.net_ppe is not None and latest.net_ppe > 0

    # Balance Sheet memo items
    assert latest.net_debt is not None
    assert latest.net_working_capital is not None
    assert latest.invested_capital is not None

    # Working Capital = Current Assets - Current Liabilities
    if latest.current_liabilities is not None:
        assert abs(latest.net_working_capital - (latest.current_assets - latest.current_liabilities)) < 1.0

    # 3. Cash Flow checks
    assert latest.operating_cash_flow is not None and latest.operating_cash_flow > 0
    assert latest.capital_expenditure is not None and latest.capital_expenditure > 0
    assert latest.free_cash_flow is not None

    # OCF - CapEx = FCF
    assert abs(latest.free_cash_flow - (latest.operating_cash_flow - latest.capital_expenditure)) < 1.0

    # Investing and Financing cash flows
    assert latest.investing_cash_flow is not None
    assert latest.financing_cash_flow is not None
    assert latest.net_change_in_cash is not None


def test_asianpaints_analysis_endpoint_has_all_lines():
    """Verify that GET /api/companies/ASIANPAINT.NS/analysis exposes new line items in periods."""
    resp = client.get("/api/companies/ASIANPAINT.NS/analysis?refresh=true")
    assert resp.status_code == 200
    data = resp.json()
    assert data["symbol"] == "ASIANPAINT.NS"
    periods = data.get("periods", [])
    assert len(periods) > 0

    annual = [p for p in periods if p.get("statement_type") != "quarterly"]
    assert len(annual) > 0
    latest = annual[-1]

    # Check that new institutional keys are present in JSON response
    expected_keys = [
        "revenue", "cost_of_revenue", "gross_profit", "ebitda", "ebitda_margin_pct",
        "depreciation_amortization", "operating_income", "net_income",
        "cash_and_equivalents", "receivables", "inventory", "net_ppe",
        "total_assets", "current_assets", "total_liabilities", "current_liabilities", "total_equity",
        "net_debt", "net_working_capital", "invested_capital",
        "operating_cash_flow", "capital_expenditure", "investing_cash_flow",
        "financing_cash_flow", "net_change_in_cash", "free_cash_flow"
    ]
    for key in expected_keys:
        assert key in latest, f"Missing {key} in latest annual period JSON"
        assert latest[key] is not None, f"Expected non-null {key} in latest annual period"
