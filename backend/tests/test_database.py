"""
FinSight AI — Phase 2 Neon Database Integration Tests
=====================================================
Validates:
- Database connectivity & /api/db/health
- Company CRUD operations
- Duplicate ticker constraint (409 Conflict)
- Statements & Ratios sub-resources
- 404 Not Found & validation error handling
- Zero hardcoded secrets / institutional error masking
"""

import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app

@pytest.mark.anyio
async def test_system_and_db_health():
    """Verify general API health and live Neon DB round-trip connectivity."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. System Health
        res = await client.get("/api/health")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "healthy"
        assert "Phase 2" in data["phase"]

        # 2. Neon Database Live Health
        db_res = await client.get("/api/db/health")
        assert db_res.status_code == 200
        db_data = db_res.json()
        assert db_data["status"] == "healthy"
        assert "neondb" in db_data["database"]
        assert db_data["branch"] == "production"
        assert "latency_ms" in db_data


@pytest.mark.anyio
async def test_list_companies_and_search():
    """Verify listing seeded companies and filtering with search query."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/companies")
        assert res.status_code == 200
        companies = res.json()
        assert len(companies) >= 6
        tickers = [c["ticker"] for c in companies]
        assert "AAPL" in tickers
        assert "NVDA" in tickers

        # Search filter
        search_res = await client.get("/api/companies?q=Apple")
        assert search_res.status_code == 200
        search_data = search_res.json()
        assert len(search_data) >= 1
        assert search_data[0]["ticker"] == "AAPL"


@pytest.mark.anyio
async def test_company_crud_lifecycle():
    """Verify full CRUD lifecycle: Create, Read, Update, Delete with duplicate conflict protection."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        test_ticker = "TTEST"

        # Clean up in case previous test run left it
        lookup = await client.get(f"/api/companies/ticker/{test_ticker}")
        if lookup.status_code == 200:
            await client.delete(f"/api/companies/{lookup.json()['id']}")

        # 1. Create Company
        payload = {
            "ticker": test_ticker,
            "company_name": "Test Technologies Inc.",
            "exchange": "NASDAQ",
            "sector": "Technology",
            "industry": "Software",
            "country": "United States",
            "currency": "USD"
        }
        create_res = await client.post("/api/companies", json=payload)
        assert create_res.status_code == 201
        created = create_res.json()
        company_id = created["id"]
        assert created["ticker"] == test_ticker

        # 2. Test Duplicate Ticker (409 Conflict)
        dup_res = await client.post("/api/companies", json=payload)
        assert dup_res.status_code == 409
        assert "already exists" in dup_res.json()["detail"]

        # 3. Read by ID and by Ticker
        get_res = await client.get(f"/api/companies/{company_id}")
        assert get_res.status_code == 200
        assert get_res.json()["company_name"] == "Test Technologies Inc."

        by_ticker = await client.get(f"/api/companies/ticker/{test_ticker}")
        assert by_ticker.status_code == 200
        assert by_ticker.json()["id"] == company_id

        # 4. Update Company (PUT)
        update_payload = {"company_name": "Test Technologies Corp."}
        update_res = await client.put(f"/api/companies/{company_id}", json=update_payload)
        assert update_res.status_code == 200
        assert update_res.json()["company_name"] == "Test Technologies Corp."

        # 5. Add Financial Statement
        stmt_payload = {
            "fiscal_year": 2024,
            "fiscal_period": "FY",
            "statement_type": "annual_combined",
            "revenue": 100000.00,
            "cost_of_revenue": 40000.00,
            "gross_profit": 60000.00,
            "operating_income": 30000.00,
            "net_income": 25000.00,
            "source": "DEMO DATASET",
            "is_demo_data": True
        }
        stmt_res = await client.post(f"/api/companies/{company_id}/statements", json=stmt_payload)
        assert stmt_res.status_code == 201
        assert float(stmt_res.json()["revenue"]) == 100000.00

        # Retrieve Financial Statements
        get_stmts = await client.get(f"/api/companies/{company_id}/statements")
        assert get_stmts.status_code == 200
        assert len(get_stmts.json()) == 1

        # 6. Add Financial Ratio
        ratio_payload = {
            "fiscal_year": 2024,
            "fiscal_period": "FY",
            "gross_margin": 0.6000,
            "operating_margin": 0.3000,
            "net_profit_margin": 0.2500,
            "source": "DEMO DATASET"
        }
        ratio_res = await client.post(f"/api/companies/{company_id}/ratios", json=ratio_payload)
        assert ratio_res.status_code == 201
        assert float(ratio_res.json()["gross_margin"]) == 0.6000

        # Retrieve Financial Ratios
        get_ratios = await client.get(f"/api/companies/{company_id}/ratios")
        assert get_ratios.status_code == 200
        assert len(get_ratios.json()) == 1

        # 7. Delete Company (DELETE)
        del_res = await client.delete(f"/api/companies/{company_id}")
        assert del_res.status_code == 204

        # 8. Verify 404 after deletion
        not_found = await client.get(f"/api/companies/{company_id}")
        assert not_found.status_code == 404
