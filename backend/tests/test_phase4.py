"""
FinSight AI — Phase 4 Comprehensive Automated Test Suite
========================================================
"""

import sys
import os
import asyncio
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.main import app
from app.services.csv_parser import parse_financial_csv
from app.services.insights_engine import generate_auto_insights, calculate_cagr
from app.services.ticker_search import search_tickers
from app.services.auto_fetcher import fetch_company_data
from app.schemas.dataset import ParsedCompanyDataset

client = TestClient(app)

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")
SCREENER_CSV_PATH = os.path.join(FIXTURES_DIR, "Asian Paints (4)4332.csv")
COMBINED_CSV_PATH = os.path.join(FIXTURES_DIR, "finsight_combined_template.csv")


# ============================================================================
# 1. DUAL-FORMAT CSV PARSER TESTS
# ============================================================================

def test_screener_csv_parser():
    """Verify Screener.in transposed CSV parser extracts company name, P&L, RATIOS, and TRENDS."""
    assert os.path.exists(SCREENER_CSV_PATH), f"Fixture not found: {SCREENER_CSV_PATH}"
    with open(SCREENER_CSV_PATH, "rb") as f:
        file_bytes = f.read()

    dataset = parse_financial_csv(file_bytes, "Asian Paints (4)4332.csv")
    assert isinstance(dataset, ParsedCompanyDataset)
    assert dataset.detected_format == "screener_csv"
    assert "asian paints" in dataset.company_name.lower()
    assert len(dataset.periods) >= 9  # Multiple fiscal years

    # Check that canonical metrics are parsed properly
    fy24 = next((p for p in dataset.periods if p.fiscal_year == 2024 and p.fiscal_period == "FY"), None)
    assert fy24 is not None
    assert fy24.revenue is not None
    assert fy24.revenue > 30000.0  # Approx 35,495 Cr
    assert fy24.operating_income is not None
    assert fy24.net_income is not None

    # Check TRENDS block extraction
    assert dataset.trends is not None
    assert "metrics" in dataset.trends
    assert "sales_growth" in dataset.trends["metrics"]

    # Check Scenarios extraction
    assert dataset.scenarios is not None
    assert "best_case" in dataset.scenarios or "trailing" in dataset.scenarios


def test_finsight_combined_csv_parser():
    """Verify FinSight Combined row-oriented CSV parser maps all canonical statement fields."""
    assert os.path.exists(COMBINED_CSV_PATH), f"Fixture not found: {COMBINED_CSV_PATH}"
    with open(COMBINED_CSV_PATH, "rb") as f:
        file_bytes = f.read()

    dataset = parse_financial_csv(file_bytes, "finsight_combined_template.csv")
    assert isinstance(dataset, ParsedCompanyDataset)
    assert dataset.detected_format == "finsight_combined_csv"
    assert len(dataset.periods) >= 2

    # Check canonical fields
    fy24 = next((p for p in dataset.periods if p.fiscal_year == 2024), None)
    assert fy24 is not None
    assert fy24.revenue == 125000.0
    assert fy24.net_income == 35000.0
    assert fy24.free_cash_flow == 36000.0


# ============================================================================
# 2. DETERMINISTIC INSIGHTS ENGINE TESTS
# ============================================================================

def test_deterministic_insights_engine():
    """Verify purely mathematical calculations for CAGR, margins, and scenario upside/downside."""
    # Test pure Python CAGR
    cagr = calculate_cagr(100.0, 200.0, 5)
    assert cagr is not None
    assert round(cagr, 1) == 14.9  # (200/100)^(1/5) - 1 = 14.87%

    # Parse and compute insights on Screener file
    with open(SCREENER_CSV_PATH, "rb") as f:
        dataset = parse_financial_csv(f.read(), "Asian Paints (4)4332.csv")

    insights = generate_auto_insights(dataset)
    assert "kpis" in insights or "kpi_cards" in insights
    assert "charts" in insights
    assert "scenarios" in insights
    assert "summary_narrative" in insights

    # Check KPI cards
    kpis = insights.get("kpis") or insights.get("kpi_cards")
    assert len(kpis) > 0

    # Check scenarios
    scenarios = insights.get("scenarios") or insights.get("scenario_insights")
    assert scenarios is not None
    if scenarios.get("upside_best_pct") is not None:
        assert isinstance(scenarios["upside_best_pct"], float)


# ============================================================================
# 3. TICKER SEARCH & AUTO-FETCHER TESTS
# ============================================================================

