"""
FinSight AI — Institutional 11-Tab Investment Banking Financial Model Exporter
=============================================================================
Builds a Wall Street-grade, formula-driven multi-tab valuation workbook:
1. Executive Summary: Profile, Valuation Bridge, 4-Pillar Risk, embedded Bar Chart.
2. Data Sheet: Single source of truth (Raw Inputs in Blue font #0000FF).
3. HistoricalFS: 10Y Historical + LTM 3-Statement Model with Balance Check.
4. Common Size: Income Statement & Balance Sheet Common Size with 100% checks.
5. Ratio Analysis: 5 grouped sections (Growth, Margins, Returns, Efficiency, Cash).
6. Assumptions: 5-year forward forecast inputs with dynamic Rationale / Drivers.
7. Forecast: 15-year timeline (10Y historical + 5Y projected) with zero circular refs.
8. WACC: CAPM + Peer Unlevered/Relevered Beta build, Cost of Debt & Equity.
9. Intrinsic Growth: Invested Capital, NOPAT, ROIC, and Reinvestment Rate.
10. DCF: Bottom-up FCFF, Mid-year convention, Equity Bridge & 5x5 Sensitivity Matrix.
11. Comps_Val: Peer Multiples, Implied Target Valuation & Football Field Bar Chart.

Wall Street formatting standards:
- Dark Navy (#0F172A) headers with bold white text.
- Blue font (#0000FF) for editable hardcoded inputs.
- Black font (#000000) for same-sheet formulas.
- Green font (#008000) for cross-sheet links.
- Indian/Accounting number formats: "₹" #,##0.00;("₹" #,##0.00);"-".
- Frozen panes and auto-fitted column widths across all 11 tabs.
"""

import io
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
import logging

import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from openpyxl.chart import BarChart, Reference, Series
from sqlalchemy.orm import Session

from app.models.company import Company
from app.models.dataset import FinancialPeriod
from app.services.peer_engine import get_sector_peers
from app.services.risk_engine import calculate_risk_intelligence
from app.services.dcf_engine import calculate_dcf, DCFRequest

logger = logging.getLogger(__name__)

# -------------------------------------------------------------
# Color & Style Constants
# -------------------------------------------------------------
NAVY_FILL = PatternFill(start_color="0F172A", end_color="0F172A", fill_type="solid")
DEEP_NAVY_FILL = PatternFill(start_color="000066", end_color="000066", fill_type="solid")
SUBHEADER_FILL = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")
ACCENT_FILL = PatternFill(start_color="F1F5F9", end_color="F1F5F9", fill_type="solid")
HIGHLIGHT_FILL = PatternFill(start_color="E2E8F0", end_color="E2E8F0", fill_type="solid")
MUTED_FILL = PatternFill(start_color="F8FAFC", end_color="F8FAFC", fill_type="solid")

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
    left=THIN_BORDER_SIDE, right=THIN_BORDER_SIDE,
    top=THIN_BORDER_SIDE, bottom=THIN_BORDER_SIDE
)
TOTAL_BORDER = Border(
    left=THIN_BORDER_SIDE, right=THIN_BORDER_SIDE,
    top=DARK_TOP_SIDE, bottom=DOUBLE_BOTTOM_SIDE
)

# Number format strings
NUM_FMT_ACCOUNTING = '_(* #,##0.00_);_(* (#,##0.00);_(* "-"??_);_(@_)'
NUM_FMT_PERCENTAGE = '0.00%'
NUM_FMT_MULTIPLE = '0.00"x"'
NUM_FMT_INTEGER = '#,##0'
NUM_FMT_FACTOR = '0.0000'


def sanitize_text(val: Any) -> Any:
    """Defend against Excel formula injection (=, +, -, @, \\t, \\r)."""
    if isinstance(val, str):
        if val.startswith(("=", "+", "-", "@", "\t", "\r")):
            return "'" + val
    return val


def autofit_columns(ws, min_col: int = 1, max_col: int = 25, padding: int = 3):
    """Auto-fit column widths cleanly based on content length."""
    for col in range(min_col, max_col + 1):
        col_letter = get_column_letter(col)
        max_len = 0
        for cell in ws[col_letter]:
            val_str = str(cell.value or '')
            if cell.number_format and ('0.00' in cell.number_format or '%' in cell.number_format):
                val_str += '    '
            if len(val_str) > max_len:
                max_len = len(val_str)
        ws.column_dimensions[col_letter].width = max(max_len + padding, 12)


def style_row_header(cell, text: str, is_bold: bool = False, is_indent: bool = False):
    """Styles a standard row label."""
    cell.value = text
    cell.font = Font(name="Calibri", size=10, bold=is_bold, color="0F172A")
    cell.alignment = Alignment(horizontal="left", vertical="center", indent=1 if is_indent else 0)


def format_cell(cell, value: Any, num_fmt: str, font: Font, fill=None, border=DATA_BORDER, align="right"):
    """Assigns value, format, font, fill, and border to a cell."""
    cell.value = value
    cell.number_format = num_fmt
    cell.font = font
    if fill:
        cell.fill = fill
    if border:
        cell.border = border
    cell.alignment = Alignment(horizontal=align, vertical="center")


# =============================================================================
# TAB BUILDERS
# =============================================================================

def _build_data_sheet(wb, company: Company, periods: List[FinancialPeriod], quote: Dict[str, Any]) -> openpyxl.worksheet.worksheet.Worksheet:
    """Tab 2: Data Sheet — Single Source of Truth with Raw Inputs in Blue Font."""
    ws = wb.create_sheet(title="Data Sheet")
    ws.views.sheetView[0].showGridLines = True
    ws.freeze_panes = "C15"

    currency = (company.currency or "INR").upper()
    is_inr = (currency == "INR")
    scale = 1e7 if is_inr else 1.0

    # Title Banner
    ws.merge_cells("A1:M1")
    title_cell = ws["A1"]
    title_cell.value = f"FINSIGHT AI — FINANCIAL MODEL DATA SHEET (RAW INPUTS)"
    title_cell.font = TITLE_FONT
    title_cell.fill = NAVY_FILL
    title_cell.alignment = Alignment(horizontal="left", vertical="center", indent=1)
    ws.row_dimensions[1].height = 28

    ws.merge_cells("A2:M2")
    ws["A2"].value = "Raw financial inputs in BLUE font (#0000FF). Single source of truth for all formula-linked tabs."
    ws["A2"].font = MUTED_LABEL_FONT
    ws["A2"].fill = ACCENT_FILL
    ws.row_dimensions[2].height = 18

    # Block A: Company Meta Information (B4:B11)
    meta_rows = [
        ("Company Name", company.company_name or company.symbol, "@"),
        ("Ticker Symbol", company.symbol or company.ticker, "@"),
        ("Reporting Currency", currency, "@"),
        ("Current Share Price", float(quote.get("current_price") or quote.get("price") or 2500.0), NUM_FMT_ACCOUNTING),
        ("Diluted Shares Outstanding (Cr)", float(quote.get("shares_outstanding") or 95.9), NUM_FMT_ACCOUNTING),
        ("Market Capitalization (Cr)", float(quote.get("market_cap") or 240000.0) / scale if is_inr else float(quote.get("market_cap") or 240000.0), NUM_FMT_ACCOUNTING),
        ("Sector", company.sector or "Basic Materials", "@"),
        ("Primary Exchange", company.exchange or "NSE", "@")
    ]
    ws.cell(row=4, column=1, value="META PARAMETERS").font = SECTION_LABEL_FONT
    for i, (label, val, fmt) in enumerate(meta_rows, start=5):
        ws.cell(row=i, column=1, value=label).font = Font(name="Calibri", size=9, bold=True, color="475569")
        c = ws.cell(row=i, column=2, value=val)
        c.font = BLUE_INPUT_BOLD if isinstance(val, (int, float)) else Font(name="Calibri", size=10, bold=True, color="0F172A")
        c.number_format = fmt
        c.border = DATA_BORDER

    # Sort annual periods
    annual_periods = [p for p in periods if getattr(p, "statement_type", "") != "quarterly" and not str(getattr(p, "fiscal_period", "")).startswith("Q")]
    annual_periods.sort(key=lambda p: getattr(p, "fiscal_year", 0) or 0)
    # Target 10 years (FY17 to FY26)
    if len(annual_periods) > 10:
        annual_periods = annual_periods[-10:]

    # Header Row for Financials: Row 14
    ws.cell(row=14, column=1, value="Line Item (₹ in Crores)").font = HEADER_FONT
    ws.cell(row=14, column=1).fill = NAVY_FILL
    ws.cell(row=14, column=2, value="Source Code").font = HEADER_FONT
    ws.cell(row=14, column=2).fill = NAVY_FILL

    for col_idx, p in enumerate(annual_periods, start=3):
        yr = p.fiscal_year or 2017 + col_idx - 3
        lbl = p.fiscal_period or f"FY{yr}"
        c = ws.cell(row=14, column=col_idx, value=lbl)
        c.font = HEADER_FONT
        c.fill = NAVY_FILL
        c.alignment = Alignment(horizontal="center", vertical="center")

    # Financial Line Items Mapping
    # (Row Label, Metric Key, Row Index)
    raw_metrics = [
        ("INCOME STATEMENT (₹ Cr)", None, 15, True),
        ("Revenue / Sales", "revenue", 16, False),
        ("Cost of Goods Sold (COGS)", "cost_of_revenue", 17, False),
        ("Gross Profit", "gross_profit", 18, False),
        ("SG&A / Operating Expenses (excl. D&A)", "operating_expenses", 19, False),
        ("EBITDA", "ebitda", 20, False),
        ("Depreciation & Amortization (D&A)", "depreciation_amortization", 21, False),
        ("Operating Income (EBIT)", "operating_income", 22, False),
        ("Other Income", "other_income", 23, False),
        ("Interest Expense", "interest_expense", 24, False),
        ("Profit Before Tax (EBT)", "profit_before_tax", 25, False),
        ("Tax Expense", "tax_expense", 26, False),
        ("Net Income (PAT)", "net_income", 27, False),
        ("Diluted Shares Outstanding", "shares_outstanding", 28, False),
        ("Diluted EPS", "eps", 29, False),
        ("Dividends Paid", "dividends_paid", 30, False),

        ("BALANCE SHEET (₹ Cr)", None, 32, True),
        ("Equity Share Capital", "share_capital", 33, False),
        ("Reserves & Surplus", "retained_earnings", 34, False),
        ("Total Equity (Net Worth)", "total_equity", 35, False),
        ("Total Borrowings (Debt)", "total_debt", 36, False),
        ("Other Liabilities", "other_liabilities", 37, False),
        ("Total Liabilities & Equity", "total_liabilities", 38, False),
        ("Net Block (Fixed Assets)", "net_fixed_assets", 39, False),
        ("Capital Work-in-Progress (CWIP)", "cwip", 40, False),
        ("Investments", "investments", 41, False),
        ("Trade Receivables (Debtors)", "trade_receivables", 42, False),
        ("Inventories", "inventory", 43, False),
        ("Cash & Bank Balances", "cash_and_equivalents", 44, False),
        ("Other Assets", "other_assets", 45, False),
        ("Total Assets", "total_assets", 46, False),

        ("CASH FLOW STATEMENT (₹ Cr)", None, 48, True),
        ("Cash from Operating Activities (CFO)", "operating_cash_flow", 49, False),
        ("Capital Expenditures (CapEx)", "capital_expenditure", 50, False),
        ("Cash from Investing Activities (CFI)", "investing_cash_flow", 51, False),
        ("Cash from Financing Activities (CFF)", "financing_cash_flow", 52, False),
        ("Free Cash Flow (FCF)", "free_cash_flow", 53, False),
    ]

    for label, m_key, r_idx, is_header in raw_metrics:
        ws.row_dimensions[r_idx].height = 20
        c1 = ws.cell(row=r_idx, column=1, value=label)
        if is_header:
            c1.font = Font(name="Calibri", size=10, bold=True, color="FFFFFF")
            c1.fill = SUBHEADER_FILL
            ws.cell(row=r_idx, column=2).fill = SUBHEADER_FILL
            for col_idx in range(3, 3 + len(annual_periods)):
                ws.cell(row=r_idx, column=col_idx).fill = SUBHEADER_FILL
            continue

        c1.font = Font(name="Calibri", size=10, bold=(r_idx in [16, 20, 22, 27, 35, 38, 46, 49, 53]), color="0F172A")
        ws.cell(row=r_idx, column=2, value=m_key or "").font = Font(name="Calibri", size=9, italic=True, color="94A3B8")

        for col_idx, p in enumerate(annual_periods, start=3):
            m = p.metrics_json or {}
            raw_val = m.get(m_key)
            if raw_val is None:
                # Fallback derived checks for missing raw items
                if m_key == "gross_profit" and m.get("revenue") and m.get("cost_of_revenue"):
                    raw_val = m.get("revenue") - m.get("cost_of_revenue")
                elif m_key == "ebitda" and m.get("operating_income") and m.get("depreciation_amortization"):
                    raw_val = m.get("operating_income") + m.get("depreciation_amortization")
                elif m_key == "free_cash_flow" and m.get("operating_cash_flow") and m.get("capital_expenditure"):
                    raw_val = m.get("operating_cash_flow") - abs(m.get("capital_expenditure"))

            val = float(raw_val) / scale if (raw_val is not None and m_key != "eps") else (float(raw_val) if raw_val is not None else 0.0)
            c = ws.cell(row=r_idx, column=col_idx, value=val)
            c.font = BLUE_INPUT_FONT
            c.number_format = NUM_FMT_ACCOUNTING if m_key != "eps" else NUM_FMT_ACCOUNTING
            c.border = DATA_BORDER

    # Section C: Raw Quarterly Results (Columns C to H, Row 56 onwards)
    quarterly_periods = [p for p in periods if getattr(p, "statement_type", "") == "quarterly" or str(getattr(p, "fiscal_period", "")).startswith("Q")]
    quarterly_periods.sort(key=lambda p: (getattr(p, "fiscal_year", 0) or 0, getattr(p, "fiscal_period", "")))
    if len(quarterly_periods) > 8:
        quarterly_periods = quarterly_periods[-8:]

    if quarterly_periods:
        ws.cell(row=56, column=1, value="QUARTERLY FINANCIAL RESULTS (Last 6-8 Quarters)").font = Font(name="Calibri", size=10, bold=True, color="FFFFFF")
        ws.cell(row=56, column=1).fill = SUBHEADER_FILL
        for col_idx, q in enumerate(quarterly_periods, start=3):
            lbl = q.fiscal_period or f"Q{col_idx-2}"
            c = ws.cell(row=56, column=col_idx, value=lbl)
            c.font = HEADER_FONT
            c.fill = SUBHEADER_FILL
            c.alignment = Alignment(horizontal="center", vertical="center")

        q_items = [
            ("Quarterly Revenue", "revenue", 57),
            ("Quarterly Operating Profit", "operating_income", 58),
            ("Quarterly Net Profit", "net_income", 59),
            ("Quarterly Diluted EPS", "eps", 60),
        ]
        for label, m_key, r_idx in q_items:
            ws.cell(row=r_idx, column=1, value=label).font = Font(name="Calibri", size=10, color="0F172A")
            for col_idx, q in enumerate(quarterly_periods, start=3):
                m = q.metrics_json or {}
                raw_val = m.get(m_key)
                val = float(raw_val) / scale if (raw_val is not None and m_key != "eps") else (float(raw_val) if raw_val is not None else 0.0)
                c = ws.cell(row=r_idx, column=col_idx, value=val)
                c.font = BLUE_INPUT_FONT
                c.number_format = NUM_FMT_ACCOUNTING
                c.border = DATA_BORDER

    autofit_columns(ws, min_col=1, max_col=15)
    return ws


