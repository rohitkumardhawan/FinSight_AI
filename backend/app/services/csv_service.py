"""
FinSight AI — CSV Financial Statement Import & Validation Service
================================================================
Processes and validates uploaded financial statements (Income Statement,
Balance Sheet, Cash Flow Statement, or Combined).
Strict rules:
1. Never silently replaces missing financial values with zero.
2. Detects duplicate records.
3. Automatically triggers pure-Python financial ratio calculation.
4. Executes within a database transaction with safe rollback.
"""

import csv
import io
from decimal import Decimal, InvalidOperation
from typing import Dict, List, Any, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.models.company import Company
from app.models.financial_statement import FinancialStatement
from app.models.financial_ratio import FinancialRatio
from app.financial.metrics import calculate_all_ratios

CSV_TEMPLATES = {
    "income_statement": [
        "fiscal_year", "fiscal_period", "revenue", "cost_of_revenue",
        "gross_profit", "operating_income", "ebit", "net_income", "source"
    ],
    "balance_sheet": [
        "fiscal_year", "fiscal_period", "total_assets", "current_assets",
        "total_liabilities", "current_liabilities", "total_equity",
        "cash_and_equivalents", "inventory", "total_debt", "source"
    ],
    "cash_flow": [
        "fiscal_year", "fiscal_period", "operating_cash_flow",
        "capital_expenditure", "free_cash_flow", "depreciation_amortization", "source"
    ],
    "combined": [
        "fiscal_year", "fiscal_period", "statement_type", "revenue", "cost_of_revenue",
        "gross_profit", "operating_income", "ebit", "net_income",
        "total_assets", "current_assets", "total_liabilities", "current_liabilities",
        "total_equity", "cash_and_equivalents", "inventory", "total_debt",
        "operating_cash_flow", "capital_expenditure", "free_cash_flow",
        "depreciation_amortization", "source"
    ]
}

SAMPLE_DATA = {
    "income_statement": [
        "fiscal_year,fiscal_period,revenue,cost_of_revenue,gross_profit,operating_income,ebit,net_income,source",
        "2024,FY,125000.00,55000.00,70000.00,42000.00,42000.00,35000.00,SEC 10-K",
        "2025,FY,145000.00,62000.00,83000.00,51000.00,51000.00,43000.00,SEC 10-K"
    ],
    "balance_sheet": [
        "fiscal_year,fiscal_period,total_assets,current_assets,total_liabilities,current_liabilities,total_equity,cash_and_equivalents,inventory,total_debt,source",
        "2024,FY,180000.00,65000.00,80000.00,35000.00,100000.00,28000.00,12000.00,45000.00,SEC 10-K",
        "2025,FY,210000.00,78000.00,88000.00,38000.00,122000.00,35000.00,14000.00,42000.00,SEC 10-K"
    ],
    "cash_flow": [
        "fiscal_year,fiscal_period,operating_cash_flow,capital_expenditure,free_cash_flow,depreciation_amortization,source",
        "2024,FY,48000.00,12000.00,36000.00,6500.00,SEC 10-K",
        "2025,FY,56000.00,14000.00,42000.00,7200.00,SEC 10-K"
    ],
    "combined": [
        "fiscal_year,fiscal_period,statement_type,revenue,cost_of_revenue,gross_profit,operating_income,ebit,net_income,total_assets,current_assets,total_liabilities,current_liabilities,total_equity,cash_and_equivalents,inventory,total_debt,operating_cash_flow,capital_expenditure,free_cash_flow,depreciation_amortization,source",
        "2024,FY,annual_combined,125000.00,55000.00,70000.00,42000.00,42000.00,35000.00,180000.00,65000.00,80000.00,35000.00,100000.00,28000.00,12000.00,45000.00,48000.00,12000.00,36000.00,6500.00,SEC EDGAR",
        "2025,FY,annual_combined,145000.00,62000.00,83000.00,51000.00,51000.00,43000.00,210000.00,78000.00,88000.00,38000.00,122000.00,35000.00,14000.00,42000.00,56000.00,14000.00,42000.00,7200.00,SEC EDGAR"
    ]
}

NUMERIC_FIELDS = {
    "revenue", "cost_of_revenue", "gross_profit", "operating_income", "ebit", "net_income",
    "total_assets", "current_assets", "total_liabilities", "current_liabilities",
    "total_equity", "cash_and_equivalents", "inventory", "total_debt",
    "operating_cash_flow", "capital_expenditure", "free_cash_flow", "depreciation_amortization"
}


def get_template_csv(statement_type: str = "combined") -> str:
    """Returns sample CSV template content for download."""
    stype = statement_type.lower()
    lines = SAMPLE_DATA.get(stype, SAMPLE_DATA["combined"])
    return "\n".join(lines)


