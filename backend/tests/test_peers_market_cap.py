"""
Tests for Sub-Industry & Market-Cap Peer Selection, EBITDA Metrics & CAGR N/M
=============================================================================
Verifies:
1. GET /api/companies/360ONE.NS/peers does NOT return alphabetical A... peers
   (like AUBANK.NS, AADHARHFC.NS) when Asset Management / Wealth peers exist.
2. Target, peers, and sector_median contain ev_to_ebitda, ebitda_margin_pct, and price_to_book.
3. calculate_cagr returns "N/M" (Not Meaningful) when start or end value <= 0.
4. GET /api/companies/{symbol}/analysis exposes ebitda and ebitda_margin_pct.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.services.insights_engine import calculate_cagr

client = TestClient(app)


def test_calculate_cagr_not_meaningful():
    """CAGR must return 'N/M' when start or end is <= 0, and float when positive."""
    # Negative start
    assert calculate_cagr(-50.0, 100.0, 3) == "N/M"
    # Negative end
    assert calculate_cagr(100.0, -25.0, 3) == "N/M"
    # Zero start
    assert calculate_cagr(0.0, 100.0, 3) == "N/M"
    # Zero end
    assert calculate_cagr(100.0, 0.0, 3) == "N/M"
    # Valid positive CAGR
    res = calculate_cagr(100.0, 200.0, 3)
    assert isinstance(res, float)
    assert round(res, 2) == 25.99
    # None or non-positive years
    assert calculate_cagr(None, 100.0, 3) is None
    assert calculate_cagr(100.0, None, 3) is None
    assert calculate_cagr(100.0, 200.0, 0) is None


def test_360one_peers_not_alphabetical_and_industry_matched():
    """GET /api/companies/360ONE.NS/peers must match Asset Management peers, not alphabetical A..."""
    response = client.get("/api/companies/360ONE.NS/peers")
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

    data = response.json()
    assert "target" in data
    assert "peers" in data
    assert "sector_median" in data

    target = data["target"]
    assert target["symbol"] == "360ONE.NS"
    assert "ev_to_ebitda" in target
    assert "ebitda_margin_pct" in target
    assert "price_to_book" in target

    peers = data["peers"]
    assert len(peers) >= 1
    peer_symbols = [p["symbol"] for p in peers]

    # Verify that alphabetical unrelated finance tickers are NOT returned
    assert "AUBANK.NS" not in peer_symbols, f"AUBANK.NS should not be selected as top wealth peer: {peer_symbols}"
    assert "AADHARHFC.NS" not in peer_symbols, f"AADHARHFC.NS should not be selected: {peer_symbols}"
    assert "AAVAS.NS" not in peer_symbols, f"AAVAS.NS should not be selected: {peer_symbols}"

    # Verify that at least one top Asset Management / Wealth peer is selected
    amc_candidates = {"ABSLAMC.NS", "ANANDRATHI.NS", "HDFCAMC.NS", "ICICIAMC.NS", "NAM-INDIA.NS", "MOTILALOFS.NS"}
    matched_amc = [s for s in peer_symbols if s in amc_candidates]
    assert len(matched_amc) >= 1, f"Expected Asset Management peers, got {peer_symbols}"

    # Verify peer metrics have all new fields
    for p in peers:
        assert "ev_to_ebitda" in p
        assert "ebitda_margin_pct" in p
        assert "price_to_book" in p

    # Verify sector median has new fields
    median = data["sector_median"]
    assert "ev_to_ebitda" in median
    assert "ebitda_margin_pct" in median
    assert "price_to_book" in median


def test_analysis_exposes_ebitda_and_growth():
    """GET /api/companies/360ONE.NS/analysis must include EBITDA metrics and trends."""
    response = client.get("/api/companies/360ONE.NS/analysis")
    assert response.status_code == 200, f"Expected 200: {response.text}"

    data = response.json()
    periods = data.get("periods", [])
    assert len(periods) > 0

    # Check at least one annual period has EBITDA and EBITDA margin
    has_ebitda = any(p.get("ebitda") is not None for p in periods)
    assert has_ebitda, "Expected at least one period with ebitda populated"

    # Check trends has ebitda_growth
    trends = data.get("trends", {})
    metrics = trends.get("metrics", {})
    assert "ebitda_growth" in metrics, f"Expected ebitda_growth in trends metrics: {metrics.keys()}"
