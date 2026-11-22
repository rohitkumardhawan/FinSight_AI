"""
FinSight AI — Unified Multi-Format Financial CSV Parser
=======================================================
Auto-detects Screener.in multi-section exports and FinSight Combined templates,
normalizes them into canonical Pydantic structures, extracts ratios, trends,
and scenarios with strict validation and sanitization.
"""

import io
import re
import csv
from typing import List, Dict, Any, Optional, Tuple
from app.schemas.dataset import FinancialPeriodRecord, ParsedCompanyDataset

MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB upload guard


def clean_number_string(val: Any) -> Tuple[Optional[float], bool]:
    """
    Cleans messy financial numerical cells:
    - Strips whitespace, quotes, and commas (' 15,061.99 ' -> 15061.99)
    - Detects percentage strings ('50.94%' -> 50.94, is_percent=True)
    - Treats '-', 'N/A', '', None as (None, False)
    """
    if val is None:
        return None, False
    s = str(val).strip().replace('"', '').replace("'", "")
    if not s or s == "-" or s.lower() == "n/a" or s.lower() == "null":
        return None, False

    is_percent = False
    if s.endswith("%"):
        is_percent = True
        s = s[:-1].strip()

    s = s.replace(",", "").strip()
    try:
        num = float(s)
        return num, is_percent
    except ValueError:
        return None, False


def clean_company_name_from_filename(filename: str) -> str:
    """Derives a clean company name from a filename if not explicitly stated."""
    base = filename.rsplit(".", 1)[0]
    # Remove trailing duplicate suffixes like (4)4332 or _copy
    cleaned = re.sub(r"\s*\(\d+\)[\d\w]*", "", base)
    cleaned = re.sub(r"[-_]template|[-_]dataset", "", cleaned, flags=re.IGNORECASE)
    cleaned = cleaned.replace("_", " ").strip()
    return cleaned.title() if cleaned else "Enterprise Entity"


def detect_csv_format(rows: List[List[str]]) -> str:
    """
    Auto-detects format:
    - 'screener_csv': Row 1 contains 'SCREENER.IN' OR any header row starts with 'Narration'
    - 'finsight_combined_csv': Any row contains both 'fiscal_year' and 'revenue'
    """
    for r in rows[:5]:
        row_str = " ".join(r).upper()
        if "SCREENER.IN" in row_str:
            return "screener_csv"
        if r and r[0].strip().lower() == "narration":
            return "screener_csv"

    for r in rows[:5]:
        cleaned = [c.strip().lower() for c in r]
        if "fiscal_year" in cleaned and "revenue" in cleaned:
            return "finsight_combined_csv"

    # Search anywhere in first 10 rows
    for r in rows[:10]:
        if r and r[0].strip().lower() == "narration":
            return "screener_csv"

    raise ValueError(
        "Unrecognized CSV format. Expected Screener.in multi-section export or FinSight Combined format."
    )


