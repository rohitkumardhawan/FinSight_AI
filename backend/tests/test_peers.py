"""
Unit & Integration Tests for Sector Peer Comparison & Quarterly Statements
==========================================================================
Verifies:
1. GET /api/companies/{symbol}/peers returns 200 with target, up to 5 peers, and sector_median.
2. Target and peer metrics contain all required fields (Price, Market Cap, P/E, OPM %, Net Margin %, ROE %, YoY Growth).
3. Sector median computation mathematically handles non-null values.
4. Quarterly financial periods support in analysis endpoint.
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.services.peer_engine import _calculate_median

client = TestClient(app)


def test_calculate_median_function():
    """Unit test for median computation with nulls, evens, and odds."""
    # Odd count
    assert _calculate_median([10.0, 20.0, 30.0]) == 20.0
    # Even count
    assert _calculate_median([10.0, 20.0, 30.0, 40.0]) == 25.0
    # With None and invalid types
    assert _calculate_median([None, 12.5, None, 15.5, 20.0]) == 15.5
    # Empty or all None
    assert _calculate_median([None, None]) is None
    assert _calculate_median([]) is None


def test_get_sector_peers_asianpaints():
    """Integration test verifying GET /api/companies/ASIANPAINT.NS/peers."""
    response = client.get("/api/companies/ASIANPAINT.NS/peers")
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    
    data = response.json()
    assert "target" in data
    assert "peers" in data
    assert "sector_median" in data
    assert "sector" in data

    target = data["target"]
    assert target["symbol"] == "ASIANPAINT.NS"
    assert "price" in target
    assert "market_cap" in target
    assert "pe_ratio" in target
    assert "opm_pct" in target
    assert "net_margin_pct" in target
    assert "roe_pct" in target
    assert "revenue_growth_pct" in target

    peers = data["peers"]
    assert isinstance(peers, list)
    assert len(peers) >= 1
    assert len(peers) <= 5

    # Check peer fields
    first_peer = peers[0]
    for key in ["symbol", "name", "price", "market_cap", "pe_ratio", "opm_pct", "net_margin_pct", "roe_pct"]:
        assert key in first_peer, f"Missing key {key} in peer"

    # Check sector median
    median = data["sector_median"]
    assert median["symbol"] == "MEDIAN"
    assert "Sector Median" in median["name"]
    for key in ["price", "market_cap", "pe_ratio", "opm_pct", "net_margin_pct", "roe_pct", "revenue_growth_pct"]:
        assert key in median, f"Missing key {key} in sector_median"


def test_quarterly_periods_in_analysis():
    """Test that GET /api/companies/ASIANPAINT.NS/analysis returns both annual and quarterly periods."""
    response = client.get("/api/companies/ASIANPAINT.NS/analysis")
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    
    data = response.json()
    assert "periods" in data
    periods = data["periods"]
    assert len(periods) > 0

    # Verify at least one annual period
    annual_periods = [p for p in periods if p.get("statement_type") != "quarterly" or (p.get("fiscal_period") or "").startswith("FY")]
    assert len(annual_periods) > 0, "Expected at least one annual period"

    # Verify at least one quarterly period (auto-enriched or live fetched)
    quarterly_periods = [p for p in periods if p.get("statement_type") == "quarterly" or (p.get("fiscal_period") or "").startswith("Q")]
    assert len(quarterly_periods) > 0, "Expected at least one quarterly period"
    
    # Check quarterly period structure
    sample_q = quarterly_periods[0]
    assert sample_q.get("fiscal_period", "").startswith("Q")
    assert sample_q.get("statement_type") == "quarterly"