def parse_and_validate_csv(
    csv_text: str,
    company_id: int,
    db: Session,
    default_statement_type: str = "annual_combined"
) -> Dict[str, Any]:
    """
    Parses and thoroughly validates CSV content.
    Returns preview data, validation messages, and duplicate flags.
    """
    reader = csv.DictReader(io.StringIO(csv_text.strip()))
    if not reader.fieldnames:
        return {
            "success": False,
            "errors": ["Uploaded file is empty or missing CSV header row."],
            "preview_rows": [],
            "total_rows": 0,
            "valid_rows_count": 0,
            "duplicates_count": 0
        }

    # Normalize headers
    normalized_headers = [h.strip().lower() for h in reader.fieldnames]
    if "fiscal_year" not in normalized_headers or "fiscal_period" not in normalized_headers:
        return {
            "success": False,
            "errors": ["Required header columns missing: 'fiscal_year' and 'fiscal_period' must be present."],
            "preview_rows": [],
            "total_rows": 0,
            "valid_rows_count": 0,
            "duplicates_count": 0
        }

    preview_rows = []
    errors = []
    valid_count = 0
    duplicate_count = 0

    for idx, raw_row in enumerate(reader, start=1):
        row = {k.strip().lower(): (v.strip() if v else "") for k, v in raw_row.items() if k}
        row_errors = []

        # 1. Validate Fiscal Year
        year_str = row.get("fiscal_year", "")
        fiscal_year = None
        try:
            fiscal_year = int(year_str)
            if fiscal_year < 1900 or fiscal_year > 2100:
                row_errors.append(f"Row {idx}: fiscal_year {year_str} out of reasonable range (1900-2100).")
        except ValueError:
            row_errors.append(f"Row {idx}: Invalid fiscal_year '{year_str}'. Must be an integer.")

        # 2. Validate Fiscal Period
        fiscal_period = row.get("fiscal_period", "").upper()
        if not fiscal_period or fiscal_period not in ["FY", "Q1", "Q2", "Q3", "Q4", "H1", "H2", "TTM"]:
            row_errors.append(f"Row {idx}: Invalid fiscal_period '{fiscal_period}'. Expected FY, Q1, Q2, Q3, or Q4.")

        # Statement type
        statement_type = row.get("statement_type", "").lower() or default_statement_type

        # 3. Validate Numeric Fields (None if empty string — NEVER convert to 0.0)
        parsed_fields = {}
        for field in NUMERIC_FIELDS:
            raw_val = row.get(field, "")
            if raw_val == "":
                parsed_fields[field] = None
            else:
                # Remove commas, currency symbols, and whitespace
                clean_val = raw_val.replace("$", "").replace(",", "").replace("%", "").strip()
                try:
                    parsed_fields[field] = Decimal(clean_val)
                except InvalidOperation:
                    row_errors.append(f"Row {idx}: Invalid numeric format for '{field}': '{raw_val}'.")
                    parsed_fields[field] = None

        # 4. Check for duplicate record in database
        is_duplicate = False
        if fiscal_year and fiscal_period:
            existing = db.execute(
                select(FinancialStatement).where(
                    FinancialStatement.company_id == company_id,
                    FinancialStatement.fiscal_year == fiscal_year,
                    FinancialStatement.fiscal_period == fiscal_period
                )
            ).scalar_one_or_none()
            if not existing:
                from app.models.dataset import FinancialPeriod
                existing = db.execute(
                    select(FinancialPeriod).where(
                        FinancialPeriod.company_id == company_id,
                        FinancialPeriod.fiscal_year == fiscal_year,
                        FinancialPeriod.fiscal_period == fiscal_period
                    )
                ).scalar_one_or_none()
            if existing:
                is_duplicate = True
                duplicate_count += 1

        is_valid = len(row_errors) == 0
        if is_valid:
            valid_count += 1
        errors.extend(row_errors)

        preview_rows.append({
            "row_number": idx,
            "fiscal_year": fiscal_year,
            "fiscal_period": fiscal_period,
            "statement_type": statement_type,
            "data": parsed_fields,
            "source": row.get("source", "CSV Import"),
            "is_duplicate": is_duplicate,
            "is_valid": is_valid,
            "errors": row_errors
        })

    return {
        "success": len(errors) == 0,
        "total_rows": len(preview_rows),
        "valid_rows_count": valid_count,
        "duplicates_count": duplicate_count,
        "errors": errors,
        "preview_rows": preview_rows
    }


