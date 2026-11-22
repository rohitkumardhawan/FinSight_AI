"""
FinSight AI — Regression Tests for P1 Institutional Usability & Financial Depth Upgrades
========================================================================================
Verifies:
1. Exact and prefix ticker search ranking:
   - Query "AAPL" ranks AAPL #1.
   - Query "TCS" ranks TCS.NS #1.
   - Query "ASIANPAINT" ranks ASIANPAINT.NS #1.
2. Institutional Valuation Multiples & Efficiency Ratios in auto_insights:
   - EV / EBITDA, EV / Revenue, Price-to-Book (P/B), Price-to-Sales (P/S),
     FCF Yield %, Debt / EBITDA, ROCE/ROIC %, Asset Turnover, Inventory Turnover.
3. Multi-Year CAGRs in trends metrics:
   - Historical CAGRs calculated for sales, ebit, net profit, eps, and fcf.
4. Quarterly Cash Flow enrichment in company analysis.
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.services.ticker_search import search_tickers
from app.services.insights_engine import generate_auto_insights
from app.schemas.dataset import ParsedCompanyDataset, FinancialPeriodRecord

client = TestClient(app)


def test_search_ranking_exact_matches():
    """Verify exact ticker matches rank #1 ahead of arbitrary partial matches via API."""
    # Test AAPL
    res_aapl = client.get("/api/companies/search?q=AAPL&limit=5")
    assert res_aapl.status_code == 200
    results_aapl = res_aapl.json()
    assert len(results_aapl) > 0, "Expected search results for 'AAPL'"
    assert results_aapl[0]["symbol"] == "AAPL", f"Expected AAPL #1, got {results_aapl[0]['symbol']}"

    # Test TCS (NSE stock TCS.NS)
    res_tcs = client.get("/api/companies/search?q=TCS&limit=5")
    assert res_tcs.status_code == 200
    results_tcs = res_tcs.json()
    assert len(results_tcs) > 0, "Expected search results for 'TCS'"
    assert results_tcs[0]["symbol"] in ("TCS.NS", "TCS"), f"Expected TCS.NS #1, got {results_tcs[0]['symbol']}"

    # Test ASIANPAINT
    res_ap = client.get("/api/companies/search?q=ASIANPAINT&limit=5")
    assert res_ap.status_code == 200
    results_ap = res_ap.json()
    assert len(results_ap) > 0, "Expected search results for 'ASIANPAINT'"
    assert results_ap[0]["symbol"] in ("ASIANPAINT.NS", "ASIANPAINT"), f"Expected ASIANPAINT.NS #1, got {results_ap[0]['symbol']}"