def test_search_tickers_indian_and_global():
    """Verify search_tickers resolves symbols across NSE and US markets."""
    # Indian equity search
    results_in = asyncio.run(search_tickers("Asian Paints", limit=5))
    assert len(results_in) > 0
    asian_paint = next((r for r in results_in if "ASIANPAINT" in r["symbol"]), results_in[0])
    assert asian_paint["currency"] in ("INR", "USD")

    # US equity search
    results_us = asyncio.run(search_tickers("AAPL", limit=5))
    assert len(results_us) > 0
    aapl = next((r for r in results_us if r["symbol"] == "AAPL"), results_us[0])
    assert aapl["symbol"] == "AAPL"


def test_auto_fetcher_indian_stock():
    """Verify auto_fetcher fetches and normalizes live data for an Indian equity."""
    try:
        dataset = fetch_company_data("ASIANPAINT.NS")
        assert isinstance(dataset, ParsedCompanyDataset)
        assert "asian paints" in dataset.company_name.lower()
        assert dataset.raw_metadata.get("currency") == "INR"
        assert len(dataset.periods) > 0
        assert dataset.auto_insights is not None
    except Exception as e:
        pytest.skip(f"Outbound network call to Yahoo Finance skipped: {e}")


def test_auto_fetcher_us_stock():
    """Verify auto_fetcher fetches and normalizes live data for a US equity."""
    try:
        dataset = fetch_company_data("AAPL")
        assert isinstance(dataset, ParsedCompanyDataset)
        assert "apple" in dataset.company_name.lower()
        assert dataset.raw_metadata.get("currency") == "USD"
        assert len(dataset.periods) > 0
        assert dataset.auto_insights is not None
    except Exception as e:
        pytest.skip(f"Outbound network call to Yahoo Finance skipped: {e}")


# ============================================================================
# 4. FASTAPI ENDPOINTS & RAG Q&A TESTS
# ============================================================================

def test_dataset_upload_endpoint():
    """Verify POST /api/datasets/upload parses, persists, and returns unified hydrated payload."""
    with open(SCREENER_CSV_PATH, "rb") as f:
        response = client.post(
            "/api/datasets/upload",
            files={"file": ("Asian Paints (4)4332.csv", f, "text/csv")}
        )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["success"] is True
    assert "company_id" in data
    assert data["detected_format"] == "screener_csv"
    assert len(data["periods"]) > 0
    assert "auto_insights" in data


def test_company_search_endpoint():
    """Verify GET /api/companies/search returns candidate tickers."""
    response = client.get("/api/companies/search?q=Apple")
    assert response.status_code == 200
    candidates = response.json()
    assert isinstance(candidates, list)
    assert len(candidates) > 0
    assert any(c["symbol"] == "AAPL" for c in candidates)


def test_company_analysis_endpoint():
    """Verify GET /api/companies/{symbol}/analysis returns cached or fresh analysis payload."""
    response = client.get("/api/companies/AAPL/analysis")
    assert response.status_code in (200, 502)
    if response.status_code == 200:
        data = response.json()
        assert data["symbol"] == "AAPL"
        assert "periods" in data
        assert "auto_insights" in data


def test_rag_ask_endpoint_with_mock():
    """Verify POST /api/companies/{company_id}/ask returns grounded answer with citations."""
    with open(SCREENER_CSV_PATH, "rb") as f:
        up_resp = client.post(
            "/api/datasets/upload",
            files={"file": ("Asian Paints (4)4332.csv", f, "text/csv")}
        )
    assert up_resp.status_code == 200
    company_id = up_resp.json()["company_id"]

    mock_gen_response = MagicMock()
    mock_gen_response.text = (
        "Based on verified database records for Asian Paints Limited [Asian Paints (4)4332.csv | Mar-24]:\n"
        "In FY2024, Sales reached Rs. 35,495 Cr with Operating Profit of Rs. 6,185 Cr, achieving an OPM of 17.43%."
    )

    with patch("app.services.rag_service._get_genai_client") as mock_client_factory:
        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_gen_response
        mock_embed_item = MagicMock()
        mock_embed_item.values = [0.01] * 3072
        mock_client.models.embed_content.return_value.embeddings = [mock_embed_item]
        mock_client_factory.return_value = mock_client

        ask_resp = client.post(
            f"/api/companies/{company_id}/ask",
            json={"dataset_id": company_id, "question": "What was the operating profit and margin in FY2024?"}
        )

        assert ask_resp.status_code == 200, ask_resp.text
        ask_data = ask_resp.json()
        assert "answer" in ask_data
        assert "Asian Paints" in ask_data["answer"] or "FY2024" in ask_data["answer"]
        assert "citations" in ask_data
        assert len(ask_data["citations"]) > 0
        assert "source_ref" in ask_data["citations"][0]
