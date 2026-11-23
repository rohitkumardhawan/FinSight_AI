"""
FinSight AI — Institutional Excel Financial Model Export Engine
==============================================================
Generates publication-grade, formula-driven multi-tab financial model workbooks:
- 4 Wall Street-grade sheets:
  1. Executive Summary: Company profile, formula-linked DCF summary, institutional risk scorecard.
  2. 3-Statement Financials: Full historical annual statements with live Excel formulas for derived items.
  3. Ratios & Peers: Historical ratios linked via cross-sheet formulas + same-currency sector peer benchmarking.
  4. DCF Valuation: Dynamic blue-font assumptions block, 5-10Y projection schedule, equity bridge, and 5x5 sensitivity matrix.
- Wall Street color standards:
  - Dark Navy (#0F172A) headers with white bold text.
  - Blue font (#0000FF) for editable hardcoded inputs.
  - Black font (#000000) for same-sheet formulas and historical data.
  - Green font (#008000) for cross-sheet links.
- Formula-injection sanitized for all text cells.
"""

import io
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
import logging

import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from sqlalchemy.orm import Session

from app.models.company import Company
from app.models.dataset import FinancialPeriod
from app.services.dcf_engine import calculate_dcf, DCFRequest
from app.services.risk_engine import calculate_risk_intelligence
from app.services.peer_engine import get_sector_peers
from app.financial.metrics import calculate_net_debt

logger = logging.getLogger(__name__)

# -------------------------------------------------------------
# Color & Style Constants
# -------------------------------------------------------------
NAVY_FILL = PatternFill(start_color="0F172A", end_color="0F172A", fill_type="solid")
SUBHEADER_FILL = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")
ACCENT_FILL = PatternFill(start_color="F1F5F9", end_color="F1F5F9", fill_type="solid")
HIGHLIGHT_FILL = PatternFill(start_color="E2E8F0", end_color="E2E8F0", fill_type="solid")

TITLE_FONT = Font(name="Calibri", size=13, bold=True, color="FFFFFF")
HEADER_FONT = Font(name="Calibri", size=10, bold=True, color="FFFFFF")
SUBHEADER_FONT = Font(name="Calibri", size=10, bold=True, color="F8FAFC")
SECTION_LABEL_FONT = Font(name="Calibri", size=10, bold=True, color="0F172A")

BLUE_INPUT_FONT = Font(name="Calibri", size=10, bold=False, color="0000FF")
BLUE_INPUT_BOLD = Font(name="Calibri", size=10, bold=True, color="0000FF")

BLACK_FORMULA_FONT = Font(name="Calibri", size=10, bold=False, color="000000")
BLACK_FORMULA_BOLD = Font(name="Calibri", size=10, bold=True, color="000000")

GREEN_LINK_FONT = Font(name="Calibri", size=10, bold=False, color="008000")
GREEN_LINK_BOLD = Font(name="Calibri", size=10, bold=True, color="008000")

MUTED_LABEL_FONT = Font(name="Calibri", size=9, italic=True, color="64748B")

THIN_BORDER_SIDE = Side(style="thin", color="CBD5E1")
DOUBLE_BOTTOM_SIDE = Side(style="double", color="0F172A")
DARK_TOP_SIDE = Side(style="thin", color="0F172A")

DATA_BORDER = Border(
    left=THIN_BORDER_SIDE,
    right=THIN_BORDER_SIDE,
    top=THIN_BORDER_SIDE,
    bottom=THIN_BORDER_SIDE
)
TOTAL_BORDER = Border(
    left=THIN_BORDER_SIDE,
    right=THIN_BORDER_SIDE,
    top=DARK_TOP_SIDE,
    bottom=DOUBLE_BOTTOM_SIDE
)

# Number format strings
NUM_FMT_ACCOUNTING = '_(* #,##0.00_);_(* (#,##0.00);_(* "-"??_);_(@_)'
NUM_FMT_PERCENTAGE = '0.00%'
NUM_FMT_MULTIPLE = '0.00"x"'
NUM_FMT_PER_SHARE = '_(* #,##0.00_);_(* (#,##0.00);_(* "-"??_);_(@_)'
NUM_FMT_INTEGER = '#,##0'
NUM_FMT_FACTOR = '0.0000'


def sanitize_text(val: Any) -> Any:
    """Defend against Excel formula injection (=, +, -, @, tab, newline)."""
    if isinstance(val, str):
        if val.startswith(("=", "+", "-", "@", "\t", "\r")):
            return "'" + val
    return val


def autofit_columns(ws, min_col: int = 1, max_col: int = 15, padding: int = 3):
    """Auto-fit column widths cleanly based on content length."""
    for col in range(min_col, max_col + 1):
        col_letter = get_column_letter(col)
        max_len = 0
        for cell in ws[col_letter]:
            if cell.value is not None:
                val_str = str(cell.value)
                if val_str.startswith("="):
                    # formula: estimate reasonable length
                    max_len = max(max_len, 12)
                else:
                    max_len = max(max_len, len(val_str))
        ws.column_dimensions[col_letter].width = max(max_len + padding, 12)


def generate_financial_model_xlsx(
    company: Company,
    periods: List[FinancialPeriod],
    db: Session,
    fcf_growth: Optional[float] = None,
    wacc: Optional[float] = None,
    terminal_growth: Optional[float] = None,
    projection_years: Optional[int] = 5
) -> io.BytesIO:
    """
    Builds the institutional 4-sheet financial model workbook and returns a BytesIO buffer.
    """
    wb = openpyxl.Workbook()
    # Remove default sheet
    default_sheet = wb.active

    # Determine Currency and Scale Factor
    currency = (company.currency or "INR").upper()
    is_inr = (currency == "INR") or (company.symbol or "").endswith((".NS", ".BO"))
    currency_symbol = "₹" if is_inr else ("$" if currency == "USD" else currency)
    scale_factor = 1e7 if is_inr else 1e6
    scale_label = f"All monetary figures in {currency_symbol} {'Crores' if is_inr else 'Millions'} except per-share data"

    # Normalize Projection Horizon
    proj_years = projection_years or 5
    if proj_years < 5:
        proj_years = 5
    elif proj_years > 10:
        proj_years = 10

    # 1. Compute deterministic DCF model
    dcf_req = DCFRequest(
        growth_rate=fcf_growth,
        wacc=wacc,
        terminal_growth_rate=terminal_growth,
        projection_years=proj_years
    )
    dcf_res = calculate_dcf(company, periods, dcf_req)

    # 2. Extract and Sort Annual Historical Periods
    annual_periods = sorted(
        [
            p for p in periods
            if p.fiscal_year is not None
            and getattr(p, "statement_type", "") != "quarterly"
            and not (getattr(p, "fiscal_period", "") or "").upper().startswith("Q")
        ],
        key=lambda x: x.fiscal_year or 0
    )
    if not annual_periods:
        annual_periods = periods[-4:] if len(periods) >= 4 else periods

    # 3. Fetch Sector Peers
    peer_data = {}
    try:
        peer_data = get_sector_peers(company.symbol or company.ticker, db)
    except Exception as p_err:
        logger.warning(f"Failed to fetch peer data for Excel export: {p_err}")

    # 4. Fetch Risk Intelligence (skip AI for instant export)
    risk_data = None
    try:
        risk_data = calculate_risk_intelligence(company, periods, skip_ai=True)
    except Exception as r_err:
        logger.warning(f"Failed to fetch risk intelligence for Excel export: {r_err}")

    # -------------------------------------------------------------
    # BUILD SHEETS
    # -------------------------------------------------------------
    _build_tab1_executive_summary(wb, company, dcf_res, risk_data, currency_symbol, scale_label, scale_factor)
    _build_tab2_three_statement_financials(wb, company, annual_periods, currency_symbol, scale_label, scale_factor)
    _build_tab3_ratios_and_peers(wb, company, annual_periods, peer_data, currency_symbol, scale_label, scale_factor)
    _build_tab4_dcf_valuation(wb, company, dcf_res, currency_symbol, scale_label, scale_factor, proj_years)

    # Remove initial default blank sheet
    if default_sheet in wb.worksheets:
        wb.remove(default_sheet)

    # Stream out BytesIO buffer
    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return output