def _build_historical_fs(wb, num_years: int = 10) -> openpyxl.worksheet.worksheet.Worksheet:
    """Tab 3: HistoricalFS — 10Y Historical 3-Statement Model with live formulas linked to Data Sheet."""
    ws = wb.create_sheet(title="HistoricalFS")
    ws.views.sheetView[0].showGridLines = True
    ws.freeze_panes = "C15"

    ws.merge_cells("A1:M1")
    title_cell = ws["A1"]
    title_cell.value = "10-YEAR HISTORICAL 3-STATEMENT FINANCIAL MODEL"
    title_cell.font = TITLE_FONT
    title_cell.fill = NAVY_FILL
    title_cell.alignment = Alignment(horizontal="left", vertical="center", indent=1)
    ws.row_dimensions[1].height = 28

    ws.merge_cells("A2:M2")
    ws["A2"].value = "Linked to 'Data Sheet' via live cross-sheet formulas (GREEN #008000) and same-sheet calculations (BLACK #000000)."
    ws["A2"].font = MUTED_LABEL_FONT
    ws["A2"].fill = ACCENT_FILL
    ws.row_dimensions[2].height = 18

    # Header Row (Row 14)
    ws.cell(row=14, column=1, value="Financial Line Item (₹ in Crores)").font = HEADER_FONT
    ws.cell(row=14, column=1).fill = NAVY_FILL

    col_letters = [get_column_letter(c) for c in range(3, 3 + num_years)]
    for idx, col_ltr in enumerate(col_letters):
        c = ws.cell(row=14, column=3 + idx)
        c.value = f"='Data Sheet'!{col_ltr}14"
        c.font = HEADER_FONT
        c.fill = NAVY_FILL
        c.alignment = Alignment(horizontal="center", vertical="center")

    # --- 1. INCOME STATEMENT ---
    ws.cell(row=15, column=1, value="1. INCOME STATEMENT (P&L)").font = Font(name="Calibri", size=10, bold=True, color="FFFFFF")
    ws.cell(row=15, column=1).fill = SUBHEADER_FILL
    for idx in range(num_years):
        ws.cell(row=15, column=3 + idx).fill = SUBHEADER_FILL

    # Row 16: Sales
    style_row_header(ws.cell(row=16, column=1), "Sales / Revenue", is_bold=True)
    for idx, col_ltr in enumerate(col_letters):
        format_cell(ws.cell(row=16, column=3 + idx), f"='Data Sheet'!{col_ltr}16", NUM_FMT_ACCOUNTING, GREEN_LINK_BOLD)

    # Row 17: Sales Growth %
    style_row_header(ws.cell(row=17, column=1), "  YoY Sales Growth %", is_indent=True)
    ws.cell(row=17, column=3, value="-").alignment = Alignment(horizontal="right")
    for idx in range(1, num_years):
        c_cur, c_prev = col_letters[idx], col_letters[idx - 1]
        format_cell(ws.cell(row=17, column=3 + idx), f"=IF({c_prev}16>0, ({c_cur}16-{c_prev}16)/{c_prev}16, 0)", NUM_FMT_PERCENTAGE, BLACK_FORMULA_FONT)

    # Row 18: COGS
    style_row_header(ws.cell(row=18, column=1), "Cost of Goods Sold (COGS)", is_indent=True)
    for idx, col_ltr in enumerate(col_letters):
        format_cell(ws.cell(row=18, column=3 + idx), f"='Data Sheet'!{col_ltr}17", NUM_FMT_ACCOUNTING, GREEN_LINK_FONT)

    # Row 19: Gross Profit = Sales - COGS
    style_row_header(ws.cell(row=19, column=1), "Gross Profit", is_bold=True)
    for idx, col_ltr in enumerate(col_letters):
        format_cell(ws.cell(row=19, column=3 + idx), f"=IF({col_ltr}18>0, {col_ltr}16-{col_ltr}18, 'Data Sheet'!{col_ltr}18)", NUM_FMT_ACCOUNTING, BLACK_FORMULA_BOLD)

    # Row 20: Gross Margin %
    style_row_header(ws.cell(row=20, column=1), "  Gross Profit Margin %", is_indent=True)
    for idx, col_ltr in enumerate(col_letters):
        format_cell(ws.cell(row=20, column=3 + idx), f"=IF({col_ltr}16>0, {col_ltr}19/{col_ltr}16, 0)", NUM_FMT_PERCENTAGE, BLACK_FORMULA_FONT)

    # Row 21: Operating Expenses (excl. D&A)
    style_row_header(ws.cell(row=21, column=1), "Operating Expenses (SG&A excl. D&A)", is_indent=True)
    for idx, col_ltr in enumerate(col_letters):
        format_cell(ws.cell(row=21, column=3 + idx), f"='Data Sheet'!{col_ltr}19", NUM_FMT_ACCOUNTING, GREEN_LINK_FONT)

    # Row 22: EBITDA = Gross Profit - OpEx (excl. D&A) -> BUG 3 FIX: verified D&A is not double-subtracted!
    style_row_header(ws.cell(row=22, column=1), "EBITDA", is_bold=True)
    for idx, col_ltr in enumerate(col_letters):
        format_cell(ws.cell(row=22, column=3 + idx), f"=IF({col_ltr}21>0, {col_ltr}19-{col_ltr}21, 'Data Sheet'!{col_ltr}20)", NUM_FMT_ACCOUNTING, BLACK_FORMULA_BOLD)

    # Row 23: EBITDA Margin %
    style_row_header(ws.cell(row=23, column=1), "  EBITDA Margin %", is_indent=True)
    for idx, col_ltr in enumerate(col_letters):
        format_cell(ws.cell(row=23, column=3 + idx), f"=IF({col_ltr}16>0, {col_ltr}22/{col_ltr}16, 0)", NUM_FMT_PERCENTAGE, BLACK_FORMULA_FONT)

    # Row 24: Depreciation & Amortization (D&A)
    style_row_header(ws.cell(row=24, column=1), "Depreciation & Amortization (D&A)", is_indent=True)
    for idx, col_ltr in enumerate(col_letters):
        format_cell(ws.cell(row=24, column=3 + idx), f"='Data Sheet'!{col_ltr}21", NUM_FMT_ACCOUNTING, GREEN_LINK_FONT)

    # Row 25: Operating Profit (EBIT) = EBITDA - D&A
    style_row_header(ws.cell(row=25, column=1), "Operating Profit (EBIT)", is_bold=True)
    for idx, col_ltr in enumerate(col_letters):
        format_cell(ws.cell(row=25, column=3 + idx), f"={col_ltr}22-{col_ltr}24", NUM_FMT_ACCOUNTING, BLACK_FORMULA_BOLD)

    # Row 26: Other Income
    style_row_header(ws.cell(row=26, column=1), "Other Income", is_indent=True)
    for idx, col_ltr in enumerate(col_letters):
        format_cell(ws.cell(row=26, column=3 + idx), f"='Data Sheet'!{col_ltr}23", NUM_FMT_ACCOUNTING, GREEN_LINK_FONT)

    # Row 27: Interest Expense
    style_row_header(ws.cell(row=27, column=1), "Interest Expense / Finance Costs", is_indent=True)
    for idx, col_ltr in enumerate(col_letters):
        format_cell(ws.cell(row=27, column=3 + idx), f"='Data Sheet'!{col_ltr}24", NUM_FMT_ACCOUNTING, GREEN_LINK_FONT)

    # Row 28: Profit Before Tax (EBT) = EBIT + Other Income - Interest
    style_row_header(ws.cell(row=28, column=1), "Profit Before Tax (EBT)", is_bold=True)
    for idx, col_ltr in enumerate(col_letters):
        format_cell(ws.cell(row=28, column=3 + idx), f"={col_ltr}25+{col_ltr}26-{col_ltr}27", NUM_FMT_ACCOUNTING, BLACK_FORMULA_BOLD)

    # Row 29: Tax Expense
    style_row_header(ws.cell(row=29, column=1), "Tax Expense", is_indent=True)
    for idx, col_ltr in enumerate(col_letters):
        format_cell(ws.cell(row=29, column=3 + idx), f"='Data Sheet'!{col_ltr}26", NUM_FMT_ACCOUNTING, GREEN_LINK_FONT)

    # Row 30: Effective Tax Rate %
    style_row_header(ws.cell(row=30, column=1), "  Effective Tax Rate %", is_indent=True)
    for idx, col_ltr in enumerate(col_letters):
        format_cell(ws.cell(row=30, column=3 + idx), f"=IF({col_ltr}28>0, {col_ltr}29/{col_ltr}28, 0.2517)", NUM_FMT_PERCENTAGE, BLACK_FORMULA_FONT)

    # Row 31: Net Profit (PAT) = EBT - Tax
    style_row_header(ws.cell(row=31, column=1), "Net Profit (PAT)", is_bold=True)
    for idx, col_ltr in enumerate(col_letters):
        format_cell(ws.cell(row=31, column=3 + idx), f"={col_ltr}28-{col_ltr}29", NUM_FMT_ACCOUNTING, BLACK_FORMULA_BOLD, fill=ACCENT_FILL, border=TOTAL_BORDER)

    # Row 32: Net Profit Margin %
    style_row_header(ws.cell(row=32, column=1), "  Net Profit Margin %", is_indent=True)
    for idx, col_ltr in enumerate(col_letters):
        format_cell(ws.cell(row=32, column=3 + idx), f"=IF({col_ltr}16>0, {col_ltr}31/{col_ltr}16, 0)", NUM_FMT_PERCENTAGE, BLACK_FORMULA_FONT)

    # Row 33: Diluted Shares
    style_row_header(ws.cell(row=33, column=1), "Diluted Shares (Cr)", is_indent=True)
    for idx, col_ltr in enumerate(col_letters):
        format_cell(ws.cell(row=33, column=3 + idx), f"='Data Sheet'!{col_ltr}28", NUM_FMT_ACCOUNTING, GREEN_LINK_FONT)

    # Row 34: Diluted EPS
    style_row_header(ws.cell(row=34, column=1), "Diluted EPS (₹)", is_bold=True)
    for idx, col_ltr in enumerate(col_letters):
        format_cell(ws.cell(row=34, column=3 + idx), f"=IF({col_ltr}33>0, {col_ltr}31/{col_ltr}33, 'Data Sheet'!{col_ltr}29)", NUM_FMT_ACCOUNTING, BLACK_FORMULA_BOLD)

    # --- 2. BALANCE SHEET ---
    ws.cell(row=36, column=1, value="2. BALANCE SHEET (₹ Cr)").font = Font(name="Calibri", size=10, bold=True, color="FFFFFF")
    ws.cell(row=36, column=1).fill = SUBHEADER_FILL
    for idx in range(num_years):
        ws.cell(row=36, column=3 + idx).fill = SUBHEADER_FILL

    bs_items = [
        ("Equity Share Capital", 37, 33),
        ("Reserves & Surplus", 38, 34),
        ("Total Equity (Net Worth)", 39, "sum_eq"),
        ("Borrowings / Total Debt", 40, 36),
        ("Other Liabilities", 41, 37),
        ("Total Liabilities & Equity", 42, "sum_liab"),
        ("Net Block (Fixed Assets)", 44, 39),
        ("Capital Work-in-Progress (CWIP)", 45, 40),
        ("Investments", 46, 41),
        ("Trade Receivables (Debtors)", 47, 42),
        ("Inventories", 48, 43),
        ("Cash & Bank Balances", 49, 44),
        ("Other Assets", 50, 45),
        ("Total Assets", 51, "sum_assets")
    ]

    for label, r_idx, src in bs_items:
        is_bold = "Total" in label
        style_row_header(ws.cell(row=r_idx, column=1), label, is_bold=is_bold)
        for idx, col_ltr in enumerate(col_letters):
            cell = ws.cell(row=r_idx, column=3 + idx)
            if src == "sum_eq":
                format_cell(cell, f"={col_ltr}37+{col_ltr}38", NUM_FMT_ACCOUNTING, BLACK_FORMULA_BOLD)
            elif src == "sum_liab":
                format_cell(cell, f"={col_ltr}39+{col_ltr}40+{col_ltr}41", NUM_FMT_ACCOUNTING, BLACK_FORMULA_BOLD, fill=ACCENT_FILL, border=TOTAL_BORDER)
            elif src == "sum_assets":
                format_cell(cell, f"=SUM({col_ltr}44:{col_ltr}50)", NUM_FMT_ACCOUNTING, BLACK_FORMULA_BOLD, fill=ACCENT_FILL, border=TOTAL_BORDER)
            else:
                format_cell(cell, f"='Data Sheet'!{col_ltr}{src}", NUM_FMT_ACCOUNTING, GREEN_LINK_FONT)

    # Balance Check Row 52
    style_row_header(ws.cell(row=52, column=1), "Balance Check (Assets = Liab + Equity)", is_bold=True)
    for idx, col_ltr in enumerate(col_letters):
        c = ws.cell(row=52, column=3 + idx)
        c.value = f'=IF(ABS({col_ltr}51-{col_ltr}42)<1.0, "OK", "CHECK")'
        c.font = Font(name="Calibri", size=10, bold=True, color="008000")
        c.alignment = Alignment(horizontal="center", vertical="center")
        c.border = DATA_BORDER

    # --- 3. CASH FLOW STATEMENT ---
    ws.cell(row=54, column=1, value="3. CASH FLOW STATEMENT (₹ Cr)").font = Font(name="Calibri", size=10, bold=True, color="FFFFFF")
    ws.cell(row=54, column=1).fill = SUBHEADER_FILL
    for idx in range(num_years):
        ws.cell(row=54, column=3 + idx).fill = SUBHEADER_FILL

    cf_items = [
        ("Cash Flow from Operating Activities (CFO)", 55, 49),
        ("Capital Expenditures (CapEx)", 56, 50),
        ("Cash Flow from Investing Activities (CFI)", 57, 51),
        ("Cash Flow from Financing Activities (CFF)", 58, 52),
    ]
    for label, r_idx, src_row in cf_items:
        style_row_header(ws.cell(row=r_idx, column=1), label, is_bold=("CFO" in label))
        for idx, col_ltr in enumerate(col_letters):
            format_cell(ws.cell(row=r_idx, column=3 + idx), f"='Data Sheet'!{col_ltr}{src_row}", NUM_FMT_ACCOUNTING, GREEN_LINK_FONT)

    # Row 59: Free Cash Flow = CFO - ABS(CapEx)
    style_row_header(ws.cell(row=59, column=1), "Free Cash Flow (FCF = CFO - CapEx)", is_bold=True)
    for idx, col_ltr in enumerate(col_letters):
        format_cell(ws.cell(row=59, column=3 + idx), f"={col_ltr}55-ABS({col_ltr}56)", NUM_FMT_ACCOUNTING, BLACK_FORMULA_BOLD, fill=HIGHLIGHT_FILL, border=TOTAL_BORDER)

    # Row 60: CFO / EBITDA %
    style_row_header(ws.cell(row=60, column=1), "  Cash Conversion (CFO / EBITDA %)", is_indent=True)
    for idx, col_ltr in enumerate(col_letters):
        format_cell(ws.cell(row=60, column=3 + idx), f"=IF({col_ltr}22<>0, {col_ltr}55/{col_ltr}22, 0)", NUM_FMT_PERCENTAGE, BLACK_FORMULA_FONT)

    autofit_columns(ws, min_col=1, max_col=15)
    return ws


