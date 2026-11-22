"""
FinSight AI — Regression Tests for P0 Financial Accuracy & AI Audit Fixes
========================================================================
Verifies:
1. GET /api/companies/AAPL/peers returns ONLY USD peers (zero .NS / INR tickers).
2. ASIANPAINT.NS returns identical trailing_pe across /analysis, /risk, and /report/preview,
   and /report/preview contains ZERO "Nonex" strings and non-null Best/Worst targets.
3. POST /api/companies/ASIANPAINT.NS/ask returns formatted cash flow & risk analysis
   (no raw 355409000000.0 floats or P/E=None).
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_aapl_peers_currency_isolation():
    """Verify GET /api/companies/AAPL/peers returns ONLY USD peers (zero .NS / INR tickers)."""
    response = client.get("/api/companies/AAPL/peers")
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

    data = response.json()
    assert "target" in data
    assert "peers" in data
    assert "sector_median" in data

    target = data["target"]
    assert target["currency"] == "USD"
    assert data["sector_median"]["currency"] == "USD"

    # Strict Currency Invariance: Zero INR or .NS peers
    peers = data["peers"]
    assert len(peers) > 0, "Expected at least 1 peer for AAPL"

    for peer in peers:
        assert peer.get("currency") == "USD", f"Found non-USD peer: {peer}"
        sym = peer.get("symbol", "")
        assert not sym.endswith(".NS"), f"Found .NS ticker in USD peers: {sym}"
        assert not sym.endswith(".BO"), f"Found .BO ticker in USD peers: {sym}"

    # Verify sector median does not mix INR stock prices
    med_price = data["sector_median"].get("price")
    if med_price is not None:
        assert med_price < 1000.0, f"Unreasonable median price for USD tech peers: {med_price}"


def test_asianpaints_canonical_pe_and_report_integrity():
    """
    Verify ASIANPAINT.NS returns identical trailing_pe across /analysis, /risk, and /report/preview,
    and /report/preview contains ZERO 'Nonex' or 'N/Ax' strings and non-null Best/Worst targets.
    """
    # 1. Fetch analysis
    res_analysis = client.get("/api/companies/ASIANPAINT.NS/analysis")
    assert res_analysis.status_code == 200, f"Failed /analysis: {res_analysis.text}"
    data_analysis = res_analysis.json()
    quote = data_analysis.get("quote", {})
    auto_insights = data_analysis.get("auto_insights", {})
    pe_analysis = quote.get("trailing_pe") or auto_insights.get("scenario_insights", {}).get("trailing_pe")

    # 2. Fetch risk
    res_risk = client.get("/api/companies/ASIANPAINT.NS/risk")
    assert res_risk.status_code == 200, f"Failed /risk: {res_risk.text}"
    data_risk = res_risk.json()
    pe_risk = data_risk.get("pillars", {}).get("valuation_stretch", {}).get("current_pe")

    # 3. Fetch report preview
    res_report = client.get("/api/companies/ASIANPAINT.NS/report/preview")
    assert res_report.status_code == 200, f"Failed /report/preview: {res_report.text}"
    data_report = res_report.json()
    scenarios = data_report.get("scenarios", {})
    pe_report = scenarios.get("trailing_pe") or data_report.get("risk_summary", {}).get("pillars", {}).get("valuation_stretch", {}).get("current_pe")

    # Canonical trailing_pe consistency
    assert pe_analysis is not None, "P/E in /analysis is None"
    assert pe_risk is not None, "P/E in /risk is None"
    assert pe_report is not None, "P/E in /report/preview is None"
    assert round(float(pe_analysis), 2) == round(float(pe_risk), 2) == round(float(pe_report), 2), (
        f"P/E mismatch: analysis={pe_analysis}, risk={pe_risk}, report={pe_report}"
    )

    # ZERO 'Nonex' or 'N/Ax' in preview response
    report_text = res_report.text
    assert "Nonex" not in report_text, "Found 'Nonex' bug string in report preview JSON!"
    assert "N/Ax" not in report_text, "Found 'N/Ax' bug string in report preview JSON!"

    # Non-null Best and Worst Case targets
    worst_val = scenarios.get("worst_case", {}).get("fair_value") or scenarios.get("worst_case_price")
    best_val = scenarios.get("best_case", {}).get("fair_value") or scenarios.get("best_case_price")
    base_val = scenarios.get("base_case", {}).get("fair_value") or scenarios.get("base_case_price")

    assert worst_val is not None, "worst_case target price is None"
    assert best_val is not None, "best_case target price is None"
    assert base_val is not None, "base_case target price is None"
    assert worst_val > 0 and best_val > 0 and base_val > 0, f"Targets must be positive: {worst_val}, {base_val}, {best_val}"


def test_asianpaints_ask_rag_formatted_cash_flow_and_risk():
    """
    Verify POST /api/companies/ASIANPAINT.NS/ask returns formatted cash flow & risk analysis
    without raw floats (e.g. no '355409000000.0').
    """
    response = client.post(
        "/api/companies/ASIANPAINT.NS/ask",
        json={"question": "What is the cash flow generation, balance sheet leverage, and risk profile of Asian Paints?"}
    )
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

    data = response.json()
    answer = data.get("answer", "")
    assert len(answer) > 50, "Expected substantive research response"

    # Must NOT contain raw unformatted float dumps
    assert "355409000000.0" not in answer, "Found raw unformatted float '355409000000.0' in RAG answer!"
    assert "70881800000.0" not in answer, "Found raw unformatted float '70881800000.0' in RAG answer!"
    assert "P/E=None" not in answer, "Found raw fallback 'P/E=None' in RAG answer!"

    # Must contain formatted institutional figures (Cr, ₹, %, or x)
    assert ("Cr" in answer or "₹" in answer or "%" in answer or "x" in answer), (
        f"Answer missing institutional metrics formatting: {answer[:200]}"
    )
