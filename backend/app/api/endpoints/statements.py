"""
FinSight AI — Financial Statements & CSV Import Endpoints
=========================================================
Endpoints:
- GET /api/statements/csv-template
- POST /api/companies/{company_id}/statements/csv-preview
- POST /api/companies/{company_id}/statements/csv-import
- PUT /api/statements/{statement_id}
- DELETE /api/statements/{statement_id}
- POST /api/companies/{company_id}/ratios/recalculate
- GET /api/companies/{company_id}/financial-trends
"""

from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Body, Response, Request, status
from sqlalchemy.orm import Session
from sqlalchemy import select, desc
from app.db.session import get_db
from app.models.company import Company
from app.models.financial_statement import FinancialStatement
from app.models.financial_ratio import FinancialRatio
from app.schemas.statement import FinancialStatementCreate, FinancialStatementUpdate, FinancialStatementResponse
from app.schemas.ratio import FinancialRatioResponse
from app.services.csv_service import get_template_csv, parse_and_validate_csv, import_financial_statements
from app.financial.metrics import calculate_all_ratios
from decimal import Decimal

router = APIRouter(tags=["Financial Statements & CSV Engine"])


@router.get("/statements/csv-template")
def download_csv_template(
    type: str = Query("combined", description="income_statement, balance_sheet, cash_flow, or combined")
):
    """Returns downloadable CSV template content with standard column headers and sample data."""
    csv_content = get_template_csv(type)
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=finsight_{type}_template.csv"}
    )


@router.post("/companies/{company_id}/statements/csv-preview")
async def preview_csv_upload(
    company_id: int,
    request: Request,
    default_statement_type: str = Query("annual_combined"),
    db: Session = Depends(get_db)
):
    """
    Parses and validates a CSV financial statement file without writing to the database.
    Accepts multipart/form-data (file upload), application/json (csv_text), or raw text.
    Checks column validity, numerical formats, and flags existing duplicate periods.
    """
    company = db.get(Company, company_id)
    if not company:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Company with ID {company_id} not found.")

    csv_text = ""
    content_type = request.headers.get("content-type", "")

    if "multipart/form-data" in content_type:
        form = await request.form()
        uploaded_file = form.get("file")
        if uploaded_file and hasattr(uploaded_file, "read"):
            content = await uploaded_file.read()
            csv_text = content.decode("utf-8-sig", errors="replace")
        elif "raw_csv" in form:
            csv_text = str(form["raw_csv"])
    elif "application/json" in content_type:
        try:
            body = await request.json()
            csv_text = body.get("csv_text", "") or body.get("raw_csv", "")
            if "default_statement_type" in body:
                default_statement_type = body["default_statement_type"]
        except Exception:
            pass
    else:
        # Raw text / csv
        raw_body = await request.body()
        csv_text = raw_body.decode("utf-8-sig", errors="replace")

    if not csv_text.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No CSV file or text payload provided.")

    result = parse_and_validate_csv(csv_text, company_id, db, default_statement_type)
    return result


@router.post("/companies/{company_id}/statements/csv-import")
async def execute_csv_import(
    company_id: int,
    payload: Dict[str, Any] = Body(...),
    db: Session = Depends(get_db)
):
    """
    Executes transaction-safe import of validated financial statement records.
    Automatically recalculates all financial ratios deterministically in pure Python.
    """
    company = db.get(Company, company_id)
    if not company:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Company with ID {company_id} not found.")

    preview_rows = payload.get("preview_rows", [])
    if not preview_rows:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No preview rows provided for import.")

    overwrite_duplicates = payload.get("overwrite_duplicates", True)

    try:
        import_result = import_financial_statements(
            company_id=company_id,
            preview_data=preview_rows,
            db=db,
            overwrite_duplicates=overwrite_duplicates
        )
        return import_result
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Import failed: {str(e)}")


