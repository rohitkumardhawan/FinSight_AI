"""
FinSight AI — Screener.in 10-Year Historical Data Backfill Engine
=================================================================
Fetches consolidated (fallback standalone) 10-year financial statement tables
(FY2017–FY2026) for Indian NSE/BSE equities from Screener.in public pages.
Converts ₹ Crores to raw INR (* 1e7) and returns normalized FinancialPeriodRecord objects.
Strict 10-second timeout with deterministic try/except error shielding.
"""

import re
import logging
from typing import List, Dict, Any, Optional
import httpx
from bs4 import BeautifulSoup
from app.schemas.dataset import FinancialPeriodRecord

logger = logging.getLogger("finsight.historical_backfill")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def _parse_val(raw_text: str) -> Optional[float]:
    """Parses a table cell string into a float, handling commas, %, and accounting parentheses."""
    if not raw_text:
        return None
    s = raw_text.strip().replace(",", "").replace("%", "")
    if not s or s in ("-", "—", "N/A", "nan"):
        return None
    # Wall Street / accounting parentheses e.g. (1,234)
    if s.startswith("(") and s.endswith(")"):
        s = f"-{s[1:-1]}"
    try:
        return float(s)
    except ValueError:
        return None


def fetch_screener_10y_periods(symbol: str) -> List[FinancialPeriodRecord]:
    """
    Scrapes 10-year consolidated (fallback standalone) P&L, Balance Sheet, and Cash Flow
    tables for an Indian equity from Screener.in.
    Returns normalized FinancialPeriodRecord instances for FY2017–FY2026.
    """
    clean_sym = symbol.replace(".NS", "").replace(".BO", "").strip().upper()
    if not clean_sym:
        return []

    urls = [
        f"https://www.screener.in/company/{clean_sym}/consolidated/",
        f"https://www.screener.in/company/{clean_sym}/",
    ]

    html_text = ""
    for url in urls:
        try:
            with httpx.Client(timeout=10.0, headers=HEADERS, follow_redirects=True) as client:
                resp = client.get(url)
                if resp.status_code == 200 and "profit-loss" in resp.text:
                    html_text = resp.text
                    break
        except Exception as ex:
            logger.debug(f"Screener fetch attempt for {url} encountered: {ex}")

    if not html_text:
        logger.warning(f"Could not retrieve Screener 10Y data for {clean_sym}")
        return []

    try:
        soup = BeautifulSoup(html_text, "html.parser")
        yearly_data: Dict[int, Dict[str, Any]] = {}

        # 1. Parse table sections
        section_configs = [
            ("profit-loss", "pl"),
            ("balance-sheet", "bs"),
            ("cash-flow", "cf"),
        ]

        for sec_id, _ in section_configs:
            sec = soup.find("section", id=sec_id)
            if not sec:
                continue
            table = sec.find("table")
            if not table:
                continue

            thead = table.find("thead")
            if not thead:
                continue

            # Parse header columns -> years
            header_th = [th.get_text(strip=True) for th in thead.find_all("th")]
            col_to_year: Dict[int, int] = {}
            for col_idx, h_text in enumerate(header_th):
                m = re.search(r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[ -]?(\d{2,4})", h_text, re.IGNORECASE)
                if m:
                    raw_yr = m.group(1)
                    yr = 2000 + int(raw_yr) if len(raw_yr) == 2 else int(raw_yr)
                    if 2015 <= yr <= 2027:
                        col_to_year[col_idx] = yr
                        if yr not in yearly_data:
                            yearly_data[yr] = {}

            tbody = table.find("tbody")
            if not tbody:
                continue

            for tr in tbody.find_all("tr"):
                cells = [c.get_text(strip=True) for c in tr.find_all(["td", "th"])]
                if not cells:
                    continue
                row_label = cells[0].replace("+", "").strip().lower()

                for col_idx, yr in col_to_year.items():
                    if col_idx < len(cells):
                        val = _parse_val(cells[col_idx])
                        if val is not None:
                            yearly_data[yr][row_label] = val

        if not yearly_data:
            return []

        # 2. Build canonical FinancialPeriodRecord instances
        records: List[FinancialPeriodRecord] = []
        for yr in sorted(yearly_data.keys()):
            if yr < 2017 or yr > 2026:
                continue

            d = yearly_data[yr]
            # Monetary fields in Screener are in ₹ Crores -> multiply by 1e7 for raw INR
            sales_cr = d.get("sales") or d.get("revenue")
            rev = round(sales_cr * 1e7, 2) if sales_cr is not None else None

            exp_cr = d.get("expenses")
            op_exp = round(exp_cr * 1e7, 2) if exp_cr is not None else None

            # Screener's "Operating Profit" is EBITDA (before D&A).
            # Subtracting Depreciation gives true EBIT / Operating Income.
            op_prof_cr = d.get("operating profit")
            depr_cr = d.get("depreciation")
            depr = round(depr_cr * 1e7, 2) if depr_cr is not None else None

            ebitda = round(op_prof_cr * 1e7, 2) if op_prof_cr is not None else None
            op_inc = round((op_prof_cr - (depr_cr or 0.0)) * 1e7, 2) if op_prof_cr is not None else None
            ebit = op_inc

            opm_pct = d.get("opm %")

            oth_inc_cr = d.get("other income")
            oth_inc = round(oth_inc_cr * 1e7, 2) if oth_inc_cr is not None else None

            interest_cr = d.get("interest")
            interest = round(interest_cr * 1e7, 2) if interest_cr is not None else None

            pbt_cr = d.get("profit before tax")
            pbt = round(pbt_cr * 1e7, 2) if pbt_cr is not None else None

            net_inc_cr = d.get("net profit")
            net_inc = round(net_inc_cr * 1e7, 2) if net_inc_cr is not None else None

            tax_exp = round(pbt - net_inc, 2) if (pbt is not None and net_inc is not None) else None

            # EPS is already in ₹ per share (do not multiply by 1e7)
            eps = d.get("eps in rs") or d.get("eps")

            # Balance sheet
            fixed_assets_cr = d.get("fixed assets")
            net_ppe = round(fixed_assets_cr * 1e7, 2) if fixed_assets_cr is not None else None

            investments_cr = d.get("investments")
            investments = round(investments_cr * 1e7, 2) if investments_cr is not None else None

            tot_assets_cr = d.get("total assets")
            tot_assets = round(tot_assets_cr * 1e7, 2) if tot_assets_cr is not None else None

            borrowings_cr = d.get("borrowings")
            tot_debt = round(borrowings_cr * 1e7, 2) if borrowings_cr is not None else None

            tot_liab_cr = d.get("total liabilities")
            tot_liab = round(tot_liab_cr * 1e7, 2) if tot_liab_cr is not None else None

            equity_cap_cr = d.get("equity capital")
            reserves_cr = d.get("reserves")
            tot_equity = None
            if equity_cap_cr is not None and reserves_cr is not None:
                tot_equity = round((equity_cap_cr + reserves_cr) * 1e7, 2)

            # Cash flow
            cfo_cr = d.get("cash from operating activity") or d.get("cfo")
            cfo = round(cfo_cr * 1e7, 2) if cfo_cr is not None else None

            cfi_cr = d.get("cash from investing activity")
            cfi = round(cfi_cr * 1e7, 2) if cfi_cr is not None else None

            cff_cr = d.get("cash from financing activity")
            cff = round(cff_cr * 1e7, 2) if cff_cr is not None else None

            net_cf_cr = d.get("net cash flow")
            net_change_cash = round(net_cf_cr * 1e7, 2) if net_cf_cr is not None else None

            # Free Cash Flow & CapEx exact reconciliation: OCF - CapEx == FCF
            fcf_cr = d.get("free cash flow")
            if fcf_cr is not None:
                fcf = round(fcf_cr * 1e7, 2)
                capex = round(cfo - fcf, 2) if cfo is not None else None
            else:
                capex = round(abs(cfi), 2) if cfi is not None else (round(depr * 0.85, 2) if depr is not None else None)
                fcf = round(cfo - capex, 2) if (cfo is not None and capex is not None) else None

            rec = FinancialPeriodRecord(
                fiscal_year=yr,
                fiscal_period=f"FY{yr}",
                statement_type="annual_combined",
                revenue=rev,
                operating_expenses=op_exp,
                operating_income=op_inc,
                opm_pct=opm_pct,
                ebit=ebit,
                ebitda=ebitda,
                other_income=oth_inc,
                interest_expense=interest,
                depreciation_amortization=depr,
                profit_before_tax=pbt,
                tax_expense=tax_exp,
                net_income=net_inc,
                eps=eps,
                total_assets=tot_assets,
                total_liabilities=tot_liab,
                total_debt=tot_debt,
                total_equity=tot_equity,
                net_ppe=net_ppe,
                investments=investments,
                operating_cash_flow=cfo,
                capital_expenditure=capex,
                investing_cash_flow=cfi,
                financing_cash_flow=cff,
                net_change_in_cash=net_change_cash,
                free_cash_flow=fcf,
                source=f"Screener.in 10Y ({clean_sym})"
            )
            records.append(rec)

        logger.info(f"Successfully scraped {len(records)} Screener 10Y periods for {clean_sym}")
        return records

    except Exception as parse_err:
        logger.warning(f"Error parsing Screener 10Y for {clean_sym}: {parse_err}")
        return []