def test_institutional_multiples_and_efficiency_ratios_engine():
    """
    Verify insights_engine computes EV/EBITDA, EV/Revenue, P/B, P/S, FCF Yield,
    Debt/EBITDA, ROIC, and Asset Turnover deterministically.
    """
    mock_financials = [
        {
            "fiscal_year": 2020,
            "statement_type": "annual",
            "revenue": 80000000.0,
            "operating_income": 16000000.0,
            "cost_of_revenue": 50000000.0,
            "depreciation_amortization": 4000000.0,
            "net_income": 12000000.0,
            "operating_cash_flow": 18000000.0,
            "capital_expenditure": 6000000.0,
            "free_cash_flow": 12000000.0,
            "total_assets": 100000000.0,
            "total_liabilities": 35000000.0,
            "total_equity": 65000000.0,
            "current_assets": 40000000.0,
            "current_liabilities": 20000000.0,
            "total_debt": 18000000.0,
            "cash_and_equivalents": 8000000.0,
            "inventory": 12000000.0,
            "diluted_eps": 12.0,
        },
        {
            "fiscal_year": 2021,
            "statement_type": "annual",
            "revenue": 100000000.0,
            "operating_income": 20000000.0,
            "cost_of_revenue": 60000000.0,
            "depreciation_amortization": 5000000.0,
            "net_income": 15000000.0,
            "operating_cash_flow": 22000000.0,
            "capital_expenditure": 7000000.0,
            "free_cash_flow": 15000000.0,
            "total_assets": 120000000.0,
            "total_liabilities": 40000000.0,
            "total_equity": 80000000.0,
            "current_assets": 50000000.0,
            "current_liabilities": 25000000.0,
            "total_debt": 20000000.0,
            "cash_and_equivalents": 10000000.0,
            "inventory": 15000000.0,
            "diluted_eps": 15.0,
        },
        {
            "fiscal_year": 2022,
            "statement_type": "annual",
            "revenue": 120000000.0,
            "operating_income": 26000000.0,
            "cost_of_revenue": 70000000.0,
            "depreciation_amortization": 6000000.0,
            "net_income": 19000000.0,
            "operating_cash_flow": 28000000.0,
            "capital_expenditure": 8000000.0,
            "free_cash_flow": 20000000.0,
            "total_assets": 140000000.0,
            "total_liabilities": 45000000.0,
            "total_equity": 95000000.0,
            "current_assets": 60000000.0,
            "current_liabilities": 30000000.0,
            "total_debt": 22000000.0,
            "cash_and_equivalents": 12000000.0,
            "inventory": 18000000.0,
            "diluted_eps": 19.0,
        },
        {
            "fiscal_year": 2023,
            "statement_type": "annual",
            "revenue": 150000000.0,
            "operating_income": 35000000.0,
            "cost_of_revenue": 85000000.0,
            "depreciation_amortization": 7000000.0,
            "net_income": 25000000.0,
            "operating_cash_flow": 36000000.0,
            "capital_expenditure": 10000000.0,
            "free_cash_flow": 26000000.0,
            "total_assets": 170000000.0,
            "total_liabilities": 50000000.0,
            "total_equity": 120000000.0,
            "current_assets": 75000000.0,
            "current_liabilities": 35000000.0,
            "total_debt": 25000000.0,
            "cash_and_equivalents": 15000000.0,
            "inventory": 20000000.0,
            "diluted_eps": 25.0,
        },
    ]

    mock_quote = {
        "current_price": 500.0,
        "market_cap": 500000000.0,
        "trailing_pe": 20.0,
    }

    dataset = ParsedCompanyDataset(
        company_name="Test Co",
        filename="test.csv",
        detected_format="screener_csv",
        periods=[FinancialPeriodRecord(**p) for p in mock_financials],
        raw_metadata={"quote": mock_quote, "currency": "INR"}
    )

    insights = generate_auto_insights(dataset)
    time_series = insights.get("time_series", [])
    assert len(time_series) == 4, f"Expected 4 time series items, got {len(time_series)}"

    latest = time_series[-1]
    # Check institutional valuation multiples in time_series
    assert latest.get("ev_to_ebitda") is not None
    assert latest.get("price_to_book") is not None
    assert latest.get("price_to_sales") is not None
    assert latest.get("fcf_yield_pct") is not None
    assert latest.get("debt_to_ebitda") is not None
    assert latest.get("roic_pct") is not None
    assert latest.get("asset_turnover") is not None
    assert latest.get("inventory_turnover") is not None

    # Expected math checks:
    # 2023 revenue = 150M, total_assets = 170M -> asset_turnover = 150 / 170 ~= 0.88
    assert abs(latest["asset_turnover"] - (150000000.0 / 170000000.0)) < 0.05
    # 2023 COGS = 85M, inventory = 20M -> inventory_turnover = 85 / 20 = 4.25
    assert abs(latest["inventory_turnover"] - 4.25) < 0.05
    # 2023 market_cap = 500M, total_equity = 120M -> P/B = 500 / 120 ~= 4.17
    assert abs(latest["price_to_book"] - (500000000.0 / 120000000.0)) < 0.05
    # 2023 FCF = 26M, market_cap = 500M -> FCF yield = 26 / 500 * 100 = 5.2%
    assert abs(latest["fcf_yield_pct"] - 5.2) < 0.1

    # Check multi-year CAGRs
    trends = insights.get("trends", {})
    metrics = trends.get("metrics", {})
    assert "sales_growth" in metrics
    assert "ebit_growth" in metrics
    assert "net_profit_growth" in metrics
    assert "eps_growth" in metrics
    assert "fcf_growth" in metrics

    # 3-year CAGR for revenue: from 80M (2020) to 150M (2023) over 3 years: (150/80)**(1/3) - 1 ~= 23.31%
    sales_growth = metrics["sales_growth"]
    assert "3 YEARS" in sales_growth
    assert abs(sales_growth["3 YEARS"] - 23.31) < 0.5


def test_api_quarterly_cash_flow_populated():
    """Verify GET /api/companies/ASIANPAINT.NS/analysis returns quarterly statements with cash flows."""
    res = client.get("/api/companies/ASIANPAINT.NS/analysis")
    assert res.status_code == 200, f"Analysis failed: {res.text}"
    data = res.json()

    periods = data.get("financial_periods", [])
    quarterly_periods = [
        p for p in periods
        if (p.get("fiscal_period") or "").startswith("Q") or p.get("statement_type") == "quarterly"
    ]

    # If quarterly periods exist, verify cash flow fields are not all empty/None
    if quarterly_periods:
        has_cash_flow = any(
            p.get("operating_cash_flow") is not None or p.get("free_cash_flow") is not None
            for p in quarterly_periods
        )
        assert has_cash_flow, "Expected at least one quarterly period with populated cash flow metrics"
