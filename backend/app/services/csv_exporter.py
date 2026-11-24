"""
FinSight AI — Raw Financial Dataset CSV Export Engine
=====================================================
Generates an RFC-4180 compliant, multi-year and quarterly financial dataset
covering Income Statement, Balance Sheet, Cash Flow, and Institutional Ratios
with strict Excel formula-injection defense.
"""

import io
import csv
from typing import List, Any, Optional
from datetime import datetime, timezone
from app.models.company import Company
from app.models.dataset import FinancialPeriod


def _sanitize_csv_cell(val: Any) -> str:
    """Escapes against formula injection (=, +, -, @, \\t, \\r)."""
    if val is None:
        return ""
    s = str(val).strip()
    if s.startswith(("=", "+", "-", "@", "\t", "\r")):
        return "'" + s
    return s


def _to_cr(val: Optional[float], is_inr: bool) -> str:
    """Scales INR values to Crores (value / 1e7) with 2 decimals, or raw for non-INR."""
    if val is None:
        return ""
    try:
        f = float(val)
        if is_inr:
            cr = f / 1e7
            return f"{cr:.2f}"
        return f"{f:.2f}"
    except (ValueError, TypeError):
        return ""


def _to_ratio(val: Optional[float], decimals: int = 2) -> str:
    """Formats ratio or percentage float value."""
    if val is None:
        return ""
    try:
        f = float(val)
        return f"{f:.{decimals}f}"
    except (ValueError, TypeError):
        return ""