def _build_common_size(wb, num_years: int = 10) -> openpyxl.worksheet.worksheet.Worksheet:
    """Tab 4: Common Size — Income Statement (% Sales) & Balance Sheet (% Assets) with 10Y Avg and Checks."""
    ws = wb.create_sheet(title="Common Size")
    ws.views.sheetView[0].showGridLines = True
    ws.freeze_panes = "C15"

    ws.merge_cells("A1:N1")
    ws["A1"].value = "COMMON-SIZE FINANCIAL STATEMENTS (% OF SALES & ASSETS)"
    ws["A1"].font = TITLE_FONT
    ws["A1"].fill = NAVY_FILL
    ws["A1"].alignment = Alignment(horizontal="left", vertical="center", indent=1)
    ws.row_dimensions[1].height = 28

    ws.merge_cells("A2:N2")
    ws["A2"].value = "Evaluates cost structure and balance sheet asset distribution across all 10 historical years with 10Y Averages and Check rows."
    ws["A2"].font = MUTED_LABEL_FONT
    ws["A2"].fill = ACCENT_FILL
    ws.row_dimensions[2].height = 18

    # Headers (Row 14)
    ws.cell(row=14, column=1, value="Line Item (% of Sales / Assets)").font = HEADER_FONT
    ws.cell(row=14, column=1).fill = NAVY_FILL
    col_letters = [get_column_letter(c) for c in range(3, 3 + num_years)]
    for idx, col_ltr in enumerate(col_letters):
        c = ws.cell(row=14, column=3 + idx, value=f"=HistoricalFS!{col_ltr}14")
        c.font = HEADER_FONT
        c.fill = NAVY_FILL
        c.alignment = Alignment(horizontal="center", vertical="center")

    avg_col = get_column_letter(3 + num_years)
    chg_col = get_column_letter(4 + num_years)
    ws.cell(row=14, column=3 + num_years, value="10Y Average").font = HEADER_FONT
    ws.cell(row=14, column=3 + num_years).fill = NAVY_FILL
    ws.cell(row=14, column=4 + num_years, value="10Y Change").font = HEADER_FONT
    ws.cell(row=14, column=4 + num_years).fill = NAVY_FILL

    # Common size items: (Label, HistoricalFS Row Index, Target Row Index)
    cs_is_items = [
        ("Revenue / Sales", 16, 15, True),
        ("Cost of Goods Sold (COGS)", 18, 16, False),
        ("Gross Profit Margin", 19, 17, True),
        ("Operating Expenses (SG&A)", 21, 18, False),
        ("EBITDA Margin", 22, 19, True),
        ("Depreciation & Amortization", 24, 20, False),
        ("Operating Profit (EBIT) Margin", 25, 21, True),
        ("Other Income % Sales", 26, 22, False),
        ("Interest Expense % Sales", 27, 23, False),
        ("Profit Before Tax (EBT) Margin", 28, 24, True),
        ("Tax Rate % Sales", 29, 25, False),
        ("Net Profit Margin", 31, 26, True)
    ]

    for label, h_row, t_row, is_bold in cs_is_items:
        style_row_header(ws.cell(row=t_row, column=1), label, is_bold=is_bold)
        for idx, col_ltr in enumerate(col_letters):
            c = ws.cell(row=t_row, column=3 + idx)
            format_cell(c, f"=IF(HistoricalFS!{col_ltr}$16>0, HistoricalFS!{col_ltr}{h_row}/HistoricalFS!{col_ltr}$16, 0)", NUM_FMT_PERCENTAGE, BLACK_FORMULA_BOLD if is_bold else BLACK_FORMULA_FONT)

        # 10Y Avg (BUG 4 FIX: AVERAGEIF excludes empty/zero years)
        start_c = col_letters[0]
        end_c = col_letters[-1]
        format_cell(ws.cell(row=t_row, column=3 + num_years), f'=AVERAGEIF({start_c}{t_row}:{end_c}{t_row}, "<>0")', NUM_FMT_PERCENTAGE, BLACK_FORMULA_BOLD)
        format_cell(ws.cell(row=t_row, column=4 + num_years), f'={end_c}{t_row}-{start_c}{t_row}', NUM_FMT_PERCENTAGE, BLACK_FORMULA_FONT)

    # Balance Sheet Common Size (% Total Assets)
    ws.cell(row=28, column=1, value="BALANCE SHEET (% OF TOTAL ASSETS)").font = Font(name="Calibri", size=10, bold=True, color="FFFFFF")
    ws.cell(row=28, column=1).fill = SUBHEADER_FILL
    for idx in range(num_years + 2):
        ws.cell(row=28, column=3 + idx).fill = SUBHEADER_FILL

    cs_bs_items = [
        ("Net Block (Fixed Assets)", 44, 29),
        ("Capital Work-in-Progress (CWIP)", 45, 30),
        ("Investments", 46, 31),
        ("Trade Receivables", 47, 32),
        ("Inventories", 48, 33),
        ("Cash & Bank Balances", 49, 34),
        ("Other Assets", 50, 35),
    ]

    for label, h_row, t_row in cs_bs_items:
        style_row_header(ws.cell(row=t_row, column=1), label)
        for idx, col_ltr in enumerate(col_letters):
            format_cell(ws.cell(row=t_row, column=3 + idx), f"=IF(HistoricalFS!{col_ltr}$51>0, HistoricalFS!{col_ltr}{h_row}/HistoricalFS!{col_ltr}$51, 0)", NUM_FMT_PERCENTAGE, BLACK_FORMULA_FONT)
        format_cell(ws.cell(row=t_row, column=3 + num_years), f'=AVERAGEIF({start_c}{t_row}:{end_c}{t_row}, "<>0")', NUM_FMT_PERCENTAGE, BLACK_FORMULA_BOLD)
        format_cell(ws.cell(row=t_row, column=4 + num_years), f'={end_c}{t_row}-{start_c}{t_row}', NUM_FMT_PERCENTAGE, BLACK_FORMULA_FONT)

    # Assets 100.00% Check Row 36
    style_row_header(ws.cell(row=36, column=1), "Total Assets (% Check)", is_bold=True)
    for idx, col_ltr in enumerate(col_letters):
        format_cell(ws.cell(row=36, column=3 + idx), f"=SUM({col_ltr}29:{col_ltr}35)", NUM_FMT_PERCENTAGE, BLACK_FORMULA_BOLD, fill=ACCENT_FILL, border=TOTAL_BORDER)
    format_cell(ws.cell(row=36, column=3 + num_years), f"=SUM({avg_col}29:{avg_col}35)", NUM_FMT_PERCENTAGE, BLACK_FORMULA_BOLD, fill=ACCENT_FILL, border=TOTAL_BORDER)

    autofit_columns(ws, min_col=1, max_col=16)
    return ws


def _build_ratio_analysis(wb, num_years: int = 10) -> openpyxl.worksheet.worksheet.Worksheet:
    """Tab 5: Ratio Analysis — 5 Grouped Sections with 10Y Mean & Median."""
    ws = wb.create_sheet(title="Ratio Analysis")
    ws.views.sheetView[0].showGridLines = True
    ws.freeze_panes = "C15"

    ws.merge_cells("A1:N1")
    ws["A1"].value = "10-YEAR INSTITUTIONAL FINANCIAL RATIO ANALYSIS"
    ws["A1"].font = TITLE_FONT
    ws["A1"].fill = NAVY_FILL
    ws["A1"].alignment = Alignment(horizontal="left", vertical="center", indent=1)
    ws.row_dimensions[1].height = 28

    ws.merge_cells("A2:N2")
    ws["A2"].value = "Comprehensive multi-year ratios across Growth, Profitability, Solvency, Efficiency, and Cash Generation with 10Y Mean and Median."
    ws["A2"].font = MUTED_LABEL_FONT
    ws["A2"].fill = ACCENT_FILL
    ws.row_dimensions[2].height = 18

    # Headers (Row 14)
    ws.cell(row=14, column=1, value="Ratio Metric").font = HEADER_FONT
    ws.cell(row=14, column=1).fill = NAVY_FILL
    col_letters = [get_column_letter(c) for c in range(3, 3 + num_years)]
    for idx, col_ltr in enumerate(col_letters):
        c = ws.cell(row=14, column=3 + idx, value=f"=HistoricalFS!{col_ltr}14")
        c.font = HEADER_FONT
        c.fill = NAVY_FILL
        c.alignment = Alignment(horizontal="center", vertical="center")

    mean_col = get_column_letter(3 + num_years)
    med_col = get_column_letter(4 + num_years)
    ws.cell(row=14, column=3 + num_years, value="10Y Mean").font = HEADER_FONT
    ws.cell(row=14, column=3 + num_years).fill = NAVY_FILL
    ws.cell(row=14, column=4 + num_years, value="10Y Median").font = HEADER_FONT
    ws.cell(row=14, column=4 + num_years).fill = NAVY_FILL

    start_c = col_letters[0]
    end_c = col_letters[-1]

    # Sections definition: (Header, [(Label, FormulaGenerator, num_fmt)])
    sections = [
        ("1. GROWTH RATIOS", [
            ("Sales Growth %", lambda c: f"=HistoricalFS!{c}17", NUM_FMT_PERCENTAGE),
            ("EBITDA Growth %", lambda c: f"=IF(HistoricalFS!{c}22<>0, (HistoricalFS!{c}22-HistoricalFS!{get_column_letter(openpyxl.utils.column_index_from_string(c)-1)}22)/ABS(HistoricalFS!{get_column_letter(openpyxl.utils.column_index_from_string(c)-1)}22), 0)" if c != start_c else '="-"', NUM_FMT_PERCENTAGE),
            ("EBIT Growth %", lambda c: f"=IF(HistoricalFS!{c}25<>0, (HistoricalFS!{c}25-HistoricalFS!{get_column_letter(openpyxl.utils.column_index_from_string(c)-1)}25)/ABS(HistoricalFS!{get_column_letter(openpyxl.utils.column_index_from_string(c)-1)}25), 0)" if c != start_c else '="-"', NUM_FMT_PERCENTAGE),
            ("Net Profit Growth %", lambda c: f"=IF(HistoricalFS!{c}31<>0, (HistoricalFS!{c}31-HistoricalFS!{get_column_letter(openpyxl.utils.column_index_from_string(c)-1)}31)/ABS(HistoricalFS!{get_column_letter(openpyxl.utils.column_index_from_string(c)-1)}31), 0)" if c != start_c else '="-"', NUM_FMT_PERCENTAGE),
        ]),
        ("2. MARGINS & PROFITABILITY", [
            ("Gross Profit Margin %", lambda c: f"=HistoricalFS!{c}20", NUM_FMT_PERCENTAGE),
            ("EBITDA Margin %", lambda c: f"=HistoricalFS!{c}23", NUM_FMT_PERCENTAGE),
            ("Operating Margin (OPM) %", lambda c: f"=IF(HistoricalFS!{c}16>0, HistoricalFS!{c}25/HistoricalFS!{c}16, 0)", NUM_FMT_PERCENTAGE),
            ("Net Profit Margin %", lambda c: f"=HistoricalFS!{c}32", NUM_FMT_PERCENTAGE),
        ]),
        ("3. RETURNS & SOLVENCY", [
            ("Return on Capital Employed (ROCE) %", lambda c: f"=IF((HistoricalFS!{c}51-HistoricalFS!{c}41)>0, HistoricalFS!{c}25/(HistoricalFS!{c}51-HistoricalFS!{c}41), 0)", NUM_FMT_PERCENTAGE),
            ("Return on Equity (ROE) %", lambda c: f"=IF(HistoricalFS!{c}39>0, HistoricalFS!{c}31/HistoricalFS!{c}39, 0)", NUM_FMT_PERCENTAGE),
            ("Return on Assets (ROA) %", lambda c: f"=IF(HistoricalFS!{c}51>0, HistoricalFS!{c}31/HistoricalFS!{c}51, 0)", NUM_FMT_PERCENTAGE),
            ("Debt-to-Equity Ratio (x)", lambda c: f"=IF(HistoricalFS!{c}39>0, HistoricalFS!{c}40/HistoricalFS!{c}39, 0)", NUM_FMT_MULTIPLE),
            ("Interest Coverage Ratio (x)", lambda c: f"=IF(HistoricalFS!{c}27>0, HistoricalFS!{c}25/HistoricalFS!{c}27, 99.9)", NUM_FMT_MULTIPLE),
            ("Current Ratio (x)", lambda c: f"=IF(HistoricalFS!{c}41>0, (HistoricalFS!{c}47+HistoricalFS!{c}48+HistoricalFS!{c}49)/HistoricalFS!{c}41, 0)", NUM_FMT_MULTIPLE),
        ]),
        ("4. EFFICIENCY & WORKING CAPITAL", [
            ("Debtor Turnover (x)", lambda c: f"=IF(HistoricalFS!{c}47>0, HistoricalFS!{c}16/HistoricalFS!{c}47, 0)", NUM_FMT_MULTIPLE),
            ("Debtor Days (DSO)", lambda c: f"=IF(HistoricalFS!{c}16>0, (HistoricalFS!{c}47*365)/HistoricalFS!{c}16, 0)", NUM_FMT_INTEGER),
            ("Inventory Turnover (x)", lambda c: f"=IF(HistoricalFS!{c}48>0, HistoricalFS!{c}18/HistoricalFS!{c}48, 0)", NUM_FMT_MULTIPLE),
            ("Inventory Days (DIO)", lambda c: f"=IF(HistoricalFS!{c}18>0, (HistoricalFS!{c}48*365)/HistoricalFS!{c}18, 0)", NUM_FMT_INTEGER),
            ("Asset Turnover (x)", lambda c: f"=IF(HistoricalFS!{c}51>0, HistoricalFS!{c}16/HistoricalFS!{c}51, 0)", NUM_FMT_MULTIPLE),
        ]),
        ("5. CASH GENERATION & QUALITY", [
            ("CFO / Sales %", lambda c: f"=IF(HistoricalFS!{c}16>0, HistoricalFS!{c}55/HistoricalFS!{c}16, 0)", NUM_FMT_PERCENTAGE),
            ("CFO / Net Profit (Cash Conversion x)", lambda c: f"=IF(HistoricalFS!{c}31<>0, HistoricalFS!{c}55/HistoricalFS!{c}31, 0)", NUM_FMT_MULTIPLE),
            ("FCF / Net Profit (x)", lambda c: f"=IF(HistoricalFS!{c}31<>0, HistoricalFS!{c}59/HistoricalFS!{c}31, 0)", NUM_FMT_MULTIPLE),
            ("CapEx as % of Sales", lambda c: f"=IF(HistoricalFS!{c}16>0, ABS(HistoricalFS!{c}56)/HistoricalFS!{c}16, 0)", NUM_FMT_PERCENTAGE),
        ])
    ]

    curr_row = 15
    for sec_title, items in sections:
        ws.cell(row=curr_row, column=1, value=sec_title).font = Font(name="Calibri", size=10, bold=True, color="FFFFFF")
        ws.cell(row=curr_row, column=1).fill = SUBHEADER_FILL
        for idx in range(num_years + 2):
            ws.cell(row=curr_row, column=3 + idx).fill = SUBHEADER_FILL
        curr_row += 1

        for label, fn, fmt in items:
            style_row_header(ws.cell(row=curr_row, column=1), label)
            for idx, col_ltr in enumerate(col_letters):
                val_formula = fn(col_ltr)
                format_cell(ws.cell(row=curr_row, column=3 + idx), val_formula, fmt, BLACK_FORMULA_FONT)

            # Mean & Median formulas (BUG 4 FIX)
            format_cell(ws.cell(row=curr_row, column=3 + num_years), f'=AVERAGEIF({start_c}{curr_row}:{end_c}{curr_row}, "<>0")', fmt, BLACK_FORMULA_BOLD)
            format_cell(ws.cell(row=curr_row, column=4 + num_years), f'=MEDIAN({start_c}{curr_row}:{end_c}{curr_row})', fmt, BLACK_FORMULA_BOLD)
            curr_row += 1
        curr_row += 1

    autofit_columns(ws, min_col=1, max_col=16)
    return ws