@router.put("/statements/{statement_id}", response_model=FinancialStatementResponse)
def update_statement(
    statement_id: int,
    statement_in: FinancialStatementUpdate,
    db: Session = Depends(get_db)
):
    """Updates an individual financial statement line item and recalculates ratios for the period."""
    statement = db.get(FinancialStatement, statement_id)
    if not statement:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Statement with ID {statement_id} not found.")

    update_data = statement_in.model_dump(exclude_unset=True)
    for field, val in update_data.items():
        setattr(statement, field, val)

    db.flush()

    # Recalculate ratios for the updated period
    ratios = calculate_all_ratios({
        "revenue": statement.revenue,
        "cost_of_revenue": statement.cost_of_revenue,
        "gross_profit": statement.gross_profit,
        "operating_income": statement.operating_income,
        "net_income": statement.net_income,
        "total_assets": statement.total_assets,
        "current_assets": statement.current_assets,
        "total_liabilities": statement.total_liabilities,
        "current_liabilities": statement.current_liabilities,
        "total_equity": statement.total_equity,
        "cash_and_equivalents": statement.cash_and_equivalents,
        "inventory": statement.inventory,
        "total_debt": statement.total_debt
    })

    ratio_rec = db.execute(
        select(FinancialRatio).where(
            FinancialRatio.company_id == statement.company_id,
            FinancialRatio.fiscal_year == statement.fiscal_year,
            FinancialRatio.fiscal_period == statement.fiscal_period
        )
    ).scalar_one_or_none()

    if ratio_rec:
        for k, v in ratios.items():
            setattr(ratio_rec, k, Decimal(str(v)) if v is not None else None)
        ratio_rec.source = "Recalculated on statement edit"

    db.commit()
    db.refresh(statement)
    return statement


@router.delete("/statements/{statement_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_statement(
    statement_id: int,
    db: Session = Depends(get_db)
):
    """Deletes an individual financial statement record."""
    statement = db.get(FinancialStatement, statement_id)
    if not statement:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Statement with ID {statement_id} not found.")

    db.delete(statement)
    db.commit()
    return None


@router.post("/companies/{company_id}/ratios/recalculate")
def recalculate_company_ratios(
    company_id: int,
    db: Session = Depends(get_db)
):
    """
    Deterministically computes financial ratios from underlying financial statements
    for all historical periods of the given company.
    """
    company = db.get(Company, company_id)
    if not company:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Company with ID {company_id} not found.")

    statements = db.execute(
        select(FinancialStatement).where(FinancialStatement.company_id == company_id)
    ).scalars().all()

    recalculated_count = 0
    for stmt in statements:
        ratios = calculate_all_ratios({
            "revenue": stmt.revenue,
            "cost_of_revenue": stmt.cost_of_revenue,
            "gross_profit": stmt.gross_profit,
            "operating_income": stmt.operating_income,
            "net_income": stmt.net_income,
            "total_assets": stmt.total_assets,
            "current_assets": stmt.current_assets,
            "total_liabilities": stmt.total_liabilities,
            "current_liabilities": stmt.current_liabilities,
            "total_equity": stmt.total_equity,
            "cash_and_equivalents": stmt.cash_and_equivalents,
            "inventory": stmt.inventory,
            "total_debt": stmt.total_debt
        })

        ratio_rec = db.execute(
            select(FinancialRatio).where(
                FinancialRatio.company_id == company_id,
                FinancialRatio.fiscal_year == stmt.fiscal_year,
                FinancialRatio.fiscal_period == stmt.fiscal_period
            )
        ).scalar_one_or_none()

        if ratio_rec:
            for k, v in ratios.items():
                setattr(ratio_rec, k, Decimal(str(v)) if v is not None else None)
        else:
            ratio_rec = FinancialRatio(
                company_id=company_id,
                fiscal_year=stmt.fiscal_year,
                fiscal_period=stmt.fiscal_period,
                gross_margin=Decimal(str(ratios["gross_margin"])) if ratios["gross_margin"] is not None else None,
                operating_margin=Decimal(str(ratios["operating_margin"])) if ratios["operating_margin"] is not None else None,
                net_profit_margin=Decimal(str(ratios["net_profit_margin"])) if ratios["net_profit_margin"] is not None else None,
                current_ratio=Decimal(str(ratios["current_ratio"])) if ratios["current_ratio"] is not None else None,
                quick_ratio=Decimal(str(ratios["quick_ratio"])) if ratios["quick_ratio"] is not None else None,
                debt_to_equity=Decimal(str(ratios["debt_to_equity"])) if ratios["debt_to_equity"] is not None else None,
                return_on_equity=Decimal(str(ratios["return_on_equity"])) if ratios["return_on_equity"] is not None else None,
                return_on_assets=Decimal(str(ratios["return_on_assets"])) if ratios["return_on_assets"] is not None else None,
                source="FinSight Engine Recalculation"
            )
            db.add(ratio_rec)

        recalculated_count += 1

    db.commit()
    return {
        "success": True,
        "company_id": company_id,
        "periods_recalculated": recalculated_count
    }