def generate_company_dataset_csv(company: Company, periods: List[FinancialPeriod]) -> io.BytesIO:
    """
    Constructs an RFC-4180 CSV containing all available Annual (FY2017-FY2026)
    and Quarterly periods for the company.
    """
    currency = (company.currency or "INR").upper()
    is_inr = (currency == "INR")
    unit_suffix = "_Cr" if is_inr else "_Millions"

    # Separate and sort periods: Annual ascending, then Quarterly ascending
    annual_periods = []
    quarterly_periods = []

    for p in periods:
        stmt_type = getattr(p, "statement_type", "") or ""
        period_lbl = getattr(p, "fiscal_period", "") or ""
        is_quarter = "quarterly" in stmt_type.lower() or period_lbl.upper().startswith("Q")
        if is_quarter:
            quarterly_periods.append(p)
        else:
            annual_periods.append(p)

    annual_periods.sort(key=lambda p: getattr(p, "fiscal_year", 0) or 0)
    quarterly_periods.sort(key=lambda p: (getattr(p, "fiscal_year", 0) or 0, getattr(p, "fiscal_period", "")))

    ordered_periods = annual_periods + quarterly_periods

    fieldnames = [
        "Period",
        "Statement_Type",
        "Fiscal_Year",
        "Currency",
        # Income Statement
        f"Revenue_Sales{unit_suffix}",
        f"Cost_of_Goods_Sold{unit_suffix}",
        f"Gross_Profit{unit_suffix}",
        f"Operating_Expenses{unit_suffix}",
        f"EBITDA{unit_suffix}",
        f"Depreciation_Amortization{unit_suffix}",
        f"Operating_Income_EBIT{unit_suffix}",
        f"Other_Income{unit_suffix}",
        f"Interest_Expense{unit_suffix}",
        f"Profit_Before_Tax_EBT{unit_suffix}",
        f"Tax_Expense{unit_suffix}",
        f"Net_Income_PAT{unit_suffix}",
        f"Shares_Outstanding{unit_suffix}",
        "Diluted_EPS",
        # Balance Sheet
        f"Total_Assets{unit_suffix}",
        f"Current_Assets{unit_suffix}",
        f"Cash_and_Equivalents{unit_suffix}",
        f"Investments{unit_suffix}",
        f"Trade_Receivables{unit_suffix}",
        f"Inventories{unit_suffix}",
        f"Net_Fixed_Assets{unit_suffix}",
        f"Total_Liabilities{unit_suffix}",
        f"Current_Liabilities{unit_suffix}",
        f"Trade_Payables{unit_suffix}",
        f"Total_Debt{unit_suffix}",
        f"Net_Debt{unit_suffix}",
        f"Total_Equity{unit_suffix}",
        f"Retained_Earnings{unit_suffix}",
        # Cash Flow
        f"Operating_Cash_Flow_CFO{unit_suffix}",
        f"Capital_Expenditures_CapEx{unit_suffix}",
        f"Free_Cash_Flow_FCF{unit_suffix}",
        f"Investing_Cash_Flow_CFI{unit_suffix}",
        f"Financing_Cash_Flow_CFF{unit_suffix}",
        # Key Ratios
        "Operating_Margin_OPM_Pct",
        "EBITDA_Margin_Pct",
        "Net_Profit_Margin_Pct",
        "ROE_Pct",
        "ROA_Pct",
        "ROCE_Pct",
        "Debt_to_Equity_Ratio",
        "Interest_Coverage_Ratio",
        "Current_Ratio",
        "Asset_Turnover_x"
    ]

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames, lineterminator="\r\n", quoting=csv.QUOTE_MINIMAL)
    writer.writeheader()

    for p in ordered_periods:
        m = p.metrics_json or {}
        yr = p.fiscal_year or m.get("fiscal_year")
        period_lbl = p.fiscal_period or m.get("fiscal_period") or (f"FY{yr}" if yr else "N/A")
        stmt_type = "Quarterly" if ("quarterly" in (p.statement_type or "").lower() or str(period_lbl).startswith("Q")) else "Annual"

        # Derived calculations for ratios if missing
        rev = m.get("revenue")
        ebit = m.get("operating_income") if m.get("operating_income") is not None else m.get("ebit")
        ebitda = m.get("ebitda")
        ni = m.get("net_income")
        tot_eq = m.get("total_equity")
        tot_assets = m.get("total_assets")
        tot_debt = m.get("total_debt")
        ca = m.get("current_assets")
        cl = m.get("current_liabilities")
        int_exp = m.get("interest_expense")

        opm = m.get("opm_pct")
        if opm is None and rev and ebit and rev > 0:
            opm = (ebit / rev) * 100.0

        ebitda_m = m.get("ebitda_margin_pct")
        if ebitda_m is None and rev and ebitda and rev > 0:
            ebitda_m = (ebitda / rev) * 100.0

        npm = m.get("net_margin_pct")
        if npm is None and rev and ni and rev > 0:
            npm = (ni / rev) * 100.0

        roe = m.get("roe_pct")
        if roe is None and ni and tot_eq and tot_eq > 0:
            roe = (ni / tot_eq) * 100.0

        roa = m.get("roa_pct")
        if roa is None and ni and tot_assets and tot_assets > 0:
            roa = (ni / tot_assets) * 100.0

        roce = m.get("roce_pct")
        if roce is None and ebit and tot_assets and cl and (tot_assets - cl) > 0:
            roce = (ebit / (tot_assets - cl)) * 100.0

        de = m.get("debt_to_equity")
        if de is None and tot_debt is not None and tot_eq and tot_eq > 0:
            de = tot_debt / tot_eq

        ic = m.get("interest_coverage")
        if ic is None and ebit is not None and int_exp and int_exp > 0:
            ic = ebit / int_exp

        cr = m.get("current_ratio")
        if cr is None and ca is not None and cl and cl > 0:
            cr = ca / cl

        at = m.get("asset_turnover")
        if at is None and rev and tot_assets and tot_assets > 0:
            at = rev / tot_assets

        row = {
            "Period": _sanitize_csv_cell(period_lbl),
            "Statement_Type": _sanitize_csv_cell(stmt_type),
            "Fiscal_Year": _sanitize_csv_cell(yr),
            "Currency": _sanitize_csv_cell(currency),
            # Income statement
            f"Revenue_Sales{unit_suffix}": _to_cr(rev, is_inr),
            f"Cost_of_Goods_Sold{unit_suffix}": _to_cr(m.get("cost_of_revenue"), is_inr),
            f"Gross_Profit{unit_suffix}": _to_cr(m.get("gross_profit"), is_inr),
            f"Operating_Expenses{unit_suffix}": _to_cr(m.get("operating_expenses"), is_inr),
            f"EBITDA{unit_suffix}": _to_cr(ebitda, is_inr),
            f"Depreciation_Amortization{unit_suffix}": _to_cr(m.get("depreciation_amortization"), is_inr),
            f"Operating_Income_EBIT{unit_suffix}": _to_cr(ebit, is_inr),
            f"Other_Income{unit_suffix}": _to_cr(m.get("other_income"), is_inr),
            f"Interest_Expense{unit_suffix}": _to_cr(int_exp, is_inr),
            f"Profit_Before_Tax_EBT{unit_suffix}": _to_cr(m.get("profit_before_tax"), is_inr),
            f"Tax_Expense{unit_suffix}": _to_cr(m.get("tax_expense"), is_inr),
            f"Net_Income_PAT{unit_suffix}": _to_cr(ni, is_inr),
            f"Shares_Outstanding{unit_suffix}": _to_cr(m.get("shares_outstanding"), is_inr),
            "Diluted_EPS": _to_ratio(m.get("eps"), 2),
            # Balance sheet
            f"Total_Assets{unit_suffix}": _to_cr(tot_assets, is_inr),
            f"Current_Assets{unit_suffix}": _to_cr(ca, is_inr),
            f"Cash_and_Equivalents{unit_suffix}": _to_cr(m.get("cash_and_equivalents"), is_inr),
            f"Investments{unit_suffix}": _to_cr(m.get("investments"), is_inr),
            f"Trade_Receivables{unit_suffix}": _to_cr(m.get("trade_receivables"), is_inr),
            f"Inventories{unit_suffix}": _to_cr(m.get("inventory"), is_inr),
            f"Net_Fixed_Assets{unit_suffix}": _to_cr(m.get("net_fixed_assets"), is_inr),
            f"Total_Liabilities{unit_suffix}": _to_cr(m.get("total_liabilities"), is_inr),
            f"Current_Liabilities{unit_suffix}": _to_cr(cl, is_inr),
            f"Trade_Payables{unit_suffix}": _to_cr(m.get("trade_payables"), is_inr),
            f"Total_Debt{unit_suffix}": _to_cr(tot_debt, is_inr),
            f"Net_Debt{unit_suffix}": _to_cr(m.get("net_debt"), is_inr),
            f"Total_Equity{unit_suffix}": _to_cr(tot_eq, is_inr),
            f"Retained_Earnings{unit_suffix}": _to_cr(m.get("retained_earnings"), is_inr),
            # Cash flow
            f"Operating_Cash_Flow_CFO{unit_suffix}": _to_cr(m.get("operating_cash_flow"), is_inr),
            f"Capital_Expenditures_CapEx{unit_suffix}": _to_cr(m.get("capital_expenditure"), is_inr),
            f"Free_Cash_Flow_FCF{unit_suffix}": _to_cr(m.get("free_cash_flow"), is_inr),
            f"Investing_Cash_Flow_CFI{unit_suffix}": _to_cr(m.get("investing_cash_flow"), is_inr),
            f"Financing_Cash_Flow_CFF{unit_suffix}": _to_cr(m.get("financing_cash_flow"), is_inr),
            # Ratios
            "Operating_Margin_OPM_Pct": _to_ratio(opm, 2),
            "EBITDA_Margin_Pct": _to_ratio(ebitda_m, 2),
            "Net_Profit_Margin_Pct": _to_ratio(npm, 2),
            "ROE_Pct": _to_ratio(roe, 2),
            "ROA_Pct": _to_ratio(roa, 2),
            "ROCE_Pct": _to_ratio(roce, 2),
            "Debt_to_Equity_Ratio": _to_ratio(de, 2),
            "Interest_Coverage_Ratio": _to_ratio(ic, 2),
            "Current_Ratio": _to_ratio(cr, 2),
            "Asset_Turnover_x": _to_ratio(at, 2)
        }
        writer.writerow(row)

    csv_bytes = io.BytesIO(output.getvalue().encode("utf-8"))
    csv_bytes.seek(0)
    return csv_bytes
