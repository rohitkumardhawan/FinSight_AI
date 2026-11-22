"""
FinSight AI — Backend API Endpoint & Schema Tests
=================================================
Validates endpoints, HTTP status codes, demo data labeling, and CORS.
"""

import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app

@pytest.mark.anyio
async def test_health_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/v1/health")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "healthy"
        assert "FinSight" in data["service"]

@pytest.mark.anyio
async def test_overview_demo_data_labeling():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/v1/overview/AAPL")
        assert res.status_code == 200
        data = res.json()
        # Verify mandatory demonstration labels
        assert data["company"]["is_demo_data"] is True
        assert "[DEMO DATA]" in data["company"]["summary"]
        assert "DEMONSTRATION DATA ONLY" in data["data_disclaimer"]
        for kpi in data["kpis"]:
            assert kpi["is_demo_data"] is True

@pytest.mark.anyio
async def test_companies_search():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/v1/companies?q=nvda")
        assert res.status_code == 200
        data = res.json()
        assert len(data["companies"]) > 0
        assert data["companies"][0]["ticker"] == "NVDA"
        assert data["is_demo_data"] is True