@router.get("/companies/{company_id}/financial-trends")
def get_financial_trends(
    company_id: int,
    db: Session = Depends(get_db)
):
    """
    Returns time-series trend analysis across revenue, profitability margins,
    and leverage for institutional multi-year comparison.
    """
    company = db.get(Company, company_id)
    if not company:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Company with ID {company_id} not found.")

    statements = db.execute(
        select(FinancialStatement)
        .where(FinancialStatement.company_id == company_id)
        .order_by(FinancialStatement.fiscal_year.asc(), FinancialStatement.fiscal_period.asc())
    ).scalars().all()

    ratios = db.execute(
        select(FinancialRatio)
        .where(FinancialRatio.company_id == company_id)
        .order_by(FinancialRatio.fiscal_year.asc(), FinancialRatio.fiscal_period.asc())
    ).scalars().all()

    ratio_map = {(r.fiscal_year, r.fiscal_period): r for r in ratios}

    trends = []
    for s in statements:
        period_key = (s.fiscal_year, s.fiscal_period)
        r = ratio_map.get(period_key)

        trends.append({
            "period": f"{s.fiscal_period}{str(s.fiscal_year)[-2:]}" if s.fiscal_period != "FY" else f"FY{str(s.fiscal_year)[-2:]}",
            "fiscal_year": s.fiscal_year,
            "fiscal_period": s.fiscal_period,
            "revenue": float(s.revenue) if s.revenue is not None else None,
            "gross_profit": float(s.gross_profit) if s.gross_profit is not None else None,
            "operating_income": float(s.operating_income) if s.operating_income is not None else None,
            "net_income": float(s.net_income) if s.net_income is not None else None,
            "free_cash_flow": float(s.free_cash_flow) if s.free_cash_flow is not None else None,
            "gross_margin": float(r.gross_margin) if r and r.gross_margin is not None else None,
            "operating_margin": float(r.operating_margin) if r and r.operating_margin is not None else None,
            "net_profit_margin": float(r.net_profit_margin) if r and r.net_profit_margin is not None else None,
            "current_ratio": float(r.current_ratio) if r and r.current_ratio is not None else None,
            "quick_ratio": float(r.quick_ratio) if r and r.quick_ratio is not None else None,
            "debt_to_equity": float(r.debt_to_equity) if r and r.debt_to_equity is not None else None,
            "return_on_equity": float(r.return_on_equity) if r and r.return_on_equity is not None else None,
            "return_on_assets": float(r.return_on_assets) if r and r.return_on_assets is not None else None,
            "is_demo_data": s.is_demo_data
        })

    return {
        "company": {
            "id": company.id,
            "ticker": company.ticker,
            "company_name": company.company_name,
            "currency": company.currency
        },
        "trends": trends
    }