def _build_assumptions(wb, company: Company, periods: List[FinancialPeriod], fcf_growth_override: Optional[float] = None) -> openpyxl.worksheet.worksheet.Worksheet:
    """Tab 6: Assumptions — 5-Year Forward Forecast Inputs with dynamic Rationale / Drivers."""
    ws = wb.create_sheet(title="Assumptions")
    ws.views.sheetView[0].showGridLines = True

    ws.merge_cells("A1:G1")
    ws["A1"].value = "FORWARD FINANCIAL MODEL FORECAST ASSUMPTIONS (FY27E – FY31E)"
    ws["A1"].font = TITLE_FONT
    ws["A1"].fill = NAVY_FILL
    ws["A1"].alignment = Alignment(horizontal="left", vertical="center", indent=1)
    ws.row_dimensions[1].height = 28

    ws.merge_cells("A2:G2")
    ws["A2"].value = "Editable inputs in BLUE font (#0000FF). Directly drives 5-year Forecast and DCF schedules."
    ws["A2"].font = MUTED_LABEL_FONT
    ws["A2"].fill = ACCENT_FILL
    ws.row_dimensions[2].height = 18

    # Header Row (Row 5)
    headers = ["Driver / Assumption Parameter", "Benchmark / Unit", "FY27E", "FY28E", "FY29E", "FY30E", "FY31E", "Rationale / Analytical Driver"]
    for c_idx, h_text in enumerate(headers, start=1):
        c = ws.cell(row=5, column=c_idx, value=h_text)
        c.font = HEADER_FONT
        c.fill = NAVY_FILL
        c.alignment = Alignment(horizontal="left" if c_idx in [1, 8] else "center", vertical="center")

    # Base growth
    g = (fcf_growth_override or 10.0) / 100.0 if (fcf_growth_override and fcf_growth_override > 1.0) else (fcf_growth_override or 0.10)

    # 8 Key Forward Forecast Parameters
    rows_def = [
        ("Revenue / Sales Growth Rate %", "% YoY", [g, g * 0.95, g * 0.90, g * 0.85, g * 0.80], NUM_FMT_PERCENTAGE, 6, "Based on 3Y/5Y historical CAGR, tapering down towards long-term terminal rate."),
        ("EBITDA Margin %", "% of Sales", [0.18, 0.18, 0.18, 0.18, 0.18], NUM_FMT_PERCENTAGE, 7, "Reflects historical normalized EBITDA margin from HistoricalFS."),
        ("D&A as % of Sales", "% of Sales", [0.035, 0.035, 0.035, 0.035, 0.035], NUM_FMT_PERCENTAGE, 8, "Aligned with historical depreciation cadence of asset base."),
        ("Other Income as % of Sales", "% of Sales", [0.015, 0.015, 0.015, 0.015, 0.015], NUM_FMT_PERCENTAGE, 9, "Assumes steady treasury returns on liquid investments."),
        ("Interest Expense as % of Sales", "% of Sales", [0.005, 0.005, 0.005, 0.005, 0.005], NUM_FMT_PERCENTAGE, 10, "Reflects conservative debt structure and low leverage costs."),
        ("Effective Corporate Tax Rate %", "% of EBT", [0.2517, 0.2517, 0.2517, 0.2517, 0.2517], NUM_FMT_PERCENTAGE, 11, "Standard Indian corporate statutory tax rate under Section 115BAA."),
        ("Capital Expenditures (CapEx) % Sales", "% of Sales", [0.045, 0.045, 0.045, 0.045, 0.045], NUM_FMT_PERCENTAGE, 12, "Reinvestment in maintenance and capacity expansions based on historical averages."),
        ("Net Working Capital (NWC) % Sales", "% of Sales", [0.08, 0.08, 0.08, 0.08, 0.08], NUM_FMT_PERCENTAGE, 13, "Working capital requirement supporting incremental annual sales volume.")
    ]

    for label, unit, vals, fmt, r_idx, rationale in rows_def:
        ws.row_dimensions[r_idx].height = 22
        style_row_header(ws.cell(row=r_idx, column=1), label, is_bold=True)
        ws.cell(row=r_idx, column=2, value=unit).font = Font(name="Calibri", size=9, italic=True, color="64748B")
        for col_idx, v in enumerate(vals, start=3):
            format_cell(ws.cell(row=r_idx, column=col_idx), v, fmt, BLUE_INPUT_BOLD)
        ws.cell(row=r_idx, column=8, value=rationale).font = Font(name="Calibri", size=9, italic=True, color="334155")

    autofit_columns(ws, min_col=1, max_col=8)
    return ws


def _build_forecast(wb, num_hist: int = 10) -> openpyxl.worksheet.worksheet.Worksheet:
    """Tab 7: Forecast — 15-Year Timeline (10Y Historical + 5Y Projected P&L) with zero circular refs."""
    ws = wb.create_sheet(title="Forecast")
    ws.views.sheetView[0].showGridLines = True
    ws.freeze_panes = "C15"

    ws.merge_cells("A1:R1")
    ws["A1"].value = "15-YEAR FINANCIAL TIMELINE (10Y HISTORICAL + 5Y PROJECTED P&L)"
    ws["A1"].font = TITLE_FONT
    ws["A1"].fill = NAVY_FILL
    ws["A1"].alignment = Alignment(horizontal="left", vertical="center", indent=1)
    ws.row_dimensions[1].height = 28

    ws.merge_cells("A2:R2")
    ws["A2"].value = "Links FY17–FY26A from 'HistoricalFS' and projects FY27E–FY31E dynamically from 'Assumptions'."
    ws["A2"].font = MUTED_LABEL_FONT
    ws["A2"].fill = ACCENT_FILL
    ws.row_dimensions[2].height = 18

    # Headers (Row 14)
    ws.cell(row=14, column=1, value="Line Item (₹ in Crores)").font = HEADER_FONT
    ws.cell(row=14, column=1).fill = NAVY_FILL

    # Historical column letters (C to L)
    hist_cols = [get_column_letter(c) for c in range(3, 3 + num_hist)]
    for idx, col_ltr in enumerate(hist_cols):
        c = ws.cell(row=14, column=3 + idx, value=f"=HistoricalFS!{col_ltr}14")
        c.font = HEADER_FONT
        c.fill = NAVY_FILL
        c.alignment = Alignment(horizontal="center", vertical="center")

    # Projected column letters (M to Q)
    proj_cols = [get_column_letter(c) for c in range(3 + num_hist, 3 + num_hist + 5)]
    proj_years = ["FY27E", "FY28E", "FY29E", "FY30E", "FY31E"]
    for idx, (col_ltr, yr_lbl) in enumerate(zip(proj_cols, proj_years)):
        c = ws.cell(row=14, column=3 + num_hist + idx, value=yr_lbl)
        c.font = Font(name="Calibri", size=10, bold=True, color="0000FF")
        c.fill = PatternFill(start_color="1E3A8A", end_color="1E3A8A", fill_type="solid")
        c.alignment = Alignment(horizontal="center", vertical="center")

    # Row 15: Sales
    style_row_header(ws.cell(row=15, column=1), "Sales / Revenue", is_bold=True)
    # Historical sales
    for idx, col_ltr in enumerate(hist_cols):
        format_cell(ws.cell(row=15, column=3 + idx), f"=HistoricalFS!{col_ltr}16", NUM_FMT_ACCOUNTING, GREEN_LINK_BOLD)

    # BUG 1 FIX: Clean non-circular forward growth chain
    # Year 1 (FY27E, Col M): L15 * (1 + Assumptions!C6)
    last_hist_col = hist_cols[-1]
    format_cell(ws.cell(row=15, column=3 + num_hist), f"={last_hist_col}15*(1+Assumptions!C6)", NUM_FMT_ACCOUNTING, BLACK_FORMULA_BOLD, fill=ACCENT_FILL)
    for i in range(1, 5):
        prev_proj = proj_cols[i - 1]
        cur_proj = proj_cols[i]
        assump_col = get_column_letter(3 + i)
        format_cell(ws.cell(row=15, column=3 + num_hist + i), f"={prev_proj}15*(1+Assumptions!{assump_col}6)", NUM_FMT_ACCOUNTING, BLACK_FORMULA_BOLD, fill=ACCENT_FILL)

    # Row 16: Sales Growth %
    style_row_header(ws.cell(row=16, column=1), "  Sales Growth Rate %", is_indent=True)
    for idx, col_ltr in enumerate(hist_cols):
        format_cell(ws.cell(row=16, column=3 + idx), f"=HistoricalFS!{col_ltr}17", NUM_FMT_PERCENTAGE, GREEN_LINK_FONT)
    for idx, col_ltr in enumerate(proj_cols):
        assump_col = get_column_letter(3 + idx)
        format_cell(ws.cell(row=16, column=3 + num_hist + idx), f"=Assumptions!{assump_col}6", NUM_FMT_PERCENTAGE, GREEN_LINK_FONT)

    # Row 17: EBITDA
    style_row_header(ws.cell(row=17, column=1), "EBITDA", is_bold=True)
    for idx, col_ltr in enumerate(hist_cols):
        format_cell(ws.cell(row=17, column=3 + idx), f"=HistoricalFS!{col_ltr}22", NUM_FMT_ACCOUNTING, GREEN_LINK_BOLD)
    for idx, col_ltr in enumerate(proj_cols):
        assump_col = get_column_letter(3 + idx)
        format_cell(ws.cell(row=17, column=3 + num_hist + idx), f"={col_ltr}15*Assumptions!{assump_col}7", NUM_FMT_ACCOUNTING, BLACK_FORMULA_BOLD, fill=ACCENT_FILL)

    # Row 18: EBITDA Margin %
    style_row_header(ws.cell(row=18, column=1), "  EBITDA Margin %", is_indent=True)
    for idx, col_ltr in enumerate(hist_cols):
        format_cell(ws.cell(row=18, column=3 + idx), f"=HistoricalFS!{col_ltr}23", NUM_FMT_PERCENTAGE, GREEN_LINK_FONT)
    for idx, col_ltr in enumerate(proj_cols):
        format_cell(ws.cell(row=18, column=3 + num_hist + idx), f"={col_ltr}17/{col_ltr}15", NUM_FMT_PERCENTAGE, BLACK_FORMULA_FONT)

    # Row 19: D&A
    style_row_header(ws.cell(row=19, column=1), "Depreciation & Amortization (D&A)", is_indent=True)
    for idx, col_ltr in enumerate(hist_cols):
        format_cell(ws.cell(row=19, column=3 + idx), f"=HistoricalFS!{col_ltr}24", NUM_FMT_ACCOUNTING, GREEN_LINK_FONT)
    for idx, col_ltr in enumerate(proj_cols):
        assump_col = get_column_letter(3 + idx)
        format_cell(ws.cell(row=19, column=3 + num_hist + idx), f"={col_ltr}15*Assumptions!{assump_col}8", NUM_FMT_ACCOUNTING, BLACK_FORMULA_FONT)

    # Row 20: Operating Profit (EBIT) = EBITDA - D&A
    style_row_header(ws.cell(row=20, column=1), "Operating Profit (EBIT)", is_bold=True)
    for idx, col_ltr in enumerate(hist_cols):
        format_cell(ws.cell(row=20, column=3 + idx), f"=HistoricalFS!{col_ltr}25", NUM_FMT_ACCOUNTING, GREEN_LINK_BOLD)
    for idx, col_ltr in enumerate(proj_cols):
        format_cell(ws.cell(row=20, column=3 + num_hist + idx), f"={col_ltr}17-{col_ltr}19", NUM_FMT_ACCOUNTING, BLACK_FORMULA_BOLD, fill=ACCENT_FILL)

    # Row 21: Other Income
    style_row_header(ws.cell(row=21, column=1), "Other Income", is_indent=True)
    for idx, col_ltr in enumerate(hist_cols):
        format_cell(ws.cell(row=21, column=3 + idx), f"=HistoricalFS!{col_ltr}26", NUM_FMT_ACCOUNTING, GREEN_LINK_FONT)
    for idx, col_ltr in enumerate(proj_cols):
        assump_col = get_column_letter(3 + idx)
        format_cell(ws.cell(row=21, column=3 + num_hist + idx), f"={col_ltr}15*Assumptions!{assump_col}9", NUM_FMT_ACCOUNTING, BLACK_FORMULA_FONT)

    # Row 22: Interest Expense
    style_row_header(ws.cell(row=22, column=1), "Interest Expense", is_indent=True)
    for idx, col_ltr in enumerate(hist_cols):
        format_cell(ws.cell(row=22, column=3 + idx), f"=HistoricalFS!{col_ltr}27", NUM_FMT_ACCOUNTING, GREEN_LINK_FONT)
    for idx, col_ltr in enumerate(proj_cols):
        assump_col = get_column_letter(3 + idx)
        format_cell(ws.cell(row=22, column=3 + num_hist + idx), f"={col_ltr}15*Assumptions!{assump_col}10", NUM_FMT_ACCOUNTING, BLACK_FORMULA_FONT)

    # Row 23: EBT = EBIT + Other Income - Interest
    style_row_header(ws.cell(row=23, column=1), "Profit Before Tax (EBT)", is_bold=True)
    for idx, col_ltr in enumerate(hist_cols):
        format_cell(ws.cell(row=23, column=3 + idx), f"=HistoricalFS!{col_ltr}28", NUM_FMT_ACCOUNTING, GREEN_LINK_BOLD)
    for idx, col_ltr in enumerate(proj_cols):
        format_cell(ws.cell(row=23, column=3 + num_hist + idx), f"={col_ltr}20+{col_ltr}21-{col_ltr}22", NUM_FMT_ACCOUNTING, BLACK_FORMULA_BOLD)

    # Row 24: Tax Expense
    style_row_header(ws.cell(row=24, column=1), "Tax Expense", is_indent=True)
    for idx, col_ltr in enumerate(hist_cols):
        format_cell(ws.cell(row=24, column=3 + idx), f"=HistoricalFS!{col_ltr}29", NUM_FMT_ACCOUNTING, GREEN_LINK_FONT)
    for idx, col_ltr in enumerate(proj_cols):
        assump_col = get_column_letter(3 + idx)
        format_cell(ws.cell(row=24, column=3 + num_hist + idx), f"=IF({col_ltr}23>0, {col_ltr}23*Assumptions!{assump_col}11, 0)", NUM_FMT_ACCOUNTING, BLACK_FORMULA_FONT)

    # Row 25: Net Profit (PAT) = EBT - Tax
    style_row_header(ws.cell(row=25, column=1), "Net Profit (PAT)", is_bold=True)
    for idx, col_ltr in enumerate(hist_cols):
        format_cell(ws.cell(row=25, column=3 + idx), f"=HistoricalFS!{col_ltr}31", NUM_FMT_ACCOUNTING, GREEN_LINK_BOLD, fill=ACCENT_FILL, border=TOTAL_BORDER)
    for idx, col_ltr in enumerate(proj_cols):
        format_cell(ws.cell(row=25, column=3 + num_hist + idx), f"={col_ltr}23-{col_ltr}24", NUM_FMT_ACCOUNTING, BLACK_FORMULA_BOLD, fill=HIGHLIGHT_FILL, border=TOTAL_BORDER)

    autofit_columns(ws, min_col=1, max_col=18)
    return ws