# =============================================================================
# TAB 1: EXECUTIVE SUMMARY
# =============================================================================
def _build_tab1_executive_summary(
    wb: openpyxl.Workbook,
    company: Company,
    dcf_res: Any,
    risk_data: Any,
    currency_symbol: str,
    scale_label: str,
    scale_factor: float
):
    ws = wb.create_sheet(title="Executive Summary")
    ws.views.sheetView[0].showGridLines = True
    ws.freeze_panes = "A4"

    # Title Block
    ws.merge_cells("A1:G1")
    ws["A1"] = f"FinSight AI — Institutional Equity Research & Valuation Model"
    ws["A1"].font = TITLE_FONT
    ws["A1"].fill = NAVY_FILL
    ws["A1"].alignment = Alignment(horizontal="left", vertical="center", indent=1)
    ws.row_dimensions[1].height = 28

    ws["A2"] = scale_label
    ws["A2"].font = MUTED_LABEL_FONT

    # Section 1: Company Profile
    ws.merge_cells("A4:G4")
    ws["A4"] = "COMPANY PROFILE & TRADING METRICS"
    ws["A4"].font = HEADER_FONT
    ws["A4"].fill = NAVY_FILL
    ws.row_dimensions[4].height = 20

    profile_headers = ["Metric", "Details / Value", "", "Company Overview", "", "", ""]
    for col_idx, h in enumerate(profile_headers[:2], start=1):
        cell = ws.cell(row=5, column=col_idx, value=h)
        cell.font = SUBHEADER_FONT
        cell.fill = SUBHEADER_FILL

    clean_sym = company.symbol or company.ticker or ""
    clean_name = company.company_name or clean_sym
    exch = company.exchange or ("NSE" if clean_sym.endswith(".NS") else "GLOBAL")
    sector = company.sector or "Equity"
    curr = company.currency or "INR"
    quote_data = (company.metadata_json or {}).get("quote", {})
    mcap = quote_data.get("market_cap") or quote_data.get("marketCap") or (dcf_res.current_price * dcf_res.shares_outstanding)

    rows_profile = [
        ("Company Name", sanitize_text(clean_name), "@"),
        ("Ticker / Symbol", sanitize_text(clean_sym), "@"),
        ("Exchange", sanitize_text(exch), "@"),
        ("Sector / Industry", sanitize_text(sector), "@"),
        ("Reporting Currency", sanitize_text(curr), "@"),
        ("Current Market Share Price", dcf_res.current_price, NUM_FMT_PER_SHARE),
        (f"Market Capitalization ({'₹ Cr' if currency_symbol == '₹' else '$M'})", (mcap / scale_factor) if mcap else None, NUM_FMT_ACCOUNTING),
        (f"Diluted Shares Outstanding ({'Cr' if currency_symbol == '₹' else 'M'})", (dcf_res.shares_outstanding / scale_factor) if dcf_res.shares_outstanding else None, NUM_FMT_ACCOUNTING),
    ]

    for idx, (label, val, fmt) in enumerate(rows_profile, start=6):
        c1 = ws.cell(row=idx, column=1, value=label)
        c2 = ws.cell(row=idx, column=2, value=val)
        c1.font = SECTION_LABEL_FONT
        c1.border = DATA_BORDER
        c2.font = BLACK_FORMULA_FONT
        c2.border = DATA_BORDER
        c2.number_format = fmt

    # Section 2: Valuation Summary (Cross-sheet formulas from Tab 4)
    ws.merge_cells("A15:G15")
    ws["A15"] = "VALUATION SUMMARY & EQUITY BRIDGE (LIVE DCF LINKS)"
    ws["A15"].font = HEADER_FONT
    ws["A15"].fill = NAVY_FILL
    ws.row_dimensions[15].height = 20

    val_headers = ["Valuation Metric", "Model Value", "Unit / Method", "Source / Reference"]
    for col_idx, h in enumerate(val_headers, start=1):
        cell = ws.cell(row=16, column=col_idx, value=h)
        cell.font = SUBHEADER_FONT
        cell.fill = SUBHEADER_FILL

    # Cross-sheet references to 'DCF Valuation'
    val_metrics = [
        ("Enterprise Value (EV)", "='DCF Valuation'!B26", NUM_FMT_ACCOUNTING, f"{currency_symbol} {'Cr' if currency_symbol == '₹' else 'M'}", "Cross-sheet link (DCF)"),
        ("Less: Net Debt", "='DCF Valuation'!B27", NUM_FMT_ACCOUNTING, f"{currency_symbol} {'Cr' if currency_symbol == '₹' else 'M'}", "Cross-sheet link (DCF)"),
        ("Implied Equity Value", "='DCF Valuation'!B28", NUM_FMT_ACCOUNTING, f"{currency_symbol} {'Cr' if currency_symbol == '₹' else 'M'}", "Cross-sheet link (DCF)"),
        ("Intrinsic Value per Share", "='DCF Valuation'!B30", NUM_FMT_PER_SHARE, f"{currency_symbol} per share", "Model Target Price"),
        ("Current Market Share Price", "='DCF Valuation'!B11", NUM_FMT_PER_SHARE, f"{currency_symbol} per share", "Live Exchange Quote"),
        ("Implied Upside / (Downside) %", "='DCF Valuation'!B32", NUM_FMT_PERCENTAGE, "% Return", "=(Intrinsic / Price) - 1"),
    ]

    for idx, (label, formula_ref, fmt, unit, note) in enumerate(val_metrics, start=17):
        c1 = ws.cell(row=idx, column=1, value=label)
        c2 = ws.cell(row=idx, column=2, value=formula_ref)
        c3 = ws.cell(row=idx, column=3, value=unit)
        c4 = ws.cell(row=idx, column=4, value=note)
        
        is_key = "Intrinsic" in label or "Upside" in label
        c1.font = BLACK_FORMULA_BOLD if is_key else SECTION_LABEL_FONT
        c2.font = GREEN_LINK_BOLD if is_key else GREEN_LINK_FONT
        c3.font = MUTED_LABEL_FONT
        c4.font = MUTED_LABEL_FONT

        c1.border = DATA_BORDER
        c2.border = DATA_BORDER
        c3.border = DATA_BORDER
        c4.border = DATA_BORDER
        c2.number_format = fmt

    # Section 3: Institutional Risk Assessment
    ws.merge_cells("A24:G24")
    ws["A24"] = "INSTITUTIONAL RISK ASSESSMENT & FINANCIAL HEALTH"
    ws["A24"].font = HEADER_FONT
    ws["A24"].fill = NAVY_FILL
    ws.row_dimensions[24].height = 20

    risk_headers = ["Risk Dimension", "Score / Rating", "Category", "Institutional Benchmark"]
    for col_idx, h in enumerate(risk_headers, start=1):
        cell = ws.cell(row=25, column=col_idx, value=h)
        cell.font = SUBHEADER_FONT
        cell.fill = SUBHEADER_FILL

    overall_rating = getattr(risk_data, "risk_level", "Moderate Risk") if risk_data else "Moderate Risk"
    overall_score = getattr(risk_data, "overall_score", 45.0) if risk_data else 45.0

    risk_rows = [
        ("Composite Risk Rating", sanitize_text(overall_rating), "Overall Health", "Lower is safer"),
        ("Composite Risk Score", overall_score, "Normalized (0-100)", "< 30 Low, 30-60 Moderate, > 60 High"),
    ]
    if risk_data and hasattr(risk_data, "pillars") and isinstance(risk_data.pillars, dict):
        pillar_names = {
            "leverage_liquidity": "Leverage & Liquidity",
            "profitability_stability": "Profitability & Stability",
            "valuation_stretch": "Valuation Stretch",
            "earnings_quality": "Earnings Quality",
        }
        for p_key, p_val in risk_data.pillars.items():
            display_name = pillar_names.get(p_key, p_key.replace("_", " ").title())
            p_score = p_val.get("pillar_score", 50.0) if isinstance(p_val, dict) else getattr(p_val, "pillar_score", 50.0)
            p_level = p_val.get("risk_level", "Moderate") if isinstance(p_val, dict) else getattr(p_val, "risk_level", "Moderate")
            risk_rows.append((display_name, p_score, p_level, "0-100 Scale"))

    for idx, (dim, score_val, cat, bench) in enumerate(risk_rows, start=26):
        c1 = ws.cell(row=idx, column=1, value=dim)
        c2 = ws.cell(row=idx, column=2, value=score_val)
        c3 = ws.cell(row=idx, column=3, value=cat)
        c4 = ws.cell(row=idx, column=4, value=bench)
        c1.font = SECTION_LABEL_FONT
        c2.font = BLACK_FORMULA_BOLD if isinstance(score_val, (int, float)) else BLACK_FORMULA_FONT
        c3.font = BLACK_FORMULA_FONT
        c4.font = MUTED_LABEL_FONT
        c1.border = DATA_BORDER
        c2.border = DATA_BORDER
        c3.border = DATA_BORDER
        c4.border = DATA_BORDER
        if isinstance(score_val, (int, float)):
            c2.number_format = NUM_FMT_INTEGER

    # Footer Disclaimer
    disclaimer_row = 26 + len(risk_rows) + 2
    ws.merge_cells(f"A{disclaimer_row}:G{disclaimer_row}")
    disc_cell = ws.cell(
        row=disclaimer_row,
        column=1,
        value="Generated by FinSight AI for research and educational purposes only. Not investment advice."
    )
    disc_cell.font = MUTED_LABEL_FONT
    disc_cell.alignment = Alignment(horizontal="left", vertical="center")

    autofit_columns(ws, min_col=1, max_col=7)