def import_financial_statements(
    company_id: int,
    preview_data: List[Dict[str, Any]],
    db: Session,
    overwrite_duplicates: bool = True
) -> Dict[str, Any]:
    """
    Executes statement insertion and ratio recalculation within a database transaction.
    Rolls back automatically on any error.
    """
    company = db.get(Company, company_id)
    if not company:
        raise ValueError(f"Company ID {company_id} does not exist.")

    imported_count = 0
    updated_count = 0
    calculated_ratios_count = 0

    try:
        for item in preview_data:
            if not item.get("is_valid", True):
                continue

            fiscal_year = item["fiscal_year"]
            fiscal_period = item["fiscal_period"]
            data = item["data"]
            statement_type = item.get("statement_type", "annual_combined")
            source = item.get("source", "CSV Import")

            # Check if record exists
            stmt = select(FinancialStatement).where(
                FinancialStatement.company_id == company_id,
                FinancialStatement.fiscal_year == fiscal_year,
                FinancialStatement.fiscal_period == fiscal_period
            )
            existing_statement = db.execute(stmt).scalar_one_or_none()

            if existing_statement:
                if not overwrite_duplicates:
                    continue
                # Update existing record
                existing_statement.statement_type = statement_type
                existing_statement.source = source
                existing_statement.is_demo_data = True
                for field, val in data.items():
                    setattr(existing_statement, field, val)
                target_statement = existing_statement
                updated_count += 1
            else:
                # Insert new statement
                new_statement = FinancialStatement(
                    company_id=company_id,
                    fiscal_year=fiscal_year,
                    fiscal_period=fiscal_period,
                    statement_type=statement_type,
                    source=source,
                    is_demo_data=True,
                    **data
                )
                db.add(new_statement)
                db.flush()
                target_statement = new_statement
                imported_count += 1

            # Automatically recalculate financial ratios for this period
            ratios_dict = calculate_all_ratios({
                "revenue": target_statement.revenue,
                "cost_of_revenue": target_statement.cost_of_revenue,
                "gross_profit": target_statement.gross_profit,
                "operating_income": target_statement.operating_income,
                "net_income": target_statement.net_income,
                "total_assets": target_statement.total_assets,
                "current_assets": target_statement.current_assets,
                "total_liabilities": target_statement.total_liabilities,
                "current_liabilities": target_statement.current_liabilities,
                "total_equity": target_statement.total_equity,
                "cash_and_equivalents": target_statement.cash_and_equivalents,
                "inventory": target_statement.inventory,
                "total_debt": target_statement.total_debt
            })

            # Check if ratio record exists
            ratio_stmt = select(FinancialRatio).where(
                FinancialRatio.company_id == company_id,
                FinancialRatio.fiscal_year == fiscal_year,
                FinancialRatio.fiscal_period == fiscal_period
            )
            existing_ratio = db.execute(ratio_stmt).scalar_one_or_none()

            if existing_ratio:
                existing_ratio.gross_margin = Decimal(str(ratios_dict["gross_margin"])) if ratios_dict["gross_margin"] is not None else None
                existing_ratio.operating_margin = Decimal(str(ratios_dict["operating_margin"])) if ratios_dict["operating_margin"] is not None else None
                existing_ratio.net_profit_margin = Decimal(str(ratios_dict["net_profit_margin"])) if ratios_dict["net_profit_margin"] is not None else None
                existing_ratio.current_ratio = Decimal(str(ratios_dict["current_ratio"])) if ratios_dict["current_ratio"] is not None else None
                existing_ratio.quick_ratio = Decimal(str(ratios_dict["quick_ratio"])) if ratios_dict["quick_ratio"] is not None else None
                existing_ratio.debt_to_equity = Decimal(str(ratios_dict["debt_to_equity"])) if ratios_dict["debt_to_equity"] is not None else None
                existing_ratio.return_on_equity = Decimal(str(ratios_dict["return_on_equity"])) if ratios_dict["return_on_equity"] is not None else None
                existing_ratio.return_on_assets = Decimal(str(ratios_dict["return_on_assets"])) if ratios_dict["return_on_assets"] is not None else None
                existing_ratio.source = f"Auto-calculated ({source})"
            else:
                new_ratio = FinancialRatio(
                    company_id=company_id,
                    fiscal_year=fiscal_year,
                    fiscal_period=fiscal_period,
                    gross_margin=Decimal(str(ratios_dict["gross_margin"])) if ratios_dict["gross_margin"] is not None else None,
                    operating_margin=Decimal(str(ratios_dict["operating_margin"])) if ratios_dict["operating_margin"] is not None else None,
                    net_profit_margin=Decimal(str(ratios_dict["net_profit_margin"])) if ratios_dict["net_profit_margin"] is not None else None,
                    current_ratio=Decimal(str(ratios_dict["current_ratio"])) if ratios_dict["current_ratio"] is not None else None,
                    quick_ratio=Decimal(str(ratios_dict["quick_ratio"])) if ratios_dict["quick_ratio"] is not None else None,
                    debt_to_equity=Decimal(str(ratios_dict["debt_to_equity"])) if ratios_dict["debt_to_equity"] is not None else None,
                    return_on_equity=Decimal(str(ratios_dict["return_on_equity"])) if ratios_dict["return_on_equity"] is not None else None,
                    return_on_assets=Decimal(str(ratios_dict["return_on_assets"])) if ratios_dict["return_on_assets"] is not None else None,
                    source=f"Auto-calculated ({source})"
                )
                db.add(new_ratio)

            calculated_ratios_count += 1

        db.commit()
        return {
            "success": True,
            "imported_statements": imported_count,
            "updated_statements": updated_count,
            "calculated_ratios": calculated_ratios_count,
            "company_id": company_id
        }

    except Exception as e:
        db.rollback()
        raise RuntimeError(f"Database import failed: {str(e)}")
