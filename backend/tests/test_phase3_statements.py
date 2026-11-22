"""
FinSight AI — Phase 3 Financial Statements & Ratio Engine Tests
==============================================================
Validates:
- Pure-Python financial ratio math formulas
- Safe missing value handling (never converts missing to 0.0)
- Division by zero safeguards
- CSV parser, template generator, and column validation
- Duplicate record detection
- Live Neon database persistence and atomic transactions
- Automatic ratio calculation upon statement import
- Trend analysis endpoint
"""

import pytest
from decimal import Decimal
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.financial.metrics import (
    calculate_gross_margin,
    calculate_operating_margin,
    calculate_net_margin,
    calculate_roe,
    calculate_roa,
    calculate_current_ratio,
    calculate_quick_ratio,
    calculate_debt_to_equity,
    calculate_all_ratios
)
from app.services.csv_service import get_template_csv, parse_and_validate_csv
from app.db.session import SessionLocal


# -------------------------------------------------------------
# 1. Financial Ratio Formulas & Mathematical Edge Cases
# -------------------------------------------------------------

def test_profitability_ratio_formulas():
    """Verify gross, operating, net margins, ROE, and ROA."""
    # Gross Margin: (100 - 40) / 100 = 60% -> 0.6000
    assert calculate_gross_margin(100.0, 40.0, as_percentage=False) == 0.6000
    assert calculate_gross_margin(100.0, 40.0, as_percentage=True) == 60.0

    # Operating Margin: 30 / 100 = 30% -> 0.3000
    assert calculate_operating_margin(30.0, 100.0, as_percentage=False) == 0.3000
    assert calculate_operating_margin(30.0, 100.0, as_percentage=True) == 30.0

    # Net Margin: 25 / 100 = 25% -> 0.2500
    assert calculate_net_margin(25.0, 100.0, as_percentage=False) == 0.2500
    assert calculate_net_margin(25.0, 100.0, as_percentage=True) == 25.0

    # ROE: 25 / 50 = 50% -> 0.5000
    assert calculate_roe(25.0, 50.0, as_percentage=False) == 0.5000

    # ROA: 25 / 200 = 12.5% -> 0.1250
    assert calculate_roa(25.0, 200.0, as_percentage=False) == 0.1250


def test_liquidity_and_leverage_ratio_formulas():
    """Verify Current Ratio, Quick Ratio, and Debt-to-Equity."""
    # Current Ratio: 150 / 100 = 1.5000
    assert calculate_current_ratio(150.0, 100.0) == 1.5000

    # Quick Ratio: (150 - 30) / 100 = 1.2000
    assert calculate_quick_ratio(current_assets=150.0, inventory=30.0, current_liabilities=100.0) == 1.2000

    # Quick Ratio fallback to cash: 80 / 100 = 0.8000
    assert calculate_quick_ratio(current_assets=None, current_liabilities=100.0, cash_and_equivalents=80.0) == 0.8000

    # Debt-to-Equity: 80 / 100 = 0.8000
    assert calculate_debt_to_equity(80.0, 100.0) == 0.8000


def test_division_by_zero_and_missing_values_protection():
    """Strict Rule: Never convert missing values to 0.0, never crash on zero denominator."""
    # Missing values must return None
    assert calculate_gross_margin(None, 40.0) is None
    assert calculate_gross_margin(100.0, None) is None
    assert calculate_operating_margin(None, 100.0) is None
    assert calculate_roe(25.0, None) is None
    assert calculate_current_ratio(None, 100.0) is None
    assert calculate_debt_to_equity(None, 50.0) is None

    # Zero or negative revenue denominator
    assert calculate_gross_margin(0.0, 40.0) is None
    assert calculate_gross_margin(-10.0, 40.0) is None
    assert calculate_operating_margin(20.0, 0.0) is None

    # Zero liabilities / equity denominator
    assert calculate_current_ratio(100.0, 0.0) is None
    assert calculate_quick_ratio(current_assets=100.0, current_liabilities=0.0) is None
    assert calculate_debt_to_equity(50.0, 0.0) is None
    assert calculate_roe(50.0, 0.0) is None


def test_calculate_all_ratios_engine():
    """Verifies aggregate ratio computation engine with Decimals."""
    stmt = {
        "revenue": Decimal("200000.00"),
        "cost_of_revenue": Decimal("80000.00"),
        "gross_profit": Decimal("120000.00"),
        "operating_income": Decimal("60000.00"),
        "net_income": Decimal("48000.00"),
        "total_assets": Decimal("300000.00"),
        "current_assets": Decimal("120000.00"),
        "total_liabilities": Decimal("100000.00"),
        "current_liabilities": Decimal("60000.00"),
        "total_equity": Decimal("200000.00"),
        "cash_and_equivalents": Decimal("40000.00"),
        "inventory": Decimal("20000.00"),
        "total_debt": Decimal("50000.00")
    }
    ratios = calculate_all_ratios(stmt)
    assert ratios["gross_margin"] == 0.6000
    assert ratios["operating_margin"] == 0.3000
    assert ratios["net_profit_margin"] == 0.2400
    assert ratios["return_on_equity"] == 0.2400
    assert ratios["return_on_assets"] == 0.1600
    assert ratios["current_ratio"] == 2.0000
    assert ratios["quick_ratio"] == 1.6667
    assert ratios["debt_to_equity"] == 0.2500


# -------------------------------------------------------------
# 2. CSV Parsing & Validation Tests
# -------------------------------------------------------------