def parse_screener_csv(
    rows: List[List[str]],
    filename: str,
    company_name_override: Optional[str] = None
) -> ParsedCompanyDataset:
    """
    Parses a Screener.in CSV export with multi-section layout:
    - Company name in cell [0, 0]
    - Narration row containing periods ('Mar-17'..'Mar-26', 'Trailing', 'Best Case', 'Worst Case')
    - P&L line items
    - RATIOS: section (Dividend Payout, OPM)
    - TRENDS: block (10Y, 7Y, 5Y, 3Y, RECENT, BEST, WORST)
    - Scenario comparisons
    """
    # 1. Company Name
    company_name = company_name_override
    if not company_name and rows and rows[0] and rows[0][0].strip():
        first_cell = rows[0][0].strip()
        if "SCREENER.IN" not in first_cell.upper():
            company_name = first_cell
    if not company_name:
        company_name = clean_company_name_from_filename(filename)

    # 2. Find Narration Header Row
    narration_row_idx = -1
    for idx, r in enumerate(rows):
        if r and r[0].strip().lower() == "narration":
            narration_row_idx = idx
            break

    if narration_row_idx == -1:
        raise ValueError("Could not find required 'Narration' header row in Screener.in CSV.")

    header_cols = rows[narration_row_idx]
    # Period mappings: list of tuples (col_index, raw_header, fiscal_year, fiscal_period)
    periods_meta: List[Dict[str, Any]] = []
    for col_idx in range(1, len(header_cols)):
        col_hdr = header_cols[col_idx].strip()
        if not col_hdr:
            continue

        fiscal_year: Optional[int] = None
        fiscal_period: str = "FY"

        # Check for fiscal year pattern like 'Mar-17', 'Mar-2026', 'FY24'
        match_my = re.search(r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[ -]?(\d{2,4})", col_hdr, re.IGNORECASE)
        match_fy = re.search(r"FY[ -]?(\d{2,4})", col_hdr, re.IGNORECASE)

        if match_my:
            raw_yr = match_my.group(1)
            fiscal_year = 2000 + int(raw_yr) if len(raw_yr) == 2 else int(raw_yr)
            fiscal_period = "FY"
        elif match_fy:
            raw_yr = match_fy.group(1)
            fiscal_year = 2000 + int(raw_yr) if len(raw_yr) == 2 else int(raw_yr)
            fiscal_period = "FY"
        elif "trailing" in col_hdr.lower() or "ttm" in col_hdr.lower():
            fiscal_year = None
            fiscal_period = "TTM"
        elif "best" in col_hdr.lower():
            fiscal_year = None
            fiscal_period = "Best Case"
        elif "worst" in col_hdr.lower():
            fiscal_year = None
            fiscal_period = "Worst Case"
        else:
            fiscal_year = None
            fiscal_period = col_hdr

        periods_meta.append({
            "col_idx": col_idx,
            "raw_header": col_hdr,
            "fiscal_year": fiscal_year,
            "fiscal_period": fiscal_period,
            "metrics": {}
        })

    # 3. Parse P&L Line Items
    ratios_start_idx = len(rows)
    for idx in range(narration_row_idx + 1, len(rows)):
        r = rows[idx]
        if not r or not any(c.strip() for c in r):
            continue
        first_col = r[0].strip().lower()
        if first_col.startswith("ratios:"):
            ratios_start_idx = idx
            break

        # Map row label to canonical field name
        field_name: Optional[str] = None
        if "sales" in first_col or "revenue" in first_col:
            field_name = "revenue"
        elif "expenses" in first_col:
            field_name = "operating_expenses"
        elif "operating profit" in first_col:
            field_name = "operating_income"
        elif "other income" in first_col:
            field_name = "other_income"
        elif "depreciation" in first_col:
            field_name = "depreciation_amortization"
        elif "interest" in first_col:
            field_name = "interest_expense"
        elif "profit before tax" in first_col:
            field_name = "profit_before_tax"
        elif first_col == "tax":
            field_name = "tax"  # handled specially for rate % vs expense
        elif "net profit" in first_col or "net income" in first_col:
            field_name = "net_income"
        elif first_col == "eps":
            field_name = "eps"
        elif "price to earning" in first_col or "p/e" in first_col:
            field_name = "pe_ratio"
        elif first_col == "price" or "share price" in first_col:
            field_name = "share_price"

        if field_name:
            for p in periods_meta:
                c_idx = p["col_idx"]
                if c_idx < len(r):
                    val, is_pct = clean_number_string(r[c_idx])
                    if field_name == "tax":
                        if is_pct:
                            p["metrics"]["tax_rate_pct"] = val
                        else:
                            p["metrics"]["tax_expense"] = val
                    else:
                        p["metrics"][field_name] = val

    # 4. Parse RATIOS: Section
    trends_start_idx = len(rows)
    for idx in range(ratios_start_idx, len(rows)):
        r = rows[idx]
        if not r or not any(c.strip() for c in r):
            continue
        first_col = r[0].strip().lower()
        if "trends:" in " ".join(r).upper():
            trends_start_idx = idx
            break

        if "dividend payout" in first_col:
            for p in periods_meta:
                c_idx = p["col_idx"]
                if c_idx < len(r):
                    val, _ = clean_number_string(r[c_idx])
                    p["metrics"]["dividend_payout_pct"] = val
        elif "opm" in first_col:
            for p in periods_meta:
                c_idx = p["col_idx"]
                if c_idx < len(r):
                    val, _ = clean_number_string(r[c_idx])
                    p["metrics"]["opm_pct"] = val

    # 5. Parse Dynamic TRENDS: Block
    trends_data: Optional[Dict[str, Any]] = None
    trends_cell_coord: Optional[Tuple[int, int]] = None

    for r_idx in range(narration_row_idx, len(rows)):
        for c_idx in range(len(rows[r_idx])):
            cell_val = rows[r_idx][c_idx].strip().upper()
            if cell_val == "TRENDS:":
                trends_cell_coord = (r_idx, c_idx)
                break
        if trends_cell_coord:
            break

    if trends_cell_coord:
        t_row, t_col = trends_cell_coord
        trends_headers = [c.strip() for c in rows[t_row][t_col + 1:] if c.strip()]
        trends_metrics: Dict[str, Dict[str, Optional[float]]] = {}

        for next_r in range(t_row + 1, min(t_row + 10, len(rows))):
            curr_row = rows[next_r]
            if t_col >= len(curr_row):
                continue
            metric_label = curr_row[t_col].strip()
            if not metric_label:
                continue

            metric_key = metric_label.lower().replace(" ", "_")
            if "sales growth" in metric_label.lower():
                metric_key = "sales_growth"
            elif "opm" in metric_label.lower():
                metric_key = "opm"
            elif "price to earning" in metric_label.lower():
                metric_key = "pe_ratio"

            values_map: Dict[str, Optional[float]] = {}
            for h_offset, h_name in enumerate(trends_headers):
                val_col = t_col + 1 + h_offset
                if val_col < len(curr_row):
                    num, _ = clean_number_string(curr_row[val_col])
                    values_map[h_name] = num
                else:
                    values_map[h_name] = None

            trends_metrics[metric_key] = values_map

        trends_data = {
            "headers": trends_headers,
            "metrics": trends_metrics
        }

    # 6. Build FinancialPeriodRecord List
    period_records: List[FinancialPeriodRecord] = []
    scenarios_data: Dict[str, Any] = {}

    for p in periods_meta:
        m = p["metrics"]
        record = FinancialPeriodRecord(
            fiscal_year=p["fiscal_year"],
            fiscal_period=p["fiscal_period"],
            statement_type="annual_combined",
            revenue=m.get("revenue"),
            operating_expenses=m.get("operating_expenses"),
            operating_income=m.get("operating_income"),
            other_income=m.get("other_income"),
            ebit=m.get("operating_income"),
            depreciation_amortization=m.get("depreciation_amortization"),
            interest_expense=m.get("interest_expense"),
            profit_before_tax=m.get("profit_before_tax"),
            tax_expense=m.get("tax_expense"),
            tax_rate_pct=m.get("tax_rate_pct"),
            net_income=m.get("net_income"),
            eps=m.get("eps"),
            pe_ratio=m.get("pe_ratio"),
            share_price=m.get("share_price"),
            dividend_payout_pct=m.get("dividend_payout_pct"),
            opm_pct=m.get("opm_pct"),
            source="Screener.in"
        )
        period_records.append(record)

        # Populate scenarios object
        if p["fiscal_period"] in ["TTM", "Best Case", "Worst Case"]:
            scenario_key = p["fiscal_period"].lower().replace(" ", "_")
            scenarios_data[scenario_key] = {
                "period": p["fiscal_period"],
                "revenue": m.get("revenue"),
                "operating_income": m.get("operating_income"),
                "net_income": m.get("net_income"),
                "eps": m.get("eps"),
                "pe_ratio": m.get("pe_ratio"),
                "share_price": m.get("share_price"),
                "opm_pct": m.get("opm_pct"),
                "tax_rate_pct": m.get("tax_rate_pct")
            }

    return ParsedCompanyDataset(
        company_name=company_name,
        filename=filename,
        detected_format="screener_csv",
        periods=period_records,
        trends=trends_data,
        scenarios=scenarios_data if scenarios_data else None,
        raw_metadata={
            "source": "Screener.in",
            "period_count": len(period_records)
        }
    )


def parse_finsight_combined_csv(
    rows: List[List[str]],
    filename: str,
    company_name_override: Optional[str] = None
) -> ParsedCompanyDataset:
    """
    Parses row-oriented FinSight Combined CSV template:
    fiscal_year,fiscal_period,statement_type,revenue,cost_of_revenue,gross_profit,...
    """
    company_name = company_name_override or clean_company_name_from_filename(filename)

    # Locate header row
    header_idx = -1
    for idx, r in enumerate(rows):
        cleaned = [c.strip().lower() for c in r]
        if "fiscal_year" in cleaned and "revenue" in cleaned:
            header_idx = idx
            break

    if header_idx == -1:
        raise ValueError("Could not find required 'fiscal_year' and 'revenue' header row in FinSight Combined CSV.")

    headers = [c.strip().lower() for c in rows[header_idx]]
    records: List[FinancialPeriodRecord] = []

    for r_idx in range(header_idx + 1, len(rows)):
        r = rows[r_idx]
        if not r or not any(c.strip() for c in r):
            continue

        row_dict = {}
        for h_idx, h in enumerate(headers):
            if h_idx < len(r):
                row_dict[h] = r[h_idx].strip()

        # Parse fiscal year & period
        raw_year = row_dict.get("fiscal_year", "")
        fiscal_year = int(raw_year) if raw_year and raw_year.isdigit() else None
        fiscal_period = row_dict.get("fiscal_period", "FY") or "FY"
        statement_type = row_dict.get("statement_type", "annual_combined") or "annual_combined"

        # Parse numeric fields
        def _get_num(key: str) -> Optional[float]:
            val, _ = clean_number_string(row_dict.get(key))
            return val

        rev = _get_num("revenue")
        cogs = _get_num("cost_of_revenue")
        gp = _get_num("gross_profit")
        op_inc = _get_num("operating_income")
        ebit = _get_num("ebit") or op_inc
        net_inc = _get_num("net_income")

        record = FinancialPeriodRecord(
            fiscal_year=fiscal_year,
            fiscal_period=fiscal_period,
            statement_type=statement_type,
            revenue=rev,
            cost_of_revenue=cogs,
            gross_profit=gp,
            operating_income=op_inc,
            ebit=ebit,
            net_income=net_inc,
            total_assets=_get_num("total_assets"),
            current_assets=_get_num("current_assets"),
            total_liabilities=_get_num("total_liabilities"),
            current_liabilities=_get_num("current_liabilities"),
            total_equity=_get_num("total_equity"),
            cash_and_equivalents=_get_num("cash_and_equivalents"),
            inventory=_get_num("inventory"),
            total_debt=_get_num("total_debt"),
            operating_cash_flow=_get_num("operating_cash_flow"),
            capital_expenditure=_get_num("capital_expenditure"),
            free_cash_flow=_get_num("free_cash_flow"),
            depreciation_amortization=_get_num("depreciation_amortization"),
            source=row_dict.get("source", "FinSight Standard Template")
        )

        # Derive OPM % and Gross Margin % if not present
        if rev and rev > 0:
            if op_inc is not None:
                record.opm_pct = round((op_inc / rev) * 100, 2)
            if gp is not None and cogs is not None:
                record.gross_profit = gp

        records.append(record)

    return ParsedCompanyDataset(
        company_name=company_name,
        filename=filename,
        detected_format="finsight_combined_csv",
        periods=records,
        raw_metadata={
            "source": "FinSight Combined Format",
            "period_count": len(records)
        }
    )


def parse_financial_csv(
    file_bytes: bytes,
    filename: str,
    company_name_override: Optional[str] = None
) -> ParsedCompanyDataset:
    """
    Main entry point:
    - Enforces 10 MB upload guard
    - Decodes text with UTF-8 BOM protection
    - Auto-detects format (Screener.in or FinSight Combined)
    - Returns validated ParsedCompanyDataset
    """
    if len(file_bytes) > MAX_FILE_SIZE_BYTES:
        raise ValueError(
            f"File size {round(len(file_bytes) / (1024 * 1024), 2)} MB exceeds maximum allowed limit of 10 MB."
        )

    if not filename.lower().endswith(".csv"):
        raise ValueError("Invalid file extension. Please upload a standard .csv document.")

    # Decode bytes safely
    text = ""
    for enc in ["utf-8-sig", "utf-8", "latin-1"]:
        try:
            text = file_bytes.decode(enc)
            break
        except UnicodeDecodeError:
            continue

    if not text.strip():
        raise ValueError("Uploaded CSV file is empty.")

    # Parse rows using csv.reader
    reader = csv.reader(io.StringIO(text))
    rows = list(reader)

    if not rows:
        raise ValueError("CSV contains no tabular data.")

    fmt = detect_csv_format(rows)

    if fmt == "screener_csv":
        return parse_screener_csv(rows, filename, company_name_override)
    elif fmt == "finsight_combined_csv":
        return parse_finsight_combined_csv(rows, filename, company_name_override)
    else:
        raise ValueError(f"Unsupported format: {fmt}")