# =============================================================================
# TAB 2: 3-STATEMENT FINANCIALS
# =============================================================================
def _build_tab2_three_statement_financials(
    wb: openpyxl.Workbook,
    company: Company,
    annual_periods: List[FinancialPeriod],
    currency_symbol: str,
    scale_label: str,
    scale_factor: float
):
    ws = wb.create_sheet(title="3-Statement Financials")
    ws.views.sheetView[0].showGridLines = True
    ws.freeze_panes = "B5"

    num_periods = len(annual_periods)
    last_col_letter = get_column_letter(1 + num_periods)

    # Title Block
    ws.merge_cells(f"A1:{last_col_letter}1")
    ws["A1"] = f"FinSight AI — 3-Statement Financial Model (Historical)"
    ws["A1"].font = TITLE_FONT
    ws["A1"].fill = NAVY_FILL
    ws["A1"].alignment = Alignment(horizontal="left", vertical="center", indent=1)
    ws.row_dimensions[1].height = 28

    ws["A2"] = scale_label
    ws["A2"].font = MUTED_LABEL_FONT

    # Table Headers: Row 4
    ws.cell(row=4, column=1, value="Line Item").fill = NAVY_FILL
    ws.cell(row=4, column=1).font = HEADER_FONT

    for col_idx, p in enumerate(annual_periods, start=2):
        yr_label = f"FY{p.fiscal_year}" if p.fiscal_year else (p.fiscal_period or f"Period {col_idx-1}")
        c = ws.cell(row=4, column=col_idx, value=yr_label)
        c.fill = NAVY_FILL
        c.font = HEADER_FONT
        c.alignment = Alignment(horizontal="right")
    ws.row_dimensions[4].height = 20

    # -------------------------------------------------------------
    # 1. INCOME STATEMENT (Rows 5 to 22)
    # -------------------------------------------------------------
    ws.merge_cells(f"A5:{last_col_letter}5")
    ws["A5"] = "1. INCOME STATEMENT"
    ws["A5"].font = SUBHEADER_FONT
    ws["A5"].fill = SUBHEADER_FILL
    ws.row_dimensions[5].height = 18

    # Extract historical line items scaled
    rev_vals = []
    cogs_vals = []
    opex_vals = []
    da_vals = []
    other_inc_vals = []
    interest_vals = []
    tax_vals = []
    eps_vals = []

    for p in annual_periods:
        m = p.metrics_json or {}
        rev = m.get("revenue")
        cogs = m.get("cost_of_revenue") or m.get("cogs")
        gp = m.get("gross_profit")
        if cogs is None and rev is not None and gp is not None:
            cogs = rev - gp
        opex = m.get("operating_expenses") or m.get("opex")
        ebitda = m.get("ebitda")
        ebit = m.get("operating_income") if m.get("operating_income") is not None else m.get("ebit")
        da = m.get("depreciation_amortization")
        if da is None and ebitda is not None and ebit is not None:
            da = abs(ebitda - ebit)
        if opex is None and gp is not None and ebitda is not None:
            opex = max(0.0, gp - ebitda)
        other_inc = m.get("other_income")
        pbt = m.get("profit_before_tax")
        interest = m.get("interest_expense")
        if other_inc is None and pbt is not None and ebit is not None:
            other_inc = round(pbt - (ebit - abs(interest or 0.0)), 2)
        tax = m.get("tax_expense")
        eps = m.get("eps_diluted") or m.get("eps")

        rev_vals.append((rev / scale_factor) if rev is not None else 0.0)
        cogs_vals.append((cogs / scale_factor) if cogs is not None else 0.0)
        opex_vals.append((opex / scale_factor) if opex is not None else 0.0)
        da_vals.append((abs(da) / scale_factor) if da is not None else 0.0)
        other_inc_vals.append((other_inc / scale_factor) if other_inc is not None else 0.0)
        interest_vals.append((abs(interest) / scale_factor) if interest is not None else 0.0)
        tax_vals.append((tax / scale_factor) if tax is not None else 0.0)
        eps_vals.append(eps if eps is not None else 0.0)

    # Row 6: Revenue
    ws.cell(row=6, column=1, value="Revenue").font = SECTION_LABEL_FONT
    for i, v in enumerate(rev_vals, start=2):
        cell = ws.cell(row=6, column=i, value=v)
        cell.font = BLUE_INPUT_FONT
        cell.number_format = NUM_FMT_ACCOUNTING
        cell.border = DATA_BORDER

    # Row 7: (-) Cost of Goods Sold (COGS)
    ws.cell(row=7, column=1, value="(-) Cost of Goods Sold (COGS)").font = BLACK_FORMULA_FONT
    for i, v in enumerate(cogs_vals, start=2):
        cell = ws.cell(row=7, column=i, value=v)
        cell.font = BLUE_INPUT_FONT
        cell.number_format = NUM_FMT_ACCOUNTING
        cell.border = DATA_BORDER

    # Row 8: (=) Gross Profit -> Formula =B6-B7
    ws.cell(row=8, column=1, value="(=) Gross Profit").font = BLACK_FORMULA_BOLD
    for i in range(2, 2 + num_periods):
        col_c = get_column_letter(i)
        cell = ws.cell(row=8, column=i, value=f"={col_c}6-{col_c}7")
        cell.font = BLACK_FORMULA_BOLD
        cell.number_format = NUM_FMT_ACCOUNTING
        cell.border = DATA_BORDER

    # Row 9: Gross Margin % -> Formula =B8/B6
    ws.cell(row=9, column=1, value="Gross Margin %").font = MUTED_LABEL_FONT
    for i in range(2, 2 + num_periods):
        col_c = get_column_letter(i)
        cell = ws.cell(row=9, column=i, value=f"=IF({col_c}6>0,{col_c}8/{col_c}6,0)")
        cell.font = BLACK_FORMULA_FONT
        cell.number_format = NUM_FMT_PERCENTAGE
        cell.border = DATA_BORDER

    # Row 10: (-) Operating Expenses (OpEx)
    ws.cell(row=10, column=1, value="(-) Operating Expenses (OpEx)").font = BLACK_FORMULA_FONT
    for i, v in enumerate(opex_vals, start=2):
        cell = ws.cell(row=10, column=i, value=v)
        cell.font = BLUE_INPUT_FONT
        cell.number_format = NUM_FMT_ACCOUNTING
        cell.border = DATA_BORDER

    # Row 11: (=) EBITDA -> Formula =B8-B10
    ws.cell(row=11, column=1, value="(=) EBITDA").font = BLACK_FORMULA_BOLD
    for i in range(2, 2 + num_periods):
        col_c = get_column_letter(i)
        cell = ws.cell(row=11, column=i, value=f"={col_c}8-{col_c}10")
        cell.font = BLACK_FORMULA_BOLD
        cell.number_format = NUM_FMT_ACCOUNTING
        cell.border = DATA_BORDER

    # Row 12: EBITDA Margin % -> Formula =B11/B6
    ws.cell(row=12, column=1, value="EBITDA Margin %").font = MUTED_LABEL_FONT
    for i in range(2, 2 + num_periods):
        col_c = get_column_letter(i)
        cell = ws.cell(row=12, column=i, value=f"=IF({col_c}6>0,{col_c}11/{col_c}6,0)")
        cell.font = BLACK_FORMULA_FONT
        cell.number_format = NUM_FMT_PERCENTAGE
        cell.border = DATA_BORDER

    # Row 13: (-) Depreciation & Amortization
    ws.cell(row=13, column=1, value="(-) Depreciation & Amortization").font = BLACK_FORMULA_FONT
    for i, v in enumerate(da_vals, start=2):
        cell = ws.cell(row=13, column=i, value=v)
        cell.font = BLUE_INPUT_FONT
        cell.number_format = NUM_FMT_ACCOUNTING
        cell.border = DATA_BORDER

    # Row 14: (=) Operating Income (EBIT) -> Formula =B11-B13
    ws.cell(row=14, column=1, value="(=) Operating Income (EBIT)").font = BLACK_FORMULA_BOLD
    for i in range(2, 2 + num_periods):
        col_c = get_column_letter(i)
        cell = ws.cell(row=14, column=i, value=f"={col_c}11-{col_c}13")
        cell.font = BLACK_FORMULA_BOLD
        cell.number_format = NUM_FMT_ACCOUNTING
        cell.border = DATA_BORDER

    # Row 15: EBIT Margin % -> Formula =B14/B6
    ws.cell(row=15, column=1, value="EBIT Margin %").font = MUTED_LABEL_FONT
    for i in range(2, 2 + num_periods):
        col_c = get_column_letter(i)
        cell = ws.cell(row=15, column=i, value=f"=IF({col_c}6>0,{col_c}14/{col_c}6,0)")
        cell.font = BLACK_FORMULA_FONT
        cell.number_format = NUM_FMT_PERCENTAGE
        cell.border = DATA_BORDER

    # Row 16: (+) Other Income
    ws.cell(row=16, column=1, value="(+) Other Income").font = BLACK_FORMULA_FONT
    for i, v in enumerate(other_inc_vals, start=2):
        cell = ws.cell(row=16, column=i, value=v)
        cell.font = BLUE_INPUT_FONT
        cell.number_format = NUM_FMT_ACCOUNTING
        cell.border = DATA_BORDER

    # Row 17: (-) Finance Costs / Interest Expense
    ws.cell(row=17, column=1, value="(-) Finance Costs / Interest Expense").font = BLACK_FORMULA_FONT
    for i, v in enumerate(interest_vals, start=2):
        cell = ws.cell(row=17, column=i, value=v)
        cell.font = BLUE_INPUT_FONT
        cell.number_format = NUM_FMT_ACCOUNTING
        cell.border = DATA_BORDER

    # Row 18: (=) Earnings Before Tax (EBT) -> Formula =B14+B16-B17
    ws.cell(row=18, column=1, value="(=) Earnings Before Tax (EBT)").font = BLACK_FORMULA_BOLD
    for i in range(2, 2 + num_periods):
        col_c = get_column_letter(i)
        cell = ws.cell(row=18, column=i, value=f"={col_c}14+{col_c}16-{col_c}17")
        cell.font = BLACK_FORMULA_BOLD
        cell.number_format = NUM_FMT_ACCOUNTING
        cell.border = DATA_BORDER

    # Row 19: (-) Income Tax Expense
    ws.cell(row=19, column=1, value="(-) Income Tax Expense").font = BLACK_FORMULA_FONT
    for i, v in enumerate(tax_vals, start=2):
        cell = ws.cell(row=19, column=i, value=v)
        cell.font = BLUE_INPUT_FONT
        cell.number_format = NUM_FMT_ACCOUNTING
        cell.border = DATA_BORDER

    # Row 20: (=) Net Income -> Formula =B18-B19
    ws.cell(row=20, column=1, value="(=) Net Income").font = BLACK_FORMULA_BOLD
    for i in range(2, 2 + num_periods):
        col_c = get_column_letter(i)
        cell = ws.cell(row=20, column=i, value=f"={col_c}18-{col_c}19")
        cell.font = BLACK_FORMULA_BOLD
        cell.number_format = NUM_FMT_ACCOUNTING
        cell.border = TOTAL_BORDER

    # Row 21: Net Margin % -> Formula =B20/B6
    ws.cell(row=21, column=1, value="Net Margin %").font = MUTED_LABEL_FONT
    for i in range(2, 2 + num_periods):
        col_c = get_column_letter(i)
        cell = ws.cell(row=21, column=i, value=f"=IF({col_c}6>0,{col_c}20/{col_c}6,0)")
        cell.font = BLACK_FORMULA_FONT
        cell.number_format = NUM_FMT_PERCENTAGE
        cell.border = DATA_BORDER

    # Row 22: Diluted EPS
    ws.cell(row=22, column=1, value="Diluted EPS").font = SECTION_LABEL_FONT
    for i, v in enumerate(eps_vals, start=2):
        cell = ws.cell(row=22, column=i, value=v)
        cell.font = BLUE_INPUT_FONT
        cell.number_format = NUM_FMT_PER_SHARE
        cell.border = DATA_BORDER

    # -------------------------------------------------------------
    # 2. BALANCE SHEET (Rows 24 to 37)
    # -------------------------------------------------------------
    ws.merge_cells(f"A24:{last_col_letter}24")
    ws["A24"] = "2. BALANCE SHEET"
    ws["A24"].font = SUBHEADER_FONT
    ws["A24"].fill = SUBHEADER_FILL
    ws.row_dimensions[24].height = 18

    cash_vals = []
    rec_vals = []
    inv_vals = []
    ca_vals = []
    ppe_vals = []
    ta_vals = []
    cl_vals = []
    debt_vals = []
    liab_vals = []
    eq_vals = []

    for p in annual_periods:
        m = p.metrics_json or {}
        cash = m.get("cash_and_equivalents")
        rec = m.get("accounts_receivable") or m.get("receivables")
        inv = m.get("inventory")
        ca = m.get("current_assets")
        ta = m.get("total_assets")
        ppe = m.get("property_plant_equipment") or m.get("non_current_assets")
        if ppe is None and ta is not None and ca is not None:
            ppe = ta - ca
        cl = m.get("current_liabilities")
        debt = m.get("total_debt")
        liab = m.get("total_liabilities")
        eq = m.get("total_equity") or m.get("stockholders_equity")

        cash_vals.append((cash / scale_factor) if cash is not None else 0.0)
        rec_vals.append((rec / scale_factor) if rec is not None else 0.0)
        inv_vals.append((inv / scale_factor) if inv is not None else 0.0)
        ca_vals.append((ca / scale_factor) if ca is not None else 0.0)
        ppe_vals.append((ppe / scale_factor) if ppe is not None else 0.0)
        ta_vals.append((ta / scale_factor) if ta is not None else 0.0)
        cl_vals.append((cl / scale_factor) if cl is not None else 0.0)
        debt_vals.append((debt / scale_factor) if debt is not None else 0.0)
        liab_vals.append((liab / scale_factor) if liab is not None else 0.0)
        eq_vals.append((eq / scale_factor) if eq is not None else 0.0)

    # Row 25: Cash & Equivalents
    ws.cell(row=25, column=1, value="Cash & Cash Equivalents").font = SECTION_LABEL_FONT
    for i, v in enumerate(cash_vals, start=2):
        c = ws.cell(row=25, column=i, value=v)
        c.font = BLUE_INPUT_FONT
        c.number_format = NUM_FMT_ACCOUNTING
        c.border = DATA_BORDER

    # Row 26: Accounts Receivable
    ws.cell(row=26, column=1, value="Accounts Receivable").font = BLACK_FORMULA_FONT
    for i, v in enumerate(rec_vals, start=2):
        c = ws.cell(row=26, column=i, value=v)
        c.font = BLUE_INPUT_FONT
        c.number_format = NUM_FMT_ACCOUNTING
        c.border = DATA_BORDER

    # Row 27: Inventory
    ws.cell(row=27, column=1, value="Inventory").font = BLACK_FORMULA_FONT
    for i, v in enumerate(inv_vals, start=2):
        c = ws.cell(row=27, column=i, value=v)
        c.font = BLUE_INPUT_FONT
        c.number_format = NUM_FMT_ACCOUNTING
        c.border = DATA_BORDER

    # Row 28: Total Current Assets
    ws.cell(row=28, column=1, value="Total Current Assets").font = BLACK_FORMULA_BOLD
    for i, v in enumerate(ca_vals, start=2):
        c = ws.cell(row=28, column=i, value=v)
        c.font = BLUE_INPUT_BOLD
        c.number_format = NUM_FMT_ACCOUNTING
        c.border = DATA_BORDER

    # Row 29: PPE & Non-Current Assets
    ws.cell(row=29, column=1, value="Property, Plant & Equipment / Non-Current Assets").font = BLACK_FORMULA_FONT
    for i, v in enumerate(ppe_vals, start=2):
        c = ws.cell(row=29, column=i, value=v)
        c.font = BLUE_INPUT_FONT
        c.number_format = NUM_FMT_ACCOUNTING
        c.border = DATA_BORDER

    # Row 30: Total Assets
    ws.cell(row=30, column=1, value="Total Assets").font = BLACK_FORMULA_BOLD
    for i, v in enumerate(ta_vals, start=2):
        c = ws.cell(row=30, column=i, value=v)
        c.font = BLUE_INPUT_BOLD
        c.number_format = NUM_FMT_ACCOUNTING
        c.border = TOTAL_BORDER

    # Row 31: Current Liabilities
    ws.cell(row=31, column=1, value="Current Liabilities").font = BLACK_FORMULA_FONT
    for i, v in enumerate(cl_vals, start=2):
        c = ws.cell(row=31, column=i, value=v)
        c.font = BLUE_INPUT_FONT
        c.number_format = NUM_FMT_ACCOUNTING
        c.border = DATA_BORDER

    # Row 32: Total Debt
    ws.cell(row=32, column=1, value="Total Debt (Short-Term + Long-Term)").font = SECTION_LABEL_FONT
    for i, v in enumerate(debt_vals, start=2):
        c = ws.cell(row=32, column=i, value=v)
        c.font = BLUE_INPUT_FONT
        c.number_format = NUM_FMT_ACCOUNTING
        c.border = DATA_BORDER

    # Row 33: Total Liabilities
    ws.cell(row=33, column=1, value="Total Liabilities").font = BLACK_FORMULA_FONT
    for i, v in enumerate(liab_vals, start=2):
        c = ws.cell(row=33, column=i, value=v)
        c.font = BLUE_INPUT_FONT
        c.number_format = NUM_FMT_ACCOUNTING
        c.border = DATA_BORDER

    # Row 34: Total Stockholders' Equity
    ws.cell(row=34, column=1, value="Total Stockholders' Equity").font = BLACK_FORMULA_BOLD
    for i, v in enumerate(eq_vals, start=2):
        c = ws.cell(row=34, column=i, value=v)
        c.font = BLUE_INPUT_BOLD
        c.number_format = NUM_FMT_ACCOUNTING
        c.border = TOTAL_BORDER

    # Memo Row 35: Net Debt -> Formula =B32-B25
    ws.cell(row=35, column=1, value="Net Debt (Total Debt - Cash)").font = BLACK_FORMULA_BOLD
    for i in range(2, 2 + num_periods):
        col_c = get_column_letter(i)
        cell = ws.cell(row=35, column=i, value=f"={col_c}32-{col_c}25")
        cell.font = BLACK_FORMULA_BOLD
        cell.number_format = NUM_FMT_ACCOUNTING
        cell.border = DATA_BORDER

    # Memo Row 36: Net Working Capital -> Formula =B28-B31
    ws.cell(row=36, column=1, value="Net Working Capital (Current Assets - Current Liabilities)").font = MUTED_LABEL_FONT
    for i in range(2, 2 + num_periods):
        col_c = get_column_letter(i)
        cell = ws.cell(row=36, column=i, value=f"={col_c}28-{col_c}31")
        cell.font = BLACK_FORMULA_FONT
        cell.number_format = NUM_FMT_ACCOUNTING
        cell.border = DATA_BORDER

    # Memo Row 37: Invested Capital -> Formula =B35+B34
    ws.cell(row=37, column=1, value="Invested Capital (Net Debt + Equity)").font = BLACK_FORMULA_BOLD
    for i in range(2, 2 + num_periods):
        col_c = get_column_letter(i)
        cell = ws.cell(row=37, column=i, value=f"={col_c}35+{col_c}34")
        cell.font = BLACK_FORMULA_BOLD
        cell.number_format = NUM_FMT_ACCOUNTING
        cell.border = DATA_BORDER

    # -------------------------------------------------------------
    # 3. CASH FLOW STATEMENT (Rows 39 to 46)
    # -------------------------------------------------------------
    ws.merge_cells(f"A39:{last_col_letter}39")
    ws["A39"] = "3. CASH FLOW STATEMENT"
    ws["A39"].font = SUBHEADER_FONT
    ws["A39"].fill = SUBHEADER_FILL
    ws.row_dimensions[39].height = 18

    ocf_vals = []
    cfi_vals = []
    capex_vals = []
    cff_vals = []

    for p in annual_periods:
        m = p.metrics_json or {}
        ocf = m.get("operating_cash_flow") or m.get("cfo")
        cfi = m.get("investing_cash_flow") or m.get("cfi")
        capex = m.get("capital_expenditure") or m.get("capex")
        cff = m.get("financing_cash_flow") or m.get("cff")

        ocf_vals.append((ocf / scale_factor) if ocf is not None else 0.0)
        cfi_vals.append((cfi / scale_factor) if cfi is not None else 0.0)
        capex_vals.append((abs(capex) / scale_factor) if capex is not None else 0.0)
        cff_vals.append((cff / scale_factor) if cff is not None else 0.0)

    # Row 40: Operating Cash Flow
    ws.cell(row=40, column=1, value="Cash Flow from Operating Activities (OCF)").font = SECTION_LABEL_FONT
    for i, v in enumerate(ocf_vals, start=2):
        c = ws.cell(row=40, column=i, value=v)
        c.font = BLUE_INPUT_BOLD
        c.number_format = NUM_FMT_ACCOUNTING
        c.border = DATA_BORDER

    # Row 41: Investing Cash Flow
    ws.cell(row=41, column=1, value="Cash Flow from Investing Activities (CFI)").font = BLACK_FORMULA_FONT
    for i, v in enumerate(cfi_vals, start=2):
        c = ws.cell(row=41, column=i, value=v)
        c.font = BLUE_INPUT_FONT
        c.number_format = NUM_FMT_ACCOUNTING
        c.border = DATA_BORDER

    # Row 42: (-) Capital Expenditure (CapEx)
    ws.cell(row=42, column=1, value="(-) Capital Expenditure (CapEx)").font = BLACK_FORMULA_FONT
    for i, v in enumerate(capex_vals, start=2):
        c = ws.cell(row=42, column=i, value=v)
        c.font = BLUE_INPUT_FONT
        c.number_format = NUM_FMT_ACCOUNTING
        c.border = DATA_BORDER

    # Row 43: Financing Cash Flow
    ws.cell(row=43, column=1, value="Cash Flow from Financing Activities (CFF)").font = BLACK_FORMULA_FONT
    for i, v in enumerate(cff_vals, start=2):
        c = ws.cell(row=43, column=i, value=v)
        c.font = BLUE_INPUT_FONT
        c.number_format = NUM_FMT_ACCOUNTING
        c.border = DATA_BORDER

    # Row 44: (=) Net Change in Cash -> Formula =B40+B41+B43
    ws.cell(row=44, column=1, value="(=) Net Change in Cash").font = BLACK_FORMULA_BOLD
    for i in range(2, 2 + num_periods):
        col_c = get_column_letter(i)
        cell = ws.cell(row=44, column=i, value=f"={col_c}40+{col_c}41+{col_c}43")
        cell.font = BLACK_FORMULA_BOLD
        cell.number_format = NUM_FMT_ACCOUNTING
        cell.border = DATA_BORDER

    # Row 45: (=) Free Cash Flow -> Formula =B40-ABS(B42)
    ws.cell(row=45, column=1, value="(=) Free Cash Flow (OCF - |CapEx|)").font = BLACK_FORMULA_BOLD
    for i in range(2, 2 + num_periods):
        col_c = get_column_letter(i)
        cell = ws.cell(row=45, column=i, value=f"={col_c}40-ABS({col_c}42)")
        cell.font = BLACK_FORMULA_BOLD
        cell.number_format = NUM_FMT_ACCOUNTING
        cell.border = TOTAL_BORDER

    # Row 46: CFO / EBITDA % -> Formula =B40/B11
    ws.cell(row=46, column=1, value="CFO / EBITDA % (Cash Conversion)").font = MUTED_LABEL_FONT
    for i in range(2, 2 + num_periods):
        col_c = get_column_letter(i)
        cell = ws.cell(row=46, column=i, value=f"=IF({col_c}11>0,{col_c}40/{col_c}11,0)")
        cell.font = BLACK_FORMULA_FONT
        cell.number_format = NUM_FMT_PERCENTAGE
        cell.border = DATA_BORDER

    autofit_columns(ws, min_col=1, max_col=1 + num_periods)