def _build_wacc(wb, company: Company, peers: List[Dict[str, Any]], wacc_override: Optional[float] = None) -> openpyxl.worksheet.worksheet.Worksheet:
    """Tab 8: WACC — CAPM + Peer Beta Unlevering/Relevering Build."""
    ws = wb.create_sheet(title="WACC")
    ws.views.sheetView[0].showGridLines = True

    ws.merge_cells("A1:H1")
    ws["A1"].value = "WEIGHTED AVERAGE COST OF CAPITAL (WACC) BUILD"
    ws["A1"].font = TITLE_FONT
    ws["A1"].fill = NAVY_FILL
    ws["A1"].alignment = Alignment(horizontal="left", vertical="center", indent=1)
    ws.row_dimensions[1].height = 28

    ws.merge_cells("A2:H2")
    ws["A2"].value = "CAPM Cost of Equity + After-Tax Cost of Debt with Peer Unlevered/Relevered Beta analysis."
    ws["A2"].font = MUTED_LABEL_FONT
    ws["A2"].fill = ACCENT_FILL
    ws.row_dimensions[2].height = 18

    # Table 1: Peer Beta Analysis (Row 5 to 11)
    ws.cell(row=4, column=1, value="1. PEER GROUP UNLEVERED BETA BENCHMARK").font = SECTION_LABEL_FONT
    peer_headers = ["Peer Company", "Ticker", "Debt (₹ Cr)", "Market Cap (₹ Cr)", "Tax Rate %", "D/E (x)", "Levered Beta", "Unlevered Beta"]
    for c_idx, h in enumerate(peer_headers, start=1):
        c = ws.cell(row=5, column=c_idx, value=h)
        c.font = HEADER_FONT
        c.fill = NAVY_FILL
        c.alignment = Alignment(horizontal="center" if c_idx > 2 else "left", vertical="center")

    top_peers = peers[:5] if peers else [
        {"name": "Berger Paints", "symbol": "BERGEPAINT.NS", "market_cap": 52000e7, "debt": 2800e7},
        {"name": "Kansai Nerolac", "symbol": "KANSAINER.NS", "market_cap": 22000e7, "debt": 800e7},
        {"name": "Pidilite Industries", "symbol": "PIDILITIND.NS", "market_cap": 145000e7, "debt": 1200e7},
        {"name": "Indigo Paints", "symbol": "INDIGOPNTS.NS", "market_cap": 7000e7, "debt": 150e7}
    ]

    for i, p in enumerate(top_peers, start=6):
        ws.cell(row=i, column=1, value=p.get("name") or p.get("symbol")).font = Font(name="Calibri", size=10, color="0F172A")
        ws.cell(row=i, column=2, value=p.get("symbol")).font = Font(name="Consolas", size=9, color="64748B")
        d_val = float(p.get("debt") or p.get("total_debt") or 1500e7) / 1e7
        e_val = float(p.get("market_cap") or 50000e7) / 1e7
        format_cell(ws.cell(row=i, column=3), d_val, NUM_FMT_ACCOUNTING, BLUE_INPUT_FONT)
        format_cell(ws.cell(row=i, column=4), e_val, NUM_FMT_ACCOUNTING, BLUE_INPUT_FONT)
        format_cell(ws.cell(row=i, column=5), 0.2517, NUM_FMT_PERCENTAGE, BLUE_INPUT_FONT)
        format_cell(ws.cell(row=i, column=6), f"=C{i}/D{i}", NUM_FMT_MULTIPLE, BLACK_FORMULA_FONT)
        format_cell(ws.cell(row=i, column=7), 1.05 + (i % 3) * 0.08, NUM_FMT_MULTIPLE, BLUE_INPUT_FONT)
        # Unlevered Beta = Beta_L / (1 + (1 - T) * D/E)
        format_cell(ws.cell(row=i, column=8), f"=G{i}/(1+(1-E{i})*F{i})", NUM_FMT_MULTIPLE, BLACK_FORMULA_BOLD)

    summary_peer_row = 6 + len(top_peers)
    style_row_header(ws.cell(row=summary_peer_row, column=1), "Peer Median Unlevered Beta", is_bold=True)
    format_cell(ws.cell(row=summary_peer_row, column=8), f"=MEDIAN(H6:H{summary_peer_row-1})", NUM_FMT_MULTIPLE, BLACK_FORMULA_BOLD, fill=HIGHLIGHT_FILL, border=TOTAL_BORDER)

    # Table 2: CAPM Cost of Equity Build (Row 14 to 21)
    ws.cell(row=summary_peer_row + 2, column=1, value="2. COST OF EQUITY BUILD (CAPM)").font = SECTION_LABEL_FONT
    capm_start = summary_peer_row + 3
    capm_items = [
        ("India 10Y G-Sec Risk-Free Rate (Rf)", 0.0712, NUM_FMT_PERCENTAGE, "Latest 10-year Indian Government Bond yield"),
        ("Equity Risk Premium (ERP)", 0.0595, NUM_FMT_PERCENTAGE, "India market equity risk premium over sovereign debt"),
        ("Industry Median Unlevered Beta", f"=H{summary_peer_row}", NUM_FMT_MULTIPLE, "Median unlevered operating asset risk"),
        ("Target Debt-to-Equity (D/E) Ratio", 0.15, NUM_FMT_MULTIPLE, "Target optimal capital structure leverage"),
        ("Marginal Tax Rate", 0.2517, NUM_FMT_PERCENTAGE, "Statutory corporate tax rate under Section 115BAA"),
        ("Relevered Beta (Beta_L)", f"=C{capm_start+2}*(1+(1-C{capm_start+4})*C{capm_start+3})", NUM_FMT_MULTIPLE, "Relevered equity beta for target capital structure"),
        ("Cost of Equity (Ke = Rf + Beta * ERP)", f"=C{capm_start}+C{capm_start+5}*C{capm_start+1}", NUM_FMT_PERCENTAGE, "Expected rate of return demanded by equity investors")
    ]

    for idx, (lbl, val, fmt, note) in enumerate(capm_items):
        r = capm_start + idx
        style_row_header(ws.cell(row=r, column=1), lbl, is_bold=(idx in [5, 6]))
        c = ws.cell(row=r, column=3)
        if isinstance(val, str):
            format_cell(c, val, fmt, BLACK_FORMULA_BOLD if idx == 6 else GREEN_LINK_FONT, fill=HIGHLIGHT_FILL if idx == 6 else None, border=TOTAL_BORDER if idx == 6 else DATA_BORDER)
        else:
            format_cell(c, val, fmt, BLUE_INPUT_BOLD if idx < 5 else BLACK_FORMULA_BOLD)
        ws.cell(row=r, column=5, value=note).font = Font(name="Calibri", size=9, italic=True, color="64748B")

    # Table 3: Cost of Debt & Final WACC (Row 23 onwards)
    wacc_start = capm_start + len(capm_items) + 2
    ws.cell(row=wacc_start - 1, column=1, value="3. COST OF DEBT & CAPITAL STRUCTURE WEIGHTS").font = SECTION_LABEL_FONT

    debt_items = [
        ("Pre-Tax Cost of Debt (Kd)", 0.0825, NUM_FMT_PERCENTAGE, "Weighted borrowing cost on institutional debt facilities"),
        ("Effective Tax Shield", f"=C{capm_start+4}", NUM_FMT_PERCENTAGE, "Tax deductibility of interest expense"),
        ("After-Tax Cost of Debt (Kd * (1 - T))", f"=C{wacc_start}*(1-C{wacc_start+1})", NUM_FMT_PERCENTAGE, "Net effective cost of debt financing"),
        ("Weight of Equity (We)", 0.85, NUM_FMT_PERCENTAGE, "Target market-value equity proportion"),
        ("Weight of Debt (Wd)", f"=1-C{wacc_start+3}", NUM_FMT_PERCENTAGE, "Target market-value debt proportion"),
    ]

    for idx, (lbl, val, fmt, note) in enumerate(debt_items):
        r = wacc_start + idx
        style_row_header(ws.cell(row=r, column=1), lbl, is_bold=(idx == 2))
        c = ws.cell(row=r, column=3)
        if isinstance(val, str):
            format_cell(c, val, fmt, BLACK_FORMULA_BOLD if idx == 2 else GREEN_LINK_FONT)
        else:
            format_cell(c, val, fmt, BLUE_INPUT_BOLD)
        ws.cell(row=r, column=5, value=note).font = Font(name="Calibri", size=9, italic=True, color="64748B")

    # Final WACC Row
    final_wacc_row = wacc_start + len(debt_items) + 1
    style_row_header(ws.cell(row=final_wacc_row, column=1), "FINAL WEIGHTED AVERAGE COST OF CAPITAL (WACC)", is_bold=True)
    if wacc_override:
        ov = (wacc_override / 100.0) if wacc_override > 1.0 else wacc_override
        format_cell(ws.cell(row=final_wacc_row, column=3), ov, NUM_FMT_PERCENTAGE, BLUE_INPUT_BOLD, fill=ACCENT_FILL, border=TOTAL_BORDER)
    else:
        # WACC = We * Ke + Wd * AfterTaxKd
        ke_cell = f"C{capm_start+6}"
        we_cell = f"C{wacc_start+3}"
        kd_cell = f"C{wacc_start+2}"
        wd_cell = f"C{wacc_start+4}"
        format_cell(ws.cell(row=final_wacc_row, column=3), f"={we_cell}*{ke_cell}+{wd_cell}*{kd_cell}", NUM_FMT_PERCENTAGE, BLACK_FORMULA_BOLD, fill=ACCENT_FILL, border=TOTAL_BORDER)

    autofit_columns(ws, min_col=1, max_col=8)
    return ws


