"""
Unit Tests for Live Market Indices Ticker (/api/market/indices)
===============================================================
Verifies live and cached market benchmark quotes (^NSEI, ^GSPC, ^IXIC).
"""

from fastapi.testclient import TestClient
from app.main import create_app

client = TestClient(create_app())


def test_market_indices_endpoint_success():
    """Verify GET /api/market/indices returns 200 with all 3 benchmark indices."""
    res = client.get("/api/market/indices")
    assert res.status_code == 200
    data = res.json()

    assert "indices" in data
    assert "last_updated" in data
    assert "is_cached" in data

    indices = data["indices"]
    assert len(indices) == 3

    symbols = [idx["symbol"] for idx in indices]
    assert "^NSEI" in symbols
    assert "^GSPC" in symbols
    assert "^IXIC" in symbols

    for idx in indices:
        assert idx["price"] > 0
        assert isinstance(idx["change"], (int, float))
        assert isinstance(idx["change_pct"], (int, float))
        assert idx["currency"] in ("INR", "USD")


def test_market_indices_caching():
    """Verify repeated call to /api/market/indices returns cached data with is_cached=True."""
    # First call
    res1 = client.get("/api/market/indices")
    assert res1.status_code == 200

    # Second call should be served from memory cache
    res2 = client.get("/api/market/indices")
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["is_cached"] is True