# =============================================================================
# TAB 3: RATIOS & PEERS
# =============================================================================
def _build_tab3_ratios_and_peers(
    wb: openpyxl.Workbook,
    company: Company,
    annual_periods: List[FinancialPeriod],
    peer_data: Dict[str, Any],
    currency_symbol: str,
    scale_label: str,
    scale_factor: float
):
    ws = wb.create_sheet(title="Ratios & Peers")
    ws.views.sheetView[0].showGridLines = True
    ws.freeze_panes = "B5"

    num_periods = len(annual_periods)
    first_year_col = "B"
    last_year_col = get_column_letter(1 + num_periods)
    avg_col = get_column_letter(2 + num_periods)
    med_col = get_column_letter(3 + num_periods)

    # Title Block
    ws.merge_cells(f"A1:{med_col}1")
    ws["A1"] = f"FinSight AI — Financial Ratios & Peer Benchmarking"
    ws["A1"].font = TITLE_FONT
    ws["A1"].fill = NAVY_FILL
    ws["A1"].alignment = Alignment(horizontal="left", vertical="center", indent=1)
    ws.row_dimensions[1].height = 28

    ws["A2"] = scale_label
    ws["A2"].font = MUTED_LABEL_FONT

    # Section 1 Headers: Row 4
    ws.cell(row=4, column=1, value="Financial Ratio / Efficiency Metric").fill = NAVY_FILL
    ws.cell(row=4, column=1).font = HEADER_FONT

    for col_idx, p in enumerate(annual_periods, start=2):
        yr_label = f"FY{p.fiscal_year}" if p.fiscal_year else (p.fiscal_period or f"Period {col_idx-1}")
        c = ws.cell(row=4, column=col_idx, value=yr_label)
        c.fill = NAVY_FILL
        c.font = HEADER_FONT
        c.alignment = Alignment(horizontal="right")

    c_avg = ws.cell(row=4, column=2 + num_periods, value="Average")
    c_avg.fill = NAVY_FILL
    c_avg.font = HEADER_FONT
    c_avg.alignment = Alignment(horizontal="right")

    c_med = ws.cell(row=4, column=3 + num_periods, value="Median")
    c_med.fill = NAVY_FILL
    c_med.font = HEADER_FONT
    c_med.alignment = Alignment(horizontal="right")
    ws.row_dimensions[4].height = 20

    # Section 1: Historical Financial Ratios
    ws.merge_cells(f"A5:{med_col}5")
    ws["A5"] = "1. HISTORICAL FINANCIAL & PROFITABILITY RATIOS (LINKED TO 3-STATEMENT MODEL)"
    ws["A5"].font = SUBHEADER_FONT
    ws["A5"].fill = SUBHEADER_FILL
    ws.row_dimensions[5].height = 18

    # Mapping of ratios linked directly to Tab 2 ('3-Statement Financials')
    # Row indices in '3-Statement Financials':
    # Rev=6, GP_Margin=9, EBITDA_Margin=12, EBIT=14, EBIT_Margin=15, NetInc=20, NetMargin=21
    # Cash=25, Rec=26, Inv=27, CurrAssets=28, TotAssets=30, CurrLiab=31, Debt=32, Equity=34, InvestedCap=37
    ratio_definitions = [
        ("Gross Margin %", lambda c: f"='3-Statement Financials'!{c}9", NUM_FMT_PERCENTAGE),
        ("EBITDA Margin %", lambda c: f"='3-Statement Financials'!{c}12", NUM_FMT_PERCENTAGE),
        ("Operating Profit Margin (OPM) %", lambda c: f"='3-Statement Financials'!{c}15", NUM_FMT_PERCENTAGE),
        ("Net Profit Margin %", lambda c: f"='3-Statement Financials'!{c}21", NUM_FMT_PERCENTAGE),
        ("Return on Equity (ROE) %", lambda c: f"=IF('3-Statement Financials'!{c}34>0,'3-Statement Financials'!{c}20/'3-Statement Financials'!{c}34,0)", NUM_FMT_PERCENTAGE),
        ("Return on Assets (ROA) %", lambda c: f"=IF('3-Statement Financials'!{c}30>0,'3-Statement Financials'!{c}20/'3-Statement Financials'!{c}30,0)", NUM_FMT_PERCENTAGE),
        ("Return on Capital Employed (ROCE) %", lambda c: f"=IF('3-Statement Financials'!{c}37>0,'3-Statement Financials'!{c}14/'3-Statement Financials'!{c}37,0)", NUM_FMT_PERCENTAGE),
        ("Current Ratio", lambda c: f"=IF('3-Statement Financials'!{c}31>0,'3-Statement Financials'!{c}28/'3-Statement Financials'!{c}31,0)", NUM_FMT_MULTIPLE),
        ("Debt to Equity Ratio", lambda c: f"=IF('3-Statement Financials'!{c}34>0,'3-Statement Financials'!{c}32/'3-Statement Financials'!{c}34,0)", NUM_FMT_MULTIPLE),
        ("Asset Turnover Ratio", lambda c: f"=IF('3-Statement Financials'!{c}30>0,'3-Statement Financials'!{c}6/'3-Statement Financials'!{c}30,0)", NUM_FMT_MULTIPLE),
    ]

    for idx, (label, formula_func, fmt) in enumerate(ratio_definitions, start=6):
        c1 = ws.cell(row=idx, column=1, value=label)
        c1.font = SECTION_LABEL_FONT
        c1.border = DATA_BORDER

        for col_i in range(2, 2 + num_periods):
            col_letter = get_column_letter(col_i)
            cell = ws.cell(row=idx, column=col_i, value=formula_func(col_letter))
            cell.font = GREEN_LINK_FONT
            cell.number_format = fmt
            cell.border = DATA_BORDER

        # Average Formula
        c_a = ws.cell(row=idx, column=2 + num_periods, value=f"=AVERAGE({first_year_col}{idx}:{last_year_col}{idx})")
        c_a.font = BLACK_FORMULA_BOLD
        c_a.number_format = fmt
        c_a.border = DATA_BORDER

        # Median Formula
        c_m = ws.cell(row=idx, column=3 + num_periods, value=f"=MEDIAN({first_year_col}{idx}:{last_year_col}{idx})")
        c_m.font = BLACK_FORMULA_BOLD
        c_m.number_format = fmt
        c_m.border = DATA_BORDER

    # -------------------------------------------------------------
    # Section 2: Sector Peer Comparison
    # -------------------------------------------------------------
    sec2_start = 18
    ws.merge_cells(f"A{sec2_start}:{med_col}{sec2_start}")
    ws[f"A{sec2_start}"] = "2. SECTOR PEER BENCHMARKING (SAME-CURRENCY / MARKET-CAP PEERS)"
    ws[f"A{sec2_start}"].font = SUBHEADER_FONT
    ws[f"A{sec2_start}"].fill = SUBHEADER_FILL
    ws.row_dimensions[sec2_start].height = 18

    peer_headers = [
        "Company Name",
        "Ticker",
        f"Market Cap ({currency_symbol} {'Cr' if currency_symbol == '₹' else 'M'})",
        f"Share Price ({currency_symbol})",
        "P/E Ratio",
        "EV / EBITDA",
        "EBITDA Margin %",
        "P/B Ratio",
        "ROE %"
    ]
    peer_hdr_row = sec2_start + 1
    for col_idx, h in enumerate(peer_headers, start=1):
        cell = ws.cell(row=peer_hdr_row, column=col_idx, value=h)
        cell.font = HEADER_FONT
        cell.fill = NAVY_FILL
        cell.alignment = Alignment(horizontal="right" if col_idx > 2 else "left")
    ws.row_dimensions[peer_hdr_row].height = 20

    # Collect peers: target + peer list
    target_p = peer_data.get("target") or {}
    peers_list = peer_data.get("peers") or []
    all_peer_rows = []

    if target_p:
        all_peer_rows.append((target_p, True))
    for p in peers_list[:6]:
        all_peer_rows.append((p, False))

    current_p_row = peer_hdr_row + 1
    first_peer_data_row = current_p_row

    for p_info, is_target in all_peer_rows:
        name_val = sanitize_text(p_info.get("name") or p_info.get("company_name") or p_info.get("symbol") or "Peer")
        sym_val = sanitize_text(p_info.get("symbol") or "")
        mcap_val = p_info.get("market_cap")
        if mcap_val is not None:
            mcap_val = mcap_val / scale_factor
        price_val = p_info.get("price")
        pe_val = p_info.get("pe_ratio")
        ev_ebitda_val = p_info.get("ev_to_ebitda")
        ebitda_margin_val = p_info.get("ebitda_margin_pct")
        if ebitda_margin_val is not None:
            ebitda_margin_val = ebitda_margin_val / 100.0  # as decimal for 0.00%
        pb_val = p_info.get("price_to_book")
        roe_val = p_info.get("roe_pct")
        if roe_val is not None:
            roe_val = roe_val / 100.0

        p_items = [
            (name_val, "@"),
            (sym_val, "@"),
            (mcap_val, NUM_FMT_ACCOUNTING),
            (price_val, NUM_FMT_PER_SHARE),
            (pe_val, NUM_FMT_MULTIPLE),
            (ev_ebitda_val, NUM_FMT_MULTIPLE),
            (ebitda_margin_val, NUM_FMT_PERCENTAGE),
            (pb_val, NUM_FMT_MULTIPLE),
            (roe_val, NUM_FMT_PERCENTAGE),
        ]

        for col_idx, (val, fmt) in enumerate(p_items, start=1):
            cell = ws.cell(row=current_p_row, column=col_idx, value=val)
            if is_target:
                cell.font = BLACK_FORMULA_BOLD
                cell.fill = HIGHLIGHT_FILL
            else:
                cell.font = BLACK_FORMULA_FONT
            cell.number_format = fmt
            cell.border = DATA_BORDER
            if col_idx > 2:
                cell.alignment = Alignment(horizontal="right")
        current_p_row += 1

    last_peer_data_row = current_p_row - 1

    # Add Median and Average Benchmark Rows
    if last_peer_data_row >= first_peer_data_row:
        # Median Benchmark Row
        ws.cell(row=current_p_row, column=1, value="= MEDIAN BENCHMARK").font = BLACK_FORMULA_BOLD
        ws.cell(row=current_p_row, column=2, value="MEDIAN").font = MUTED_LABEL_FONT
        ws.cell(row=current_p_row, column=1).border = DATA_BORDER
        ws.cell(row=current_p_row, column=2).border = DATA_BORDER

        for col_idx, fmt in [(3, NUM_FMT_ACCOUNTING), (4, NUM_FMT_PER_SHARE), (5, NUM_FMT_MULTIPLE), (6, NUM_FMT_MULTIPLE), (7, NUM_FMT_PERCENTAGE), (8, NUM_FMT_MULTIPLE), (9, NUM_FMT_PERCENTAGE)]:
            col_letter = get_column_letter(col_idx)
            cell = ws.cell(row=current_p_row, column=col_idx, value=f"=MEDIAN({col_letter}{first_peer_data_row}:{col_letter}{last_peer_data_row})")
            cell.font = BLACK_FORMULA_BOLD
            cell.number_format = fmt
            cell.border = DATA_BORDER
            cell.alignment = Alignment(horizontal="right")
        current_p_row += 1

        # Average Benchmark Row
        ws.cell(row=current_p_row, column=1, value="= AVERAGE BENCHMARK").font = BLACK_FORMULA_BOLD
        ws.cell(row=current_p_row, column=2, value="AVERAGE").font = MUTED_LABEL_FONT
        ws.cell(row=current_p_row, column=1).border = TOTAL_BORDER
        ws.cell(row=current_p_row, column=2).border = TOTAL_BORDER

        for col_idx, fmt in [(3, NUM_FMT_ACCOUNTING), (4, NUM_FMT_PER_SHARE), (5, NUM_FMT_MULTIPLE), (6, NUM_FMT_MULTIPLE), (7, NUM_FMT_PERCENTAGE), (8, NUM_FMT_MULTIPLE), (9, NUM_FMT_PERCENTAGE)]:
            col_letter = get_column_letter(col_idx)
            cell = ws.cell(row=current_p_row, column=col_idx, value=f"=AVERAGE({col_letter}{first_peer_data_row}:{col_letter}{last_peer_data_row})")
            cell.font = BLACK_FORMULA_BOLD
            cell.number_format = fmt
            cell.border = TOTAL_BORDER
            cell.alignment = Alignment(horizontal="right")

    autofit_columns(ws, min_col=1, max_col=max(10, 3 + num_periods))