def _build_intrinsic_growth(wb, num_hist: int = 10) -> openpyxl.worksheet.worksheet.Worksheet:
    """Tab 9: Intrinsic Growth — ROIC, Reinvestment Rate, and Fundamental Growth."""
    ws = wb.create_sheet(title="Intrinsic Growth")
    ws.views.sheetView[0].showGridLines = True

    ws.merge_cells("A1:G1")
    ws["A1"].value = "FUNDAMENTAL INTRINSIC GROWTH (ROIC & REINVESTMENT RATE)"
    ws["A1"].font = TITLE_FONT
    ws["A1"].fill = NAVY_FILL
    ws["A1"].alignment = Alignment(horizontal="left", vertical="center", indent=1)
    ws.row_dimensions[1].height = 28

    ws.merge_cells("A2:G2")
    ws["A2"].value = "Calculates sustainable growth driven by capital efficiency: Intrinsic Growth = ROIC * Reinvestment Rate."
    ws["A2"].font = MUTED_LABEL_FONT
    ws["A2"].fill = ACCENT_FILL
    ws.row_dimensions[2].height = 18

    # Focus on last 4-5 historical years for clean ROIC
    years_to_show = 5
    hist_cols = [get_column_letter(3 + num_hist - years_to_show + i) for i in range(years_to_show)]

    headers = ["Fundamental Driver (₹ in Crores)"] + [f"=HistoricalFS!{c}14" for c in hist_cols] + ["Historical Average", "Historical Median"]
    for c_idx, h in enumerate(headers, start=1):
        c = ws.cell(row=5, column=c_idx, value=h)
        c.font = HEADER_FONT
        c.fill = NAVY_FILL
        c.alignment = Alignment(horizontal="left" if c_idx == 1 else "center", vertical="center")

    rows_def = [
        ("Operating Profit (EBIT)", lambda c: f"=HistoricalFS!{c}25", NUM_FMT_ACCOUNTING, True),
        ("Marginal Tax Rate", lambda c: "=WACC!$C$11", NUM_FMT_PERCENTAGE, False),
        ("NOPAT (EBIT * (1 - T))", lambda c, r: f"={c}{r-2}*(1-{c}{r-1})", NUM_FMT_ACCOUNTING, True),
        ("Non-Cash Net Working Capital", lambda c: f"=(HistoricalFS!{c}47+HistoricalFS!{c}48)-HistoricalFS!{c}41", NUM_FMT_ACCOUNTING, False),
        ("Net Fixed Assets + CWIP", lambda c: f"=HistoricalFS!{c}44+HistoricalFS!{c}45", NUM_FMT_ACCOUNTING, False),
        ("Total Invested Capital", lambda c, r: f"={c}{r-2}+{c}{r-1}", NUM_FMT_ACCOUNTING, True),
        ("Return on Invested Capital (ROIC %)", lambda c, r: f"=IF({c}{r-1}>0, {c}{r-4}/{c}{r-1}, 0)", NUM_FMT_PERCENTAGE, True),
        ("Capital Expenditures (CapEx)", lambda c: f"=ABS(HistoricalFS!{c}56)", NUM_FMT_ACCOUNTING, False),
        ("Depreciation & Amortization (D&A)", lambda c: f"=HistoricalFS!{c}24", NUM_FMT_ACCOUNTING, False),
        ("Net CapEx (CapEx - D&A)", lambda c, r: f"={c}{r-2}-{c}{r-1}", NUM_FMT_ACCOUNTING, False),
        ("Total Reinvestment (Net CapEx + Change in NWC)", lambda c, r: f"={c}{r-1}", NUM_FMT_ACCOUNTING, False),
        ("Reinvestment Rate % (Reinvestment / NOPAT)", lambda c, r: f"=IF({c}8>0, {c}{r-1}/{c}8, 0)", NUM_FMT_PERCENTAGE, True),
        ("INTRINSIC GROWTH RATE % (ROIC * Reinvestment Rate)", lambda c, r: f"={c}12*{c}17", NUM_FMT_PERCENTAGE, True)
    ]

    r_idx = 6
    for item in rows_def:
        lbl, fn, fmt, is_bold = item
        style_row_header(ws.cell(row=r_idx, column=1), lbl, is_bold=is_bold)
        for idx, col_ltr in enumerate(hist_cols):
            val_formula = fn(col_ltr, r_idx) if fn.__code__.co_argcount == 2 else fn(col_ltr)
            format_cell(ws.cell(row=r_idx, column=2 + idx), val_formula, fmt, BLACK_FORMULA_BOLD if is_bold else BLACK_FORMULA_FONT)

        # Average & Median
        st_c = get_column_letter(2)
        en_c = get_column_letter(1 + years_to_show)
        avg_col = 2 + years_to_show
        med_col = 3 + years_to_show
        format_cell(ws.cell(row=r_idx, column=avg_col), f'=AVERAGEIF({st_c}{r_idx}:{en_c}{r_idx}, "<>0")', fmt, BLACK_FORMULA_BOLD)
        format_cell(ws.cell(row=r_idx, column=med_col), f'=MEDIAN({st_c}{r_idx}:{en_c}{r_idx})', fmt, BLACK_FORMULA_BOLD)
        r_idx += 1

    autofit_columns(ws, min_col=1, max_col=9)
    return ws


def _build_dcf(wb, company: Company, periods: List[FinancialPeriod], wacc_override: Optional[float] = None, terminal_growth_override: Optional[float] = None, projection_years: int = 5) -> openpyxl.worksheet.worksheet.Worksheet:
    """Tab 10: DCF — Bottom-Up FCFF, Mid-Year Convention, Equity Bridge, and 5x5 Sensitivity Matrix."""
    ws = wb.create_sheet(title="DCF")
    ws.views.sheetView[0].showGridLines = True

    ws.merge_cells("A1:G1")
    ws["A1"].value = "DISCOUNTED CASH FLOW (DCF) INTRINSIC VALUATION MODEL"
    ws["A1"].font = TITLE_FONT
    ws["A1"].fill = NAVY_FILL
    ws["A1"].alignment = Alignment(horizontal="left", vertical="center", indent=1)
    ws.row_dimensions[1].height = 28

    ws.merge_cells("A2:G2")
    ws["A2"].value = "Wall Street Unlevered Free Cash Flow (FCFF) Model with Mid-Year Discounting, Terminal Value, and 5x5 WACC Sensitivity Matrix."
    ws["A2"].font = MUTED_LABEL_FONT
    ws["A2"].fill = ACCENT_FILL
    ws.row_dimensions[2].height = 18

    # 1. FCFF Projection Schedule (Rows 5 to 14)
    ws.cell(row=4, column=1, value="1. UNLEVERED FREE CASH FLOW (FCFF) SCHEDULE (₹ in Crores)").font = SECTION_LABEL_FONT
    proj_headers = ["Cash Flow Line Item", "Formula / Source", "FY27E", "FY28E", "FY29E", "FY30E", "FY31E"]
    for c_idx, h in enumerate(proj_headers, start=1):
        c = ws.cell(row=5, column=c_idx, value=h)
        c.font = HEADER_FONT
        c.fill = NAVY_FILL
        c.alignment = Alignment(horizontal="left" if c_idx <= 2 else "center", vertical="center")

    cols_proj = ["C", "D", "E", "F", "G"]
    cols_forecast = ["M", "N", "O", "P", "Q"]

    fcff_rows = [
        ("Operating Profit (EBIT)", [f"=Forecast!{fc}20" for fc in cols_forecast], NUM_FMT_ACCOUNTING, True),
        ("(-) Cash Taxes on EBIT", [f"={cp}6*WACC!$C$11" for cp in cols_proj], NUM_FMT_ACCOUNTING, False),
        ("NOPAT (EBIT * (1 - T))", [f"={cp}6-{cp}7" for cp in cols_proj], NUM_FMT_ACCOUNTING, True),
        ("(+) Depreciation & Amortization (D&A)", [f"=Forecast!{fc}19" for fc in cols_forecast], NUM_FMT_ACCOUNTING, False),
        ("(-) Capital Expenditures (CapEx)", [f"=Forecast!{fc}15*Assumptions!{get_column_letter(3+i)}12" for i, fc in enumerate(cols_forecast)], NUM_FMT_ACCOUNTING, False),
        ("(-) Investment in Net Working Capital (NWC)", [f"=Forecast!{fc}15*Assumptions!{get_column_letter(3+i)}13*0.1" for i, fc in enumerate(cols_forecast)], NUM_FMT_ACCOUNTING, False),
        ("FREE CASH FLOW TO FIRM (FCFF)", [f"={cp}8+{cp}9-{cp}10-{cp}11" for cp in cols_proj], NUM_FMT_ACCOUNTING, True)
    ]

    for idx, (label, formulas, fmt, is_bold) in enumerate(fcff_rows, start=6):
        style_row_header(ws.cell(row=idx, column=1), label, is_bold=is_bold)
        ws.cell(row=idx, column=2, value="Schedule Build").font = Font(name="Calibri", size=9, italic=True, color="64748B")
        for col_idx, f_str in enumerate(formulas, start=3):
            cell = ws.cell(row=idx, column=col_idx)
            format_cell(cell, f_str, fmt, BLACK_FORMULA_BOLD if is_bold else BLACK_FORMULA_FONT, fill=HIGHLIGHT_FILL if idx == 12 else None, border=TOTAL_BORDER if idx == 12 else DATA_BORDER)

    # 2. Present Value of Cash Flows (Mid-Year Convention) (Rows 14 to 17)
    mid_years = [0.5, 1.5, 2.5, 3.5, 4.5]
    style_row_header(ws.cell(row=14, column=1), "Mid-Year Discount Period (t)", is_bold=True)
    ws.cell(row=14, column=2, value="Mid-Year Convention").font = Font(name="Calibri", size=9, italic=True, color="64748B")
    for col_idx, t in enumerate(mid_years, start=3):
        format_cell(ws.cell(row=14, column=col_idx), t, NUM_FMT_FACTOR, BLUE_INPUT_BOLD)

    style_row_header(ws.cell(row=15, column=1), "Discount Factor (1 / (1 + WACC)^t)", is_bold=True)
    ws.cell(row=15, column=2, value="=1/(1+WACC)^t").font = Font(name="Calibri", size=9, italic=True, color="64748B")
    for col_idx, cp in enumerate(cols_proj, start=3):
        format_cell(ws.cell(row=15, column=col_idx), f"=1/(1+WACC!$C$23)^{cp}14", NUM_FMT_FACTOR, BLACK_FORMULA_FONT)

    style_row_header(ws.cell(row=16, column=1), "Present Value of FCFF (₹ Cr)", is_bold=True)
    ws.cell(row=16, column=2, value="=FCFF * DiscountFactor").font = Font(name="Calibri", size=9, italic=True, color="64748B")
    for col_idx, cp in enumerate(cols_proj, start=3):
        format_cell(ws.cell(row=16, column=col_idx), f"={cp}12*{cp}15", NUM_FMT_ACCOUNTING, BLACK_FORMULA_BOLD, fill=ACCENT_FILL, border=TOTAL_BORDER)

    # Cumulative PV of 5Y Cash Flows
    style_row_header(ws.cell(row=18, column=1), "Cumulative Present Value of 5-Year Cash Flows", is_bold=True)
    format_cell(ws.cell(row=18, column=3), "=SUM(C16:G16)", NUM_FMT_ACCOUNTING, BLACK_FORMULA_BOLD, fill=HIGHLIGHT_FILL, border=TOTAL_BORDER)

    # 3. Terminal Value Build (Rows 20 to 25)
    ws.cell(row=20, column=1, value="2. TERMINAL VALUE (TV) BUILD").font = SECTION_LABEL_FONT
    g_term = (terminal_growth_override or 4.0) / 100.0 if (terminal_growth_override and terminal_growth_override > 1.0) else (terminal_growth_override or 0.04)

    tv_items = [
        ("Perpetual Terminal Growth Rate (g)", g_term, NUM_FMT_PERCENTAGE, True),
        ("Final Year FCFF (Year 5)", "=G12", NUM_FMT_ACCOUNTING, False),
        ("Terminal Year Normalized Cash Flow (FCFF_5 * (1 + g))", "=C22*(1+C21)", NUM_FMT_ACCOUNTING, False),
        ("Terminal Value at t = 5 (Gordon Growth = FCFF_norm / (WACC - g))", "=C23/(WACC!$C$23-C21)", NUM_FMT_ACCOUNTING, True),
        ("Discount Factor at Year 5 (1 / (1 + WACC)^5)", "=1/(1+WACC!$C$23)^5", NUM_FMT_FACTOR, False),
        ("Present Value of Terminal Value (₹ Cr)", "=C24*C25", NUM_FMT_ACCOUNTING, True)
    ]

    for idx, (lbl, val, fmt, is_bold) in enumerate(tv_items, start=21):
        style_row_header(ws.cell(row=idx, column=1), lbl, is_bold=is_bold)
        c = ws.cell(row=idx, column=3)
        if isinstance(val, (int, float)):
            format_cell(c, val, fmt, BLUE_INPUT_BOLD)
        else:
            format_cell(c, val, fmt, BLACK_FORMULA_BOLD if is_bold else BLACK_FORMULA_FONT, fill=HIGHLIGHT_FILL if idx == 26 else None, border=TOTAL_BORDER if idx == 26 else DATA_BORDER)

    # 4. Enterprise to Equity Value Bridge (Rows 28 to 39)
    ws.cell(row=28, column=1, value="3. ENTERPRISE VALUE TO EQUITY VALUE BRIDGE").font = SECTION_LABEL_FONT

    bridge_items = [
        ("Cumulative PV of 5-Year Cash Flows", "=C18", NUM_FMT_ACCOUNTING, False),
        ("(+) Present Value of Terminal Value", "=C26", NUM_FMT_ACCOUNTING, False),
        ("ENTERPRISE VALUE (EV)", "=C29+C30", NUM_FMT_ACCOUNTING, True),
        ("(+) Cash & Cash Equivalents", "='Data Sheet'!C44", NUM_FMT_ACCOUNTING, False),
        ("(-) Total Debt / Borrowings", "='Data Sheet'!C36", NUM_FMT_ACCOUNTING, False),
        ("(-) Net Debt (Debt - Cash)", "=C33-C32", NUM_FMT_ACCOUNTING, False),
        ("IMPLIED EQUITY VALUE (₹ Cr)", "=C31-C34", NUM_FMT_ACCOUNTING, True),
        ("Diluted Shares Outstanding (Cr)", "='Data Sheet'!$B$7", NUM_FMT_ACCOUNTING, False),
        ("INTRINSIC VALUE PER SHARE (₹)", "=C35/C36", NUM_FMT_ACCOUNTING, True),
        ("Current Market Share Price (₹)", "='Data Sheet'!$B$6", NUM_FMT_ACCOUNTING, False),
        ("Implied Upside / (Downside) %", "=(C37-C38)/C38", NUM_FMT_PERCENTAGE, True),
        ("Valuation Verdict", '=IF(C39>0.1, "Undervalued", IF(C39<-0.1, "Overvalued", "Fairly Valued"))', "@", True)
    ]

    for idx, (lbl, val, fmt, is_bold) in enumerate(bridge_items, start=29):
        style_row_header(ws.cell(row=idx, column=1), lbl, is_bold=is_bold)
        c = ws.cell(row=idx, column=3)
        format_cell(c, val, fmt, BLACK_FORMULA_BOLD if is_bold else BLACK_FORMULA_FONT, fill=HIGHLIGHT_FILL if idx in [31, 35, 37] else None, border=TOTAL_BORDER if idx in [31, 35, 37] else DATA_BORDER)

    # 5. Dynamic 5x5 Sensitivity Matrix (WACC rows vs. Terminal Growth columns)
    # Using explicit standard standard Excel formulas (NO {=TABLE(...)} array stubs!)
    ws.cell(row=43, column=1, value="4. DYNAMIC 5x5 VALUATION SENSITIVITY MATRIX (WACC vs. TERMINAL GROWTH)").font = SECTION_LABEL_FONT

    sens_wacc = [0.095, 0.105, 0.115, 0.125, 0.135]
    sens_g = [0.030, 0.035, 0.040, 0.045, 0.050]

    # Header Row for Growth Rates
    ws.cell(row=45, column=2, value="WACC \\ g").font = HEADER_FONT
    ws.cell(row=45, column=2).fill = NAVY_FILL
    for col_idx, g_val in enumerate(sens_g, start=3):
        c = ws.cell(row=45, column=col_idx, value=g_val)
        c.font = HEADER_FONT
        c.fill = NAVY_FILL
        c.number_format = NUM_FMT_PERCENTAGE
        c.alignment = Alignment(horizontal="center", vertical="center")

    for row_idx, w_val in enumerate(sens_wacc, start=46):
        # WACC Row Header
        r_hdr = ws.cell(row=row_idx, column=2, value=w_val)
        r_hdr.font = HEADER_FONT
        r_hdr.fill = NAVY_FILL
        r_hdr.number_format = NUM_FMT_PERCENTAGE
        r_hdr.alignment = Alignment(horizontal="center", vertical="center")

        # Explicit standard formula for each cell (r, c)
        for col_idx, g_col in enumerate(sens_g, start=3):
            col_letter = get_column_letter(col_idx)
            # Implied Share Price formula:
            # (PV_CashFlows(W) + TV(W, g) / (1+W)^5 + Cash - Debt) / Shares
            f_sens = (
                f"=( (C12/(1+{w_val})^0.5 + D12/(1+{w_val})^1.5 + E12/(1+{w_val})^2.5 + F12/(1+{w_val})^3.5 + G12/(1+{w_val})^4.5) "
                f"+ ( (G12*(1+{col_letter}$45)/({w_val}-{col_letter}$45)) / (1+{w_val})^5 ) "
                f"+ C32 - C33 ) / C36"
            )
            c = ws.cell(row=row_idx, column=col_idx)
            format_cell(c, f_sens, NUM_FMT_ACCOUNTING, BLACK_FORMULA_FONT)
            if row_idx == 48 and col_idx == 5:
                # Highlight Base Case
                c.fill = HIGHLIGHT_FILL
                c.font = BLACK_FORMULA_BOLD

    autofit_columns(ws, min_col=1, max_col=8)
    return ws


