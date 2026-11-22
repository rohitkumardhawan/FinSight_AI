import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.services.news_engine import get_company_news, _NEWS_CACHE

client = TestClient(app)


def test_get_company_news_structure():
    """Verify news endpoint returns 200 and standard schema."""
    response = client.get("/api/companies/ASIANPAINT.NS/news?limit=5")
    assert response.status_code == 200
    data = response.json()
    assert data["symbol"] == "ASIANPAINT.NS"
    assert "news" in data
    assert isinstance(data["news"], list)
    assert "count" in data
    assert "is_cached" in data

    if data["news"]:
        first = data["news"][0]
        assert "title" in first
        assert "publisher" in first
        assert "link" in first
        assert "published_at" in first
        assert first["title"] != ""
        assert first["link"].startswith("http")


def test_news_in_memory_cache():
    """Verify that subsequent calls within cache TTL return is_cached = True."""
    # Ensure cache has entry
    get_company_news("AAPL", limit=3)
    response = client.get("/api/companies/AAPL/news?limit=3")
    assert response.status_code == 200
    data = response.json()
    assert data["symbol"] == "AAPL"
    assert data["is_cached"] is True


def test_news_graceful_fallback():
    """Verify that nonexistent or malformed tickers return an empty list gracefully without 500."""
    response = client.get("/api/companies/INVALID_TICKER_9999_XYZ/news")
    assert response.status_code == 200
    data = response.json()
    assert data["symbol"] == "INVALID_TICKER_9999_XYZ"
    assert isinstance(data["news"], list)