# =============================================================================
# TAB 4: DCF VALUATION
# =============================================================================
def _build_tab4_dcf_valuation(
    wb: openpyxl.Workbook,
    company: Company,
    dcf_res: Any,
    currency_symbol: str,
    scale_label: str,
    scale_factor: float,
    proj_years: int
):
    ws = wb.create_sheet(title="DCF Valuation")
    ws.views.sheetView[0].showGridLines = True
    ws.freeze_panes = "C5"

    last_proj_col_letter = get_column_letter(3 + proj_years)  # Col D is Yr 1, Col D+N-1 is Yr N

    # Title Block
    ws.merge_cells(f"A1:{last_proj_col_letter}1")
    ws["A1"] = f"FinSight AI — Institutional DCF Valuation Model & Sensitivity Analysis"
    ws["A1"].font = TITLE_FONT
    ws["A1"].fill = NAVY_FILL
    ws["A1"].alignment = Alignment(horizontal="left", vertical="center", indent=1)
    ws.row_dimensions[1].height = 28

    ws["A2"] = scale_label
    ws["A2"].font = MUTED_LABEL_FONT

    # -------------------------------------------------------------
    # 1. EDITABLE ASSUMPTIONS BLOCK (Rows 4 to 11)
    # -------------------------------------------------------------
    ws.merge_cells(f"A4:{last_proj_col_letter}4")
    ws["A4"] = "1. KEY VALUATION ASSUMPTIONS (EDITABLE BLUE FONT)"
    ws["A4"].font = SUBHEADER_FONT
    ws["A4"].fill = SUBHEADER_FILL
    ws.row_dimensions[4].height = 18

    # Headers for Assumptions
    for col_idx, h in enumerate(["Assumption Parameter", "Model Value", "Unit / Metric", "Model Significance / Notes"], start=1):
        cell = ws.cell(row=5, column=col_idx, value=h)
        cell.font = SUBHEADER_FONT
        cell.fill = SUBHEADER_FILL

    base_fcf_scaled = dcf_res.fcf_base / scale_factor
    net_debt_scaled = dcf_res.net_debt / scale_factor
    shares_scaled = dcf_res.shares_outstanding / scale_factor

    # Rows 6 to 12
    assumptions_data = [
        (6, "Base Year Free Cash Flow (FCF_0)", base_fcf_scaled, NUM_FMT_ACCOUNTING, f"{currency_symbol} {'Cr' if currency_symbol == '₹' else 'M'}", "Normalized or latest annual FCF"),
        (7, "Projected Annual FCF Growth Rate (g)", dcf_res.growth_rate, NUM_FMT_PERCENTAGE, "% Annual", "5Y historical CAGR or analyst consensus"),
        (8, "Weighted Average Cost of Capital (WACC)", dcf_res.wacc, NUM_FMT_PERCENTAGE, "% Discount", "CAPM hurdle rate based on beta & risk-free rate"),
        (9, "Perpetual Terminal Growth Rate (g_term)", dcf_res.terminal_growth_rate, NUM_FMT_PERCENTAGE, "% Perpetual", "Long-term GDP growth constraint"),
        (10, "Net Debt (Total Debt - Cash)", net_debt_scaled, NUM_FMT_ACCOUNTING, f"{currency_symbol} {'Cr' if currency_symbol == '₹' else 'M'}", "From latest balance sheet memo row"),
        (11, "Current Market Share Price", dcf_res.current_price, NUM_FMT_PER_SHARE, f"{currency_symbol} per share", "Current live exchange quotation"),
        (12, "Diluted Shares Outstanding", shares_scaled, NUM_FMT_ACCOUNTING, f"{'Cr' if currency_symbol == '₹' else 'M'} shares", "Total diluted share count"),
    ]

    for r_idx, label, val, fmt, unit, note in assumptions_data:
        c1 = ws.cell(row=r_idx, column=1, value=label)
        c2 = ws.cell(row=r_idx, column=2, value=val)  # Value in Column B
        c3 = ws.cell(row=r_idx, column=3, value=unit)
        c4 = ws.cell(row=r_idx, column=4, value=note)

        c1.font = SECTION_LABEL_FONT
        c2.font = BLUE_INPUT_BOLD  # Blue font for editable inputs!
        c3.font = MUTED_LABEL_FONT
        c4.font = MUTED_LABEL_FONT

        c1.border = DATA_BORDER
        c2.border = DATA_BORDER
        c3.border = DATA_BORDER
        c4.border = DATA_BORDER
        c2.number_format = fmt

    # -------------------------------------------------------------
    # 2. PROJECTION SCHEDULE (Rows 14 to 18)
    # -------------------------------------------------------------
    ws.merge_cells(f"A14:{last_proj_col_letter}14")
    ws["A14"] = f"2. DISCOUNTED CASH FLOW PROJECTION SCHEDULE ({proj_years}-YEAR HORIZON)"
    ws["A14"].font = SUBHEADER_FONT
    ws["A14"].fill = SUBHEADER_FILL
    ws.row_dimensions[14].height = 18

    # Row 15: Column Headers
    ws.cell(row=15, column=1, value="Projection Line Item").fill = NAVY_FILL
    ws.cell(row=15, column=1).font = HEADER_FONT

    for y in range(1, proj_years + 1):
        col_c = get_column_letter(3 + y)  # Col D is Year 1
        cell = ws.cell(row=15, column=3 + y, value=f"Year {y}")
        cell.fill = NAVY_FILL
        cell.font = HEADER_FONT
        cell.alignment = Alignment(horizontal="right")
    ws.row_dimensions[15].height = 20

    # Row 16: Projected Free Cash Flow (FCF)
    ws.cell(row=16, column=1, value="Projected Free Cash Flow (FCF)").font = SECTION_LABEL_FONT
    # Year 1 (Col D): =$B$6*(1+$B$7)
    ws.cell(row=16, column=4, value="=$B$6*(1+$B$7)").font = BLACK_FORMULA_BOLD
    ws.cell(row=16, column=4).number_format = NUM_FMT_ACCOUNTING
    ws.cell(row=16, column=4).border = DATA_BORDER

    # Year 2+ : =Prev*(1+$B$7)
    for y in range(2, proj_years + 1):
        prev_col = get_column_letter(2 + y + 1)
        curr_col = get_column_letter(3 + y)
        cell = ws.cell(row=16, column=3 + y, value=f"={prev_col}16*(1+$B$7)")
        cell.font = BLACK_FORMULA_BOLD
        cell.number_format = NUM_FMT_ACCOUNTING
        cell.border = DATA_BORDER

    # Row 17: Discount Period (t)
    ws.cell(row=17, column=1, value="Discount Period (t)").font = MUTED_LABEL_FONT
    for y in range(1, proj_years + 1):
        cell = ws.cell(row=17, column=3 + y, value=y)
        cell.font = BLACK_FORMULA_FONT
        cell.number_format = NUM_FMT_INTEGER
        cell.border = DATA_BORDER
        cell.alignment = Alignment(horizontal="right")

    # Row 18: Discount Factor (1 / (1 + WACC)^t)
    ws.cell(row=18, column=1, value="Discount Factor [1 / (1 + WACC)^t]").font = MUTED_LABEL_FONT
    for y in range(1, proj_years + 1):
        curr_col = get_column_letter(3 + y)
        cell = ws.cell(row=18, column=3 + y, value=f"=1/(1+$B$8)^{curr_col}17")
        cell.font = BLACK_FORMULA_FONT
        cell.number_format = NUM_FMT_FACTOR
        cell.border = DATA_BORDER

    # Row 19: Present Value of FCF (PV)
    ws.cell(row=19, column=1, value="Present Value of FCF (PV)").font = BLACK_FORMULA_BOLD
    for y in range(1, proj_years + 1):
        curr_col = get_column_letter(3 + y)
        cell = ws.cell(row=19, column=3 + y, value=f"={curr_col}16*{curr_col}18")
        cell.font = BLACK_FORMULA_BOLD
        cell.number_format = NUM_FMT_ACCOUNTING
        cell.border = TOTAL_BORDER

    # -------------------------------------------------------------
    # 3. TERMINAL VALUE & EQUITY BRIDGE (Rows 21 to 32)
    # -------------------------------------------------------------
    ws.merge_cells(f"A21:{last_proj_col_letter}21")
    ws["A21"] = "3. TERMINAL VALUE & EQUITY VALUE BRIDGE"
    ws["A21"].font = SUBHEADER_FONT
    ws["A21"].fill = SUBHEADER_FILL
    ws.row_dimensions[21].height = 18

    last_fcf_cell = f"{last_proj_col_letter}16"
    last_pv_cell = f"{last_proj_col_letter}19"

    # Bridge Line items (placed in Column B for Value, Column C for Unit, Column D for Formula)
    bridge_lines = [
        (22, "Cumulative PV of Projection Period FCFs", f"=SUM(D19:{last_pv_cell})", NUM_FMT_ACCOUNTING, f"{currency_symbol} {'Cr' if currency_symbol == '₹' else 'M'}", f"=SUM(D19:{last_pv_cell})"),
        (23, "Terminal Year Normalized FCF (FCF_N+1)", f"={last_fcf_cell}*(1+$B$9)", NUM_FMT_ACCOUNTING, f"{currency_symbol} {'Cr' if currency_symbol == '₹' else 'M'}", f"={last_fcf_cell}*(1+$B$9)"),
        (24, "Perpetual Terminal Value (Gordon Growth)", f"=B23/($B$8-$B$9)", NUM_FMT_ACCOUNTING, f"{currency_symbol} {'Cr' if currency_symbol == '₹' else 'M'}", "=FCF_N+1 / (WACC - g_term)"),
        (25, "Present Value of Terminal Value", f"=B24/(1+$B$8)^{proj_years}", NUM_FMT_ACCOUNTING, f"{currency_symbol} {'Cr' if currency_symbol == '₹' else 'M'}", f"=Terminal Value / (1+WACC)^{proj_years}"),
        (26, "Enterprise Value (EV)", "=B22+B25", NUM_FMT_ACCOUNTING, f"{currency_symbol} {'Cr' if currency_symbol == '₹' else 'M'}", "=PV(FCFs) + PV(Terminal Value)"),
        (27, "Less: Net Debt", "=$B$10", NUM_FMT_ACCOUNTING, f"{currency_symbol} {'Cr' if currency_symbol == '₹' else 'M'}", "=Net Debt (Total Debt - Cash)"),
        (28, "Implied Equity Value", "=B26-B27", NUM_FMT_ACCOUNTING, f"{currency_symbol} {'Cr' if currency_symbol == '₹' else 'M'}", "=Enterprise Value - Net Debt"),
        (29, "Diluted Shares Outstanding", "=$B$12", NUM_FMT_ACCOUNTING, f"{'Cr' if currency_symbol == '₹' else 'M'} shares", "=Diluted share count"),
        (30, "Intrinsic Value per Share", "=B28/B29", NUM_FMT_PER_SHARE, f"{currency_symbol} per share", "=Equity Value / Shares"),
        (31, "Current Market Share Price", "=$B$11", NUM_FMT_PER_SHARE, f"{currency_symbol} per share", "=Current Market Price"),
        (32, "Implied Upside / (Downside) %", "=(B30/B31)-1", NUM_FMT_PERCENTAGE, "% Return", "=(Intrinsic / Price) - 1"),
    ]

    for r_idx, label, formula_str, fmt, unit, note in bridge_lines:
        c1 = ws.cell(row=r_idx, column=1, value=label)
        c2 = ws.cell(row=r_idx, column=2, value=formula_str)
        c3 = ws.cell(row=r_idx, column=3, value=unit)
        c4 = ws.cell(row=r_idx, column=4, value=note)

        is_subtotal = r_idx in (26, 28, 30, 32)
        c1.font = BLACK_FORMULA_BOLD if is_subtotal else SECTION_LABEL_FONT
        c2.font = BLACK_FORMULA_BOLD if is_subtotal else BLACK_FORMULA_FONT
        c3.font = MUTED_LABEL_FONT
        c4.font = MUTED_LABEL_FONT

        c1.border = TOTAL_BORDER if is_subtotal else DATA_BORDER
        c2.border = TOTAL_BORDER if is_subtotal else DATA_BORDER
        c3.border = DATA_BORDER
        c4.border = DATA_BORDER
        c2.number_format = fmt

    # -------------------------------------------------------------
    # 4. FORMULA-DRIVEN 5x5 SENSITIVITY MATRIX (Rows 34 to 41)
    # -------------------------------------------------------------
    ws.merge_cells(f"A34:{last_proj_col_letter}34")
    ws["A34"] = f"4. VALUATION SENSITIVITY MATRIX: INTRINSIC VALUE PER SHARE ({currency_symbol})"
    ws["A34"].font = SUBHEADER_FONT
    ws["A34"].fill = SUBHEADER_FILL
    ws.row_dimensions[34].height = 18

    # Matrix Headers: Row 35
    # Terminal Growth rates across Columns C, D, E, F, G
    ws.cell(row=35, column=2, value="WACC \\ g_term").fill = NAVY_FILL
    ws.cell(row=35, column=2).font = HEADER_FONT

    col_offsets = [(-0.010, "Base - 1.0%"), (-0.005, "Base - 0.5%"), (0.000, "Base Rate"), (0.005, "Base + 0.5%"), (0.010, "Base + 1.0%")]
    for col_idx, (offset, lbl) in enumerate(col_offsets, start=3):
        col_c = get_column_letter(col_idx)
        # Live formula referencing $B$9 (Terminal Growth Rate)
        formula_g = f"=$B$9+{offset}" if offset != 0.0 else "=$B$9"
        cell = ws.cell(row=35, column=col_idx, value=formula_g)
        cell.fill = NAVY_FILL
        cell.font = HEADER_FONT
        cell.number_format = NUM_FMT_PERCENTAGE
        cell.alignment = Alignment(horizontal="right")
    ws.row_dimensions[35].height = 20

    # WACC rows: Rows 36 to 40
    row_offsets = [(-0.020, "Base - 2.0%"), (-0.010, "Base - 1.0%"), (0.000, "Base WACC"), (0.010, "Base + 1.0%"), (0.020, "Base + 2.0%")]
    for row_idx, (w_offset, lbl) in enumerate(row_offsets, start=36):
        # Column B contains WACC live formula referencing $B$8
        formula_w = f"=$B$8+{w_offset}" if w_offset != 0.0 else "=$B$8"
        cell_w = ws.cell(row=row_idx, column=2, value=formula_w)
        cell_w.fill = NAVY_FILL if w_offset == 0.0 else SUBHEADER_FILL
        cell_w.font = HEADER_FONT
        cell_w.number_format = NUM_FMT_PERCENTAGE
        cell_w.alignment = Alignment(horizontal="right")

        # In each cell (row_idx, col_idx):
        # We calculate the exact intrinsic share price via closed-form live formula:
        # =(NPV($B{row_idx}, $D$16:${last_proj_col_letter}$16) + (${last_fcf_cell} * (1 + {col}$35) / ($B{row_idx} - {col}$35)) / ((1 + $B{row_idx})^{proj_years}) - $B$10) / $B$12
        for col_idx in range(3, 8):
            col_letter = get_column_letter(col_idx)
            sens_formula = (
                f"=(NPV($B{row_idx}, $D$16:${last_proj_col_letter}$16) + "
                f"(${last_fcf_cell}*(1+{col_letter}$35)/($B{row_idx}-{col_letter}$35))/((1+$B{row_idx})^{proj_years}) - $B$10)/$B$12"
            )
            val_cell = ws.cell(row=row_idx, column=col_idx, value=sens_formula)
            is_base = (w_offset == 0.0 and col_idx == 5)
            val_cell.font = BLACK_FORMULA_BOLD if is_base else BLACK_FORMULA_FONT
            if is_base:
                val_cell.fill = HIGHLIGHT_FILL
            val_cell.number_format = NUM_FMT_PER_SHARE
            val_cell.border = TOTAL_BORDER if is_base else DATA_BORDER
            val_cell.alignment = Alignment(horizontal="right")

    autofit_columns(ws, min_col=1, max_col=max(9, 4 + proj_years))