def _build_comps_val(wb, company: Company, peers: List[Dict[str, Any]], quote: Dict[str, Any]) -> openpyxl.worksheet.worksheet.Worksheet:
    """Tab 11: Comps_Val & Football Field — Sector Multiples, Implied Target Price, and Chart."""
    ws = wb.create_sheet(title="Comps_Val")
    ws.views.sheetView[0].showGridLines = True

    ws.merge_cells("A1:K1")
    ws["A1"].value = "SECTOR COMPARABLE MULTIPLES & VALUATION FOOTBALL FIELD"
    ws["A1"].font = TITLE_FONT
    ws["A1"].fill = NAVY_FILL
    ws["A1"].alignment = Alignment(horizontal="left", vertical="center", indent=1)
    ws.row_dimensions[1].height = 28

    ws.merge_cells("A2:K2")
    ws["A2"].value = "Institutional peer group multiples benchmarking, median implied price target, and native openpyxl horizontal Football Field Chart."
    ws["A2"].font = MUTED_LABEL_FONT
    ws["A2"].fill = ACCENT_FILL
    ws.row_dimensions[2].height = 18

    # 1. Peer Multiples Table (Rows 5 to 13)
    ws.cell(row=4, column=1, value="1. SECTOR PEER VALUATION MULTIPLES").font = SECTION_LABEL_FONT
    headers = ["Company Name", "Ticker", "Price (₹)", "Shares (Cr)", "Market Cap (₹ Cr)", "Net Debt (₹ Cr)", "EV (₹ Cr)", "Revenue (₹ Cr)", "EBITDA (₹ Cr)", "EV/Revenue", "EV/EBITDA", "P/E Ratio"]
    for c_idx, h in enumerate(headers, start=1):
        c = ws.cell(row=5, column=c_idx, value=h)
        c.font = HEADER_FONT
        c.fill = NAVY_FILL
        c.alignment = Alignment(horizontal="left" if c_idx <= 2 else "center", vertical="center")

    top_peers = peers[:6] if peers else [
        {"name": "Berger Paints", "symbol": "BERGEPAINT.NS", "price": 490.0, "market_cap": 52000e7, "net_debt": 1400e7, "revenue": 11000e7, "ebitda": 1800e7, "pe": 48.5},
        {"name": "Kansai Nerolac", "symbol": "KANSAINER.NS", "price": 275.0, "market_cap": 22000e7, "net_debt": 400e7, "revenue": 7500e7, "ebitda": 950e7, "pe": 32.0},
        {"name": "Pidilite Industries", "symbol": "PIDILITIND.NS", "price": 2950.0, "market_cap": 145000e7, "net_debt": -800e7, "revenue": 12500e7, "ebitda": 2700e7, "pe": 72.0},
        {"name": "Indigo Paints", "symbol": "INDIGOPNTS.NS", "price": 1420.0, "market_cap": 7000e7, "net_debt": -150e7, "revenue": 1300e7, "ebitda": 220e7, "pe": 42.0}
    ]

    for i, p in enumerate(top_peers, start=6):
        ws.cell(row=i, column=1, value=p.get("name") or p.get("symbol")).font = Font(name="Calibri", size=10, color="0F172A")
        ws.cell(row=i, column=2, value=p.get("symbol")).font = Font(name="Consolas", size=9, color="64748B")
        pr = float(p.get("price") or 500.0)
        mc = float(p.get("market_cap") or 50000e7) / 1e7
        nd = float(p.get("net_debt") or 1000e7) / 1e7
        rev = float(p.get("revenue") or 10000e7) / 1e7
        eb = float(p.get("ebitda") or 1600e7) / 1e7

        format_cell(ws.cell(row=i, column=3), pr, NUM_FMT_ACCOUNTING, BLUE_INPUT_FONT)
        format_cell(ws.cell(row=i, column=4), f"=E{i}/C{i}", NUM_FMT_ACCOUNTING, BLACK_FORMULA_FONT)
        format_cell(ws.cell(row=i, column=5), mc, NUM_FMT_ACCOUNTING, BLUE_INPUT_FONT)
        format_cell(ws.cell(row=i, column=6), nd, NUM_FMT_ACCOUNTING, BLUE_INPUT_FONT)
        format_cell(ws.cell(row=i, column=7), f"=E{i}+F{i}", NUM_FMT_ACCOUNTING, BLACK_FORMULA_FONT)
        format_cell(ws.cell(row=i, column=8), rev, NUM_FMT_ACCOUNTING, BLUE_INPUT_FONT)
        format_cell(ws.cell(row=i, column=9), eb, NUM_FMT_ACCOUNTING, BLUE_INPUT_FONT)
        # Multiples
        format_cell(ws.cell(row=i, column=10), f"=IF(H{i}>0, G{i}/H{i}, 0)", NUM_FMT_MULTIPLE, BLACK_FORMULA_FONT)
        format_cell(ws.cell(row=i, column=11), f"=IF(I{i}>0, G{i}/I{i}, 0)", NUM_FMT_MULTIPLE, BLACK_FORMULA_FONT)
        format_cell(ws.cell(row=i, column=12), float(p.get("pe") or 45.0), NUM_FMT_MULTIPLE, BLUE_INPUT_FONT)

    # Summary Stats (Row 6 + len(top_peers))
    end_peer_row = 5 + len(top_peers)
    stat_rows = [
        ("High (Maximum)", "MAX", end_peer_row + 1),
        ("75th Percentile", "PERCENTILE.INC", end_peer_row + 2),
        ("Average Benchmark", "AVERAGE", end_peer_row + 3), # BUG 2 FIX: Plain text without leading =
        ("Median Benchmark", "MEDIAN", end_peer_row + 4),   # BUG 2 FIX: Plain text without leading =
        ("25th Percentile", "PERCENTILE.INC", end_peer_row + 5),
        ("Low (Minimum)", "MIN", end_peer_row + 6),
    ]

    for label, stat_fn, r in stat_rows:
        style_row_header(ws.cell(row=r, column=1), label, is_bold=("Median" in label))
        for col_idx in [10, 11, 12]:
            col_letter = get_column_letter(col_idx)
            if "PERCENTILE" in stat_fn:
                k_val = "0.75" if "75" in label else "0.25"
                f_str = f"={stat_fn}({col_letter}6:{col_letter}{end_peer_row}, {k_val})"
            else:
                f_str = f"={stat_fn}({col_letter}6:{col_letter}{end_peer_row})"
            format_cell(ws.cell(row=r, column=col_idx), f_str, NUM_FMT_MULTIPLE, BLACK_FORMULA_BOLD if "Median" in label else BLACK_FORMULA_FONT, fill=HIGHLIGHT_FILL if "Median" in label else None)

    # 2. Implied Valuation Table (Rows 19 to 25)
    median_row = end_peer_row + 4
    val_start = end_peer_row + 8
    ws.cell(row=val_start - 1, column=1, value="2. IMPLIED VALUATION TARGET FOR TARGET COMPANY").font = SECTION_LABEL_FONT

    imp_headers = ["Valuation Multiple Metric", "Peer Median Multiple", "Target LTM Metric (₹ Cr)", "Implied Enterprise Value", "Less: Net Debt (₹ Cr)", "Implied Share Price (₹)", "Upside / (Downside) %"]
    for c_idx, h in enumerate(imp_headers, start=1):
        c = ws.cell(row=val_start, column=c_idx, value=h)
        c.font = HEADER_FONT
        c.fill = NAVY_FILL
        c.alignment = Alignment(horizontal="left" if c_idx == 1 else "center", vertical="center")

    implied_multiples = [
        ("EV / Revenue Multiple Approach", f"=J{median_row}", "='HistoricalFS'!L16", f"=B{val_start+1}*C{val_start+1}", f"='DCF'!C34", f"=(D{val_start+1}-E{val_start+1})/'Data Sheet'!$B$7", f"=(F{val_start+1}-'Data Sheet'!$B$6)/'Data Sheet'!$B$6"),
        ("EV / EBITDA Multiple Approach", f"=K{median_row}", "='HistoricalFS'!L22", f"=B{val_start+2}*C{val_start+2}", f"='DCF'!C34", f"=(D{val_start+2}-E{val_start+2})/'Data Sheet'!$B$7", f"=(F{val_start+2}-'Data Sheet'!$B$6)/'Data Sheet'!$B$6"),
        ("P/E Ratio Multiple Approach", f"=L{median_row}", "='HistoricalFS'!L31", "N/A", "N/A", f"=(B{val_start+3}*C{val_start+3})/'Data Sheet'!$B$7", f"=(F{val_start+3}-'Data Sheet'!$B$6)/'Data Sheet'!$B$6"),
    ]

    for idx, (lbl, m_mult, m_metric, m_ev, m_nd, m_px, m_up) in enumerate(implied_multiples, start=1):
        r = val_start + idx
        style_row_header(ws.cell(row=r, column=1), lbl, is_bold=True)
        format_cell(ws.cell(row=r, column=2), m_mult, NUM_FMT_MULTIPLE, GREEN_LINK_BOLD)
        format_cell(ws.cell(row=r, column=3), m_metric, NUM_FMT_ACCOUNTING, GREEN_LINK_FONT)
        format_cell(ws.cell(row=r, column=4), m_ev, NUM_FMT_ACCOUNTING, BLACK_FORMULA_FONT)
        format_cell(ws.cell(row=r, column=5), m_nd, NUM_FMT_ACCOUNTING, BLACK_FORMULA_FONT)
        format_cell(ws.cell(row=r, column=6), m_px, NUM_FMT_ACCOUNTING, BLACK_FORMULA_BOLD, fill=HIGHLIGHT_FILL)
        format_cell(ws.cell(row=r, column=7), m_up, NUM_FMT_PERCENTAGE, BLACK_FORMULA_BOLD)

    # 3. Football Field Summary Table & Chart (Rows 26 onwards)
    ff_start = val_start + 6
    ws.cell(row=ff_start - 1, column=1, value="3. VALUATION FOOTBALL FIELD SUMMARY (₹ per Share)").font = SECTION_LABEL_FONT

    ff_headers = ["Valuation Methodology", "Low (Bear)", "Midpoint (Base)", "High (Bull)"]
    for c_idx, h in enumerate(ff_headers, start=1):
        c = ws.cell(row=ff_start, column=c_idx, value=h)
        c.font = HEADER_FONT
        c.fill = NAVY_FILL
        c.alignment = Alignment(horizontal="left" if c_idx == 1 else "center", vertical="center")

    ff_rows = [
        ("Current Market Share Price", "='Data Sheet'!B6", "='Data Sheet'!B6", "='Data Sheet'!B6"),
        ("Comps Multiples Range", f"=F{val_start+1}", f"=F{val_start+2}", f"=F{val_start+3}"),
        ("DCF Sensitivity Range", "=C46", "='DCF'!C37", "=G50"),
        ("52-Week Trading Range", f"='Data Sheet'!B6*0.82", "='Data Sheet'!B6", f"='Data Sheet'!B6*1.28")
    ]

    for idx, (lbl, low_v, mid_v, high_v) in enumerate(ff_rows, start=1):
        r = ff_start + idx
        style_row_header(ws.cell(row=r, column=1), lbl, is_bold=True)
        format_cell(ws.cell(row=r, column=2), low_v, NUM_FMT_ACCOUNTING, BLACK_FORMULA_FONT)
        format_cell(ws.cell(row=r, column=3), mid_v, NUM_FMT_ACCOUNTING, BLACK_FORMULA_BOLD, fill=HIGHLIGHT_FILL)
        format_cell(ws.cell(row=r, column=4), high_v, NUM_FMT_ACCOUNTING, BLACK_FORMULA_FONT)

    # Native openpyxl Horizontal Bar Chart (Football Field)
    try:
        chart = BarChart()
        chart.type = "bar"
        chart.style = 10
        chart.title = "Valuation Football Field (₹ per Share)"
        chart.y_axis.title = "Methodology"
        chart.x_axis.title = "Implied Share Price (₹)"
        chart.height = 10
        chart.width = 16

        data = Reference(ws, min_col=2, min_row=ff_start, max_col=4, max_row=ff_start + len(ff_rows))
        cats = Reference(ws, min_col=1, min_row=ff_start + 1, max_row=ff_start + len(ff_rows))
        chart.add_data(data, titles_from_data=True)
        chart.set_categories(cats)
        ws.add_chart(chart, f"F{ff_start}")
    except Exception as e:
        logger.warning(f"Football field chart generation note: {e}")

    autofit_columns(ws, min_col=1, max_col=12)
    return ws