def test_csv_template_generator():
    """Verify templates contain expected column headers."""
    inc_tmpl = get_template_csv("income_statement")
    assert "revenue" in inc_tmpl
    assert "fiscal_year" in inc_tmpl
    assert "cost_of_revenue" in inc_tmpl

    bal_tmpl = get_template_csv("balance_sheet")
    assert "total_assets" in bal_tmpl
    assert "current_assets" in bal_tmpl

    cf_tmpl = get_template_csv("cash_flow")
    assert "operating_cash_flow" in cf_tmpl


def test_csv_validation_and_duplicate_detection():
    """Verify CSV validation handles missing columns, invalid numbers, and duplicate detection."""
    db = SessionLocal()
    try:
        # Invalid CSV: missing required headers
        invalid_csv = "revenue,net_income\n100,50"
        result = parse_and_validate_csv(invalid_csv, company_id=1, db=db)
        assert result["success"] is False
        assert any("Required header" in err for err in result["errors"])

        # Ensure AAPL 2024 FY statement exists for duplicate detection test
        from app.models.financial_statement import FinancialStatement
        from sqlalchemy import select
        existing_stmt = db.execute(
            select(FinancialStatement).where(
                FinancialStatement.company_id == 1,
                FinancialStatement.fiscal_year == 2024,
                FinancialStatement.fiscal_period == "FY"
            )
        ).scalar_one_or_none()
        if not existing_stmt:
            db.add(FinancialStatement(
                company_id=1,
                fiscal_year=2024,
                fiscal_period="FY",
                statement_type="income",
                revenue=Decimal("391035.00"),
                net_income=Decimal("101200.00")
            ))
            db.commit()

        # Valid CSV with existing period (AAPL 2024 FY was seeded, so it's a duplicate)
        csv_with_dup = (
            "fiscal_year,fiscal_period,revenue,net_income,source\n"
            "2024,FY,391035.00,101200.00,SEC 10-K\n"
            "2099,FY,999999.00,500000.00,SEC Future Forecast"
        )
        res_dup = parse_and_validate_csv(csv_with_dup, company_id=1, db=db)
        assert res_dup["total_rows"] == 2
        assert res_dup["valid_rows_count"] == 2
        assert res_dup["duplicates_count"] == 1
        assert res_dup["preview_rows"][0]["is_duplicate"] is True
        assert res_dup["preview_rows"][1]["is_duplicate"] is False
    finally:
        db.close()


# -------------------------------------------------------------
# 3. Backend Endpoints Integration Tests (Async)
# -------------------------------------------------------------

@pytest.mark.anyio
async def test_csv_preview_and_import_workflow():
    """
    Tests complete workflow:
    1. Upload CSV to preview endpoint
    2. Confirm preview rows
    3. Import to Neon DB
    4. Verify automatic ratio calculation
    5. Query trends endpoint
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Download Template
        tmpl_res = await client.get("/api/statements/csv-template?type=combined")
        assert tmpl_res.status_code == 200
        assert "fiscal_year" in tmpl_res.text

        # 2. Preview CSV Upload
        test_year = 2088
        csv_payload = {
            "csv_text": (
                "fiscal_year,fiscal_period,statement_type,revenue,cost_of_revenue,gross_profit,operating_income,net_income,total_assets,current_assets,total_liabilities,current_liabilities,total_equity,cash_and_equivalents,inventory,total_debt,source\n"
                f"{test_year},FY,annual_combined,500000.00,200000.00,300000.00,150000.00,120000.00,800000.00,300000.00,300000.00,150000.00,500000.00,100000.00,50000.00,100000.00,Phase3 CSV Integration Test"
            )
        }
        preview_res = await client.post("/api/companies/1/statements/csv-preview", json=csv_payload)
        assert preview_res.status_code == 200
        preview_data = preview_res.json()
        assert preview_data["success"] is True
        assert preview_data["total_rows"] == 1
        assert preview_data["valid_rows_count"] == 1

        # 3. Execute CSV Import
        import_payload = {
            "preview_rows": preview_data["preview_rows"],
            "overwrite_duplicates": True
        }
        import_res = await client.post("/api/companies/1/statements/csv-import", json=import_payload)
        assert import_res.status_code == 200
        import_info = import_res.json()
        assert import_info["success"] is True
        assert import_info["calculated_ratios"] >= 1

        # 4. Verify Statement was saved in DB
        stmts_res = await client.get(f"/api/companies/1/statements?year={test_year}")
        assert stmts_res.status_code == 200
        stmts = stmts_res.json()
        assert len(stmts) >= 1
        assert float(stmts[0]["revenue"]) == 500000.00
        statement_id = stmts[0]["id"]

        # 5. Verify Automatic Financial Ratios in DB
        ratios_res = await client.get("/api/companies/1/ratios")
        assert ratios_res.status_code == 200
        ratios_list = ratios_res.json()
        matched_ratio = next((r for r in ratios_list if r["fiscal_year"] == test_year), None)
        assert matched_ratio is not None
        assert float(matched_ratio["gross_margin"]) == 0.6000
        assert float(matched_ratio["operating_margin"]) == 0.3000
        assert float(matched_ratio["net_profit_margin"]) == 0.2400
        assert float(matched_ratio["current_ratio"]) == 2.0000

        # 6. Verify Financial Trends Endpoint
        trends_res = await client.get("/api/companies/1/financial-trends")
        assert trends_res.status_code == 200
        trends_data = trends_res.json()
        assert "trends" in trends_data
        assert any(t["fiscal_year"] == test_year for t in trends_data["trends"])

        # 7. Clean up test record
        del_res = await client.delete(f"/api/statements/{statement_id}")
        assert del_res.status_code == 204