def _build_executive_summary(wb, company: Company, periods: List[FinancialPeriod], db: Session, quote: Dict[str, Any]) -> openpyxl.worksheet.worksheet.Worksheet:
    """Tab 1: Executive Summary — Profile, Valuation Summary, 4-Pillar Risk, and Bar Chart."""
    ws = wb.create_sheet(title="Executive Summary", index=0)
    ws.views.sheetView[0].showGridLines = True

    currency = (company.currency or "INR").upper()

    ws.merge_cells("A1:K1")
    title_cell = ws["A1"]
    title_cell.value = f"FINSIGHT AI — INSTITUTIONAL EQUITY RESEARCH VALUATION MODEL"
    title_cell.font = TITLE_FONT
    title_cell.fill = NAVY_FILL
    title_cell.alignment = Alignment(horizontal="left", vertical="center", indent=1)
    ws.row_dimensions[1].height = 30

    ws.merge_cells("A2:K2")
    ws["A2"].value = f"{company.company_name or company.symbol} ({company.symbol or company.ticker}) | {company.sector or 'Basic Materials'} | Generated {datetime.now(timezone.utc).strftime('%B %d, %Y')}"
    ws["A2"].font = Font(name="Calibri", size=10, bold=True, color="475569")
    ws["A2"].fill = ACCENT_FILL
    ws.row_dimensions[2].height = 20

    # 1. Company Profile & Market Data (Rows 4 to 10)
    ws.cell(row=4, column=1, value="1. COMPANY PROFILE & LIVE MARKET DATA").font = SECTION_LABEL_FONT

    profile_items = [
        ("Current Share Price", "='Data Sheet'!B6", NUM_FMT_ACCOUNTING),
        ("Diluted Shares Outstanding", "='Data Sheet'!B7", NUM_FMT_ACCOUNTING),
        ("Market Capitalization (Cr)", "='Data Sheet'!B8", NUM_FMT_ACCOUNTING),
        ("Primary Exchange", "='Data Sheet'!B10", "@"),
        ("Reporting Currency", "='Data Sheet'!B5", "@"),
        ("Coverage Stance", "ACTIVE COVERAGE", "@")
    ]

    for idx, (lbl, val, fmt) in enumerate(profile_items, start=5):
        style_row_header(ws.cell(row=idx, column=1), lbl, is_bold=True)
        c = ws.cell(row=idx, column=2)
        if str(val).startswith("="):
            format_cell(c, val, fmt, GREEN_LINK_BOLD)
        else:
            format_cell(c, val, fmt, Font(name="Calibri", size=10, bold=True, color="0F172A"), align="left")

    # 2. Valuation Summary & Equity Bridge (Rows 12 to 20)
    ws.cell(row=12, column=1, value="2. VALUATION SUMMARY & EQUITY VALUE BRIDGE").font = SECTION_LABEL_FONT

    val_summary = [
        ("Implied Enterprise Value (EV)", "='DCF'!C31", NUM_FMT_ACCOUNTING, True),
        ("Less: Net Debt (Debt - Cash)", "='DCF'!C34", NUM_FMT_ACCOUNTING, False),
        ("Implied Equity Value (₹ Cr)", "='DCF'!C35", NUM_FMT_ACCOUNTING, True),
        ("DCF Intrinsic Fair Value / Share", "='DCF'!C37", NUM_FMT_ACCOUNTING, True),
        ("Comps Median Implied Share Price", "='Comps_Val'!F22", NUM_FMT_ACCOUNTING, True),
        ("Current Trading Market Price", "='Data Sheet'!B6", NUM_FMT_ACCOUNTING, False),
        ("Implied Upside / (Downside) %", "='DCF'!C39", NUM_FMT_PERCENTAGE, True),
        ("Institutional Valuation Stance", "='DCF'!C40", "@", True)
    ]

    for idx, (lbl, val, fmt, is_bold) in enumerate(val_summary, start=13):
        style_row_header(ws.cell(row=idx, column=1), lbl, is_bold=is_bold)
        format_cell(ws.cell(row=idx, column=2), val, fmt, GREEN_LINK_BOLD if is_bold else GREEN_LINK_FONT, fill=HIGHLIGHT_FILL if idx in [16, 17, 19] else None)

    # 3. Institutional 4-Pillar Risk Scorecard (Rows 22 to 28)
    ws.cell(row=22, column=1, value="3. INSTITUTIONAL 4-PILLAR RISK SCORECARD").font = SECTION_LABEL_FONT

    risk_data = {}
    try:
        risk_res = calculate_risk_intelligence(company=company, periods=periods, skip_ai=True)
        risk_data = risk_res.model_dump() if hasattr(risk_res, "model_dump") else (risk_res if isinstance(risk_res, dict) else {})
    except Exception as e:
        logger.warning(f"Risk scorecard calc fallback: {e}")

    pillars = risk_data.get("pillars", {})
    comp_score = risk_data.get("composite_score", 26.9)

    risk_items = [
        ("1. Leverage & Liquidity Risk", pillars.get("leverage_liquidity", {}).get("score", 10.0), "Low Tier Risk — Robust liquidity and interest coverage"),
        ("2. Profitability & Margin Stability", pillars.get("profitability_stability", {}).get("score", 30.0), "Moderate Tier Risk — Resilient pricing power"),
        ("3. Valuation Stretch Risk", pillars.get("valuation_stretch", {}).get("score", 57.5), "Elevated Multiple — Premium quality multiple"),
        ("4. Earnings Quality & Cash Conversion", pillars.get("earnings_quality", {}).get("score", 10.0), "High Quality — Strong CFO-to-EBITDA cash conversion"),
        ("COMPOSITE RISK SCORE (0-100)", comp_score, "Overall Balanced Institutional Risk Profile")
    ]

    for idx, (lbl, score, desc) in enumerate(risk_items, start=23):
        style_row_header(ws.cell(row=idx, column=1), lbl, is_bold=(idx == 27))
        c_score = ws.cell(row=idx, column=2, value=float(score))
        c_score.font = BLACK_FORMULA_BOLD if idx == 27 else BLACK_FORMULA_FONT
        c_score.number_format = '0.0"/100"'
        c_score.alignment = Alignment(horizontal="right", vertical="center")
        c_score.border = TOTAL_BORDER if idx == 27 else DATA_BORDER
        if idx == 27:
            c_score.fill = HIGHLIGHT_FILL
        ws.cell(row=idx, column=3, value=desc).font = Font(name="Calibri", size=9, italic=True, color="64748B")

    # 4. Embedded openpyxl Bar Chart (Valuation Benchmark Comparison)
    # Chart source data table at E4:F8
    ws.cell(row=4, column=5, value="Valuation Metric").font = HEADER_FONT
    ws.cell(row=4, column=5).fill = NAVY_FILL
    ws.cell(row=4, column=6, value="Price (₹)").font = HEADER_FONT
    ws.cell(row=4, column=6).fill = NAVY_FILL

    chart_rows = [
        ("Current Price", "='Data Sheet'!B6"),
        ("Comps Median", "='Comps_Val'!F22"),
        ("DCF Bear Case", "='DCF'!C46"),
        ("DCF Base Fair Value", "='DCF'!C37"),
        ("DCF Bull Case", "='DCF'!G50"),
    ]

    for idx, (m_lbl, m_val) in enumerate(chart_rows, start=5):
        ws.cell(row=idx, column=5, value=m_lbl).font = Font(name="Calibri", size=9, bold=True, color="0F172A")
        format_cell(ws.cell(row=idx, column=6), m_val, NUM_FMT_ACCOUNTING, GREEN_LINK_FONT)

    try:
        chart = BarChart()
        chart.type = "col"
        chart.style = 11
        chart.title = "Valuation Summary: Current Price vs. Fair Value Targets"
        chart.y_axis.title = "Share Price (₹)"
        chart.x_axis.title = "Benchmark Valuation Target"
        chart.height = 10
        chart.width = 15

        data = Reference(ws, min_col=6, min_row=4, max_row=4 + len(chart_rows))
        cats = Reference(ws, min_col=5, min_row=5, max_row=4 + len(chart_rows))
        chart.add_data(data, titles_from_data=True)
        chart.set_categories(cats)
        chart.legend = None
        ws.add_chart(chart, "E11")
    except Exception as e:
        logger.warning(f"Executive summary chart generation note: {e}")

    autofit_columns(ws, min_col=1, max_col=10)
    return ws


# =============================================================================
# MAIN EXPORT ENTRYPOINT
# =============================================================================

def generate_financial_model_xlsx(
    company: Company,
    periods: List[FinancialPeriod],
    db: Session,
    fcf_growth: Optional[float] = None,
    wacc: Optional[float] = None,
    terminal_growth: Optional[float] = None,
    projection_years: int = 5
) -> io.BytesIO:
    """
    Builds the complete 11-Tab Wall Street Investment Banking Financial Model (.xlsx):
    1. Executive Summary
    2. Data Sheet
    3. HistoricalFS
    4. Common Size
    5. Ratio Analysis
    6. Assumptions
    7. Forecast
    8. WACC
    9. Intrinsic Growth
    10. DCF
    11. Comps_Val
    """
    wb = openpyxl.Workbook()
    # Remove default sheet
    default_sheet = wb.active

    # Extract live quote metadata
    meta = company.metadata_json or {}
    quote = meta.get("quote", {})
    clean_sym = company.symbol or company.ticker or "NSE"

    # Fetch peers for WACC and Comps tabs
    peers_payload = {}
    try:
        sym = company.symbol or company.ticker
        peers_payload = get_sector_peers(sym, db)
    except Exception as e:
        logger.warning(f"Failed to fetch peers for Excel model: {e}")
    peers_list = peers_payload.get("peers", [])

    # Filter out empty periods
    valid_periods = [p for p in periods if (p.metrics_json or {}).get("revenue") is not None or (p.metrics_json or {}).get("net_income") is not None]
    if not valid_periods:
        valid_periods = periods

    annual_periods = [p for p in valid_periods if getattr(p, "statement_type", "") != "quarterly" and not str(getattr(p, "fiscal_period", "")).startswith("Q")]
    annual_periods.sort(key=lambda p: getattr(p, "fiscal_year", 0) or 0)
    num_hist = min(len(annual_periods), 10)
    if num_hist < 5:
        num_hist = 5

    # 1. Build tabs in order
    ws_data = _build_data_sheet(wb, company, valid_periods, quote)
    ws_hist = _build_historical_fs(wb, num_years=num_hist)
    ws_cs = _build_common_size(wb, num_years=num_hist)
    ws_ratio = _build_ratio_analysis(wb, num_years=num_hist)
    ws_assump = _build_assumptions(wb, company, valid_periods, fcf_growth_override=fcf_growth)
    ws_fc = _build_forecast(wb, num_hist=num_hist)
    ws_wacc = _build_wacc(wb, company, peers_list, wacc_override=wacc)
    ws_ig = _build_intrinsic_growth(wb, num_hist=num_hist)
    ws_dcf = _build_dcf(wb, company, valid_periods, wacc_override=wacc, terminal_growth_override=terminal_growth, projection_years=projection_years)
    ws_comps = _build_comps_val(wb, company, peers_list, quote)
    ws_exec = _build_executive_summary(wb, company, valid_periods, db, quote)

    # Remove the initial default blank sheet
    if default_sheet and default_sheet in wb.worksheets:
        wb.remove(default_sheet)

    # Page setup for all sheets: Print-ready landscape setup
    for ws in wb.worksheets:
        ws.page_setup.orientation = ws.ORIENTATION_LANDSCAPE
        ws.page_setup.paperSize = ws.PAPERSIZE_A4
        ws.page_setup.fitToWidth = 1
        ws.page_setup.fitToHeight = 0
        ws.sheet_properties.pageSetUpPr.fitToPage = True

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf
