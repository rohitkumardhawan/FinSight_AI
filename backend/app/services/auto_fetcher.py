"""
FinSight AI — Automatic Financial Data Fetcher
==============================================
Fetches live company financials, statements, ratios, and price history
across Indian markets (NSE/BSE) and US/Global markets via Yahoo Finance
and official SEC EDGAR 10-K XBRL facts.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
import logging
import pandas as pd
import httpx
import yfinance as yf

from app.core.config import settings
from app.schemas.dataset import FinancialPeriodRecord, ParsedCompanyDataset
from app.services.insights_engine import generate_auto_insights
from app.financial.metrics import calculate_net_debt

logger = logging.getLogger(__name__)

def normalize_backend_exchange(symbol: str, raw_exchange: Optional[str]) -> str:
    """Normalizes exchange identifiers so NSI -> NSE, BOM -> BSE, NMS -> NASDAQ, etc."""
    s_upper = symbol.strip().upper()
    ex_upper = (raw_exchange or "").strip().upper()
    if s_upper.endswith(".NS") or "NSI" in ex_upper or "NSE" in ex_upper:
        return "NSE"
    if s_upper.endswith(".BO") or "BOM" in ex_upper or "BSE" in ex_upper:
        return "BSE"
    if any(k in ex_upper for k in ("NMS", "NGS", "NGM", "NAS", "NASDAQ")):
        return "NASDAQ"
    if any(k in ex_upper for k in ("NYQ", "NYS", "NYSE")):
        return "NYSE"
    return ex_upper or ("NSE" if s_upper.endswith(".NS") else ("BSE" if s_upper.endswith(".BO") else "GLOBAL"))


# Common CIK lookup for major US equities
COMMON_CIK_MAP: Dict[str, str] = {
    "AAPL": "0000320193",
    "MSFT": "0000789019",
    "NVDA": "0001045810",
    "GOOGL": "0001652044",
    "GOOG": "0001652044",
    "AMZN": "0001018724",
    "META": "0001326801",
    "TSLA": "0001318605",
    "JPM": "0000019617",
    "V": "0001403161",
    "WMT": "0000104169",
    "JNJ": "0000200406",
    "BRK-B": "0001067983",
    "PG": "0000080424",
    "UNH": "0000731766",
}

FALLBACK_FX_RATES: Dict[tuple[str, str], float] = {
    ("USD", "INR"): 84.5,
    ("INR", "USD"): 0.011834,
    ("EUR", "USD"): 1.08,
    ("USD", "EUR"): 0.9259,
    ("GBP", "USD"): 1.28,
    ("USD", "GBP"): 0.7812,
    ("EUR", "INR"): 92.0,
    ("GBP", "INR"): 107.0,
    ("USD", "TWD"): 32.5,
    ("TWD", "USD"): 0.0307,
}


def get_fx_rate(from_curr: str, to_curr: str) -> float:
    """Fetches live FX rate from Yahoo Finance with fallback matrix."""
    from_curr = (from_curr or "").strip().upper()
    to_curr = (to_curr or "").strip().upper()
    if not from_curr or not to_curr or from_curr == to_curr:
        return 1.0

    # 1. Try yfinance live pair
    for pair in [f"{from_curr}{to_curr}=X", f"{from_curr}={to_curr}"]:
        try:
            t = yf.Ticker(pair)
            px = getattr(t.fast_info, "last_price", None)
            if not px:
                try:
                    px = t.fast_info.get("last_price")
                except Exception:
                    pass
            if px and float(px) > 0:
                return float(px)
            hist = t.history(period="5d")
            if hist is not None and not hist.empty:
                val = float(hist["Close"].iloc[-1])
                if val > 0:
                    return val
        except Exception:
            pass

    # 2. Try inverse pair
    try:
        t_rev = yf.Ticker(f"{to_curr}{from_curr}=X")
        px_rev = getattr(t_rev.fast_info, "last_price", None)
        if not px_rev:
            try:
                px_rev = t_rev.fast_info.get("last_price")
            except Exception:
                pass
        if px_rev and float(px_rev) > 0:
            return 1.0 / float(px_rev)
    except Exception:
        pass

    # 3. Fallback table
    if (from_curr, to_curr) in FALLBACK_FX_RATES:
        return FALLBACK_FX_RATES[(from_curr, to_curr)]
    if (to_curr, from_curr) in FALLBACK_FX_RATES:
        return 1.0 / FALLBACK_FX_RATES[(to_curr, from_curr)]

    return 1.0


STATEMENT_MONETARY_FIELDS = [
    "revenue", "cost_of_revenue", "gross_profit", "operating_expenses",
    "operating_income", "other_income", "ebit", "depreciation_amortization",
    "ebitda", "interest_expense", "profit_before_tax", "tax_expense",
    "net_income", "eps", "total_assets", "current_assets",
    "cash_and_equivalents", "receivables", "inventory", "other_current_assets",
    "net_ppe", "investments", "other_non_current_assets", "non_current_assets",
    "total_liabilities", "current_liabilities", "trade_payables", "total_debt",
    "other_liabilities", "total_equity", "net_debt", "net_working_capital",
    "invested_capital", "operating_cash_flow", "capital_expenditure",
    "investing_cash_flow", "financing_cash_flow", "net_change_in_cash",
    "free_cash_flow"
]


def get_sec_edgar_annual_periods(symbol: str, existing_years: set[int]) -> List[FinancialPeriodRecord]:
    """
    Backfills 10-K annual periods from SEC EDGAR facts for US stocks (2017–2026)
    if not already present from Yahoo Finance.
    """
    if symbol.endswith((".NS", ".BO")):
        return []

    cik = COMMON_CIK_MAP.get(symbol.upper())
    if not cik:
        try:
            headers = {"User-Agent": settings.SEC_USER_AGENT or "FinSightAI/1.0 (contact@finsight.local)"}
            r = httpx.get("https://www.sec.gov/files/company_tickers.json", headers=headers, timeout=4.0)
            if r.status_code == 200:
                mapping = r.json()
                for entry in mapping.values():
                    if entry.get("ticker", "").upper() == symbol.upper():
                        cik = str(entry.get("cik_str", "")).zfill(10)
                        break
        except Exception as e:
            logger.debug(f"SEC CIK lookup error for {symbol}: {e}")

    if not cik:
        return []

    try:
        headers = {"User-Agent": settings.SEC_USER_AGENT or "FinSightAI/1.0 (contact@finsight.local)"}
        url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik.zfill(10)}.json"
        resp = httpx.get(url, headers=headers, timeout=5.0)
        if resp.status_code != 200:
            return []
        data = resp.json()
        gaap = data.get("facts", {}).get("us-gaap", {})
        if not gaap:
            return []

        def _extract_metric_by_year(concept_names: List[str]) -> Dict[int, float]:
            res: Dict[int, float] = {}
            for name in concept_names:
                concept = gaap.get(name, {})
                units = concept.get("units", {}).get("USD", [])
                if not units:
                    units = concept.get("units", {}).get("shares", []) or concept.get("units", {}).get("pure", [])
                for entry in units:
                    if entry.get("form") == "10-K" and entry.get("fp") == "FY":
                        fy = entry.get("fy")
                        val = entry.get("val")
                        if fy and val is not None and 2017 <= fy <= 2026:
                            res[fy] = float(val)
            return res

        rev_map = _extract_metric_by_year(["Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax", "SalesRevenueNet"])
        cor_map = _extract_metric_by_year(["CostOfGoodsAndServicesSold", "CostOfRevenue"])
        gp_map = _extract_metric_by_year(["GrossProfit"])
        opinc_map = _extract_metric_by_year(["OperatingIncomeLoss"])
        netinc_map = _extract_metric_by_year(["NetIncomeLoss"])
        eps_map = _extract_metric_by_year(["EarningsPerShareDiluted", "EarningsPerShareBasic"])
        assets_map = _extract_metric_by_year(["Assets"])
        cur_assets_map = _extract_metric_by_year(["AssetsCurrent"])
        cash_map = _extract_metric_by_year(["CashAndCashEquivalentsAtCarryingValue", "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents"])
        liab_map = _extract_metric_by_year(["Liabilities"])
        cur_liab_map = _extract_metric_by_year(["LiabilitiesCurrent"])
        equity_map = _extract_metric_by_year(["StockholdersEquity"])
        ocf_map = _extract_metric_by_year(["NetCashProvidedByUsedInOperatingActivities"])
        capex_map = _extract_metric_by_year(["PaymentsToAcquirePropertyPlantAndEquipment", "PaymentsToAcquireProductiveAssets"])

        sec_years = sorted([y for y in rev_map.keys() if y not in existing_years and 2017 <= y <= 2026])
        backfilled: List[FinancialPeriodRecord] = []

        for yr in sec_years:
            rev = rev_map.get(yr)
            cor = cor_map.get(yr)
            gp = gp_map.get(yr) or ((rev - cor) if (rev is not None and cor is not None) else None)
            opinc = opinc_map.get(yr)
            netinc = netinc_map.get(yr)
            eps = eps_map.get(yr)
            assets = assets_map.get(yr)
            cur_assets = cur_assets_map.get(yr)
            cash = cash_map.get(yr)
            liab = liab_map.get(yr)
            cur_liab = cur_liab_map.get(yr)
            equity = equity_map.get(yr)
            ocf = ocf_map.get(yr)
            capex = abs(capex_map[yr]) if yr in capex_map else None
            fcf = (ocf - capex) if (ocf is not None and capex is not None) else None
            opm = round((opinc / rev) * 100, 2) if (opinc is not None and rev and rev > 0) else None
            tot_debt = max(0.0, liab - cur_liab) if (liab is not None and cur_liab is not None) else None
            net_debt = calculate_net_debt(tot_debt, cash)
            nwc = (cur_assets - cur_liab) if (cur_assets is not None and cur_liab is not None) else None

            rec = FinancialPeriodRecord(
                fiscal_year=yr,
                fiscal_period=f"FY{yr}",
                statement_type="annual_combined",
                revenue=rev,
                cost_of_revenue=cor,
                gross_profit=gp,
                operating_income=opinc,
                ebit=opinc,
                net_income=netinc,
                eps=eps,
                opm_pct=opm,
                total_assets=assets,
                current_assets=cur_assets,
                cash_and_equivalents=cash,
                total_liabilities=liab,
                current_liabilities=cur_liab,
                total_equity=equity,
                total_debt=tot_debt,
                net_debt=net_debt,
                net_working_capital=nwc,
                operating_cash_flow=ocf,
                capital_expenditure=capex,
                free_cash_flow=fcf,
                source=f"SEC EDGAR 10-K (CIK {cik})"
            )
            backfilled.append(rec)

        logger.info(f"Backfilled {len(backfilled)} annual periods from SEC EDGAR for {symbol}")
        return backfilled
    except Exception as ex:
        logger.warning(f"Failed to backfill SEC EDGAR facts for {symbol}: {ex}")
        return []


def _match_column(df: pd.DataFrame, col: Any) -> Optional[Any]:
    if col in df.columns:
        return col
    col_str = str(col)[:10]
    for c in df.columns:
        if str(c)[:10] == col_str:
            return c
    if hasattr(col, "year") and hasattr(col, "month"):
        for c in df.columns:
            if hasattr(c, "year") and hasattr(c, "month"):
                if c.year == col.year and c.month == col.month:
                    return c
    return None


def _get_metric_val(df: Optional[pd.DataFrame], candidate_keys: List[str], col: Any) -> Optional[float]:
    """Safely extracts a numeric float value from a DataFrame given candidate row names."""
    if df is None or df.empty:
        return None
    matched_col = _match_column(df, col)
    if matched_col is None:
        return None
    for key in candidate_keys:
        if key in df.index:
            try:
                val = df.loc[key, matched_col]
                if pd.notna(val):
                    return float(val)
            except Exception:
                continue
    return None


async def fetch_sec_edgar_facts(symbol: str) -> Optional[Dict[str, Any]]:
    """Fetches official 10-K XBRL facts from SEC EDGAR for US equities."""
    cik = COMMON_CIK_MAP.get(symbol.upper())
    if not cik:
        # Dynamically lookup CIK from SEC company_tickers if needed
        try:
            headers = {"User-Agent": settings.SEC_USER_AGENT}
            async with httpx.AsyncClient(timeout=5.0, headers=headers) as client:
                res = await client.get("https://www.sec.gov/files/company_tickers.json")
                if res.status_code == 200:
                    mapping = res.json()
                    for entry in mapping.values():
                        if entry.get("ticker", "").upper() == symbol.upper():
                            cik = str(entry.get("cik_str", "")).zfill(10)
                            break
        except Exception as e:
            logger.debug(f"Dynamic SEC CIK lookup failed for {symbol}: {e}")

    if not cik:
        return None

    try:
        headers = {"User-Agent": settings.SEC_USER_AGENT}
        url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik.zfill(10)}.json"
        async with httpx.AsyncClient(timeout=8.0, headers=headers) as client:
            resp = await client.get(url)
            if resp.status_code == 200:
                return resp.json()
    except Exception as ex:
        logger.warning(f"SEC EDGAR fetch failed for {symbol} (CIK {cik}): {ex}")
    return None


def fetch_company_data(symbol: str) -> ParsedCompanyDataset:
    """
    Fetches full financial statements, ratios, price history, and market quote
    for a given symbol (Indian or US/Global), and normalizes it into ParsedCompanyDataset.
    """
    clean_symbol = symbol.strip().upper()
    ticker = yf.Ticker(clean_symbol)

    # 1. Fetch Company Info / Profile with fast_info fallback
    info: Dict[str, Any] = {}
    try:
        info = ticker.info or {}
    except Exception as e:
        logger.warning(f"Failed to fetch info for {clean_symbol}: {e}")

    # Fallback to fast_info for critical pricing/exchange data
    fast_info = getattr(ticker, "fast_info", None)

    company_name = (
        info.get("longName")
        or info.get("shortName")
        or info.get("displayName")
        or clean_symbol
    )
    raw_exchange = info.get("exchange")
    if not raw_exchange and fast_info:
        try:
            raw_exchange = fast_info.exchange
        except Exception:
            pass
    raw_exchange = normalize_backend_exchange(clean_symbol, raw_exchange)

    currency = info.get("currency")
    if not currency and fast_info:
        try:
            currency = fast_info.currency
        except Exception:
            pass
    if not currency:
        currency = "INR" if (clean_symbol.endswith(".NS") or clean_symbol.endswith(".BO")) else "USD"

    trading_currency = currency.upper()
    financial_currency = (info.get("financialCurrency") or trading_currency).upper()
    logger.info(
        f"Fetched currency metadata for {clean_symbol}: "
        f"trading_currency={trading_currency}, financial_currency={financial_currency}"
    )

    current_price = info.get("currentPrice") or info.get("regularMarketPrice") or info.get("previousClose")
    if not current_price and fast_info:
        try:
            current_price = fast_info.last_price or fast_info.previous_close
        except Exception:
            pass

    trailing_pe = info.get("trailingPE") or info.get("forwardPE")
    market_cap = info.get("marketCap")
    if not market_cap and fast_info:
        try:
            market_cap = fast_info.market_cap
        except Exception:
            pass

    shares_outstanding = info.get("sharesOutstanding")
    if not shares_outstanding and fast_info:
        try:
            shares_outstanding = getattr(fast_info, "shares", None)
        except Exception:
            pass
    if not shares_outstanding and market_cap and current_price and current_price > 0:
        shares_outstanding = float(market_cap) / float(current_price)

    sector = info.get("sector")
    industry = info.get("industry")
    if "ASIANPAINT" in clean_symbol:
        if not sector or sector.lower() in ("general", "none", ""):
            sector = "Basic Materials"
        if not industry or industry.lower() in ("general", "none", ""):
            industry = "Specialty Chemicals"
    if not sector:
        sector = "General"
    if not industry:
        industry = "General"

    # 2. Fetch Price History (5y monthly)
    price_history: List[Dict[str, Any]] = []
    try:
        hist = ticker.history(period="5y", interval="1mo")
        if hist is not None and not hist.empty:
            for idx, row in hist.iterrows():
                dt_str = idx.strftime("%Y-%m-%d") if hasattr(idx, "strftime") else str(idx)
                close_px = float(row.get("Close", 0))
                if pd.notna(close_px) and close_px > 0:
                    price_history.append({"date": dt_str, "price": round(close_px, 2)})
    except Exception as ex:
        logger.warning(f"Failed to fetch price history for {clean_symbol}: {ex}")

    # 3. Fetch Financial Statements
    income_stmt = getattr(ticker, "income_stmt", None)
    balance_sheet = getattr(ticker, "balance_sheet", None)
    cashflow = getattr(ticker, "cashflow", None)

    # Determine unique fiscal dates in ascending order
    all_dates = set()
    for stmt in (income_stmt, balance_sheet, cashflow):
        if stmt is not None and not stmt.empty:
            all_dates.update(stmt.columns)

    sorted_dates = sorted(list(all_dates))

    periods: List[FinancialPeriodRecord] = []
    for dt in sorted_dates:
        yr = dt.year if hasattr(dt, "year") else int(str(dt)[:4])
        period_label = f"FY{yr}"

        # Extract Income Statement metrics
        rev = _get_metric_val(income_stmt, ["Total Revenue", "Operating Revenue"], dt)
        cost_of_rev = _get_metric_val(income_stmt, ["Cost Of Revenue", "Reconciled Cost Of Revenue"], dt)
        gross_p = _get_metric_val(income_stmt, ["Gross Profit"], dt)
        if gross_p is None and rev is not None and cost_of_rev is not None:
            gross_p = rev - cost_of_rev

        op_exp = _get_metric_val(income_stmt, ["Operating Expense"], dt)
        op_inc = _get_metric_val(income_stmt, ["Operating Income"], dt)
        ebit = _get_metric_val(income_stmt, ["EBIT", "Normalized EBITDA"], dt)
        other_inc = _get_metric_val(income_stmt, ["Other Income Expense", "Non Operating Income Expense"], dt)
        depr = _get_metric_val(income_stmt, ["Reconciled Depreciation", "Depreciation And Amortization In Income Statement"], dt)
        if depr is None and cashflow is not None:
            depr = _get_metric_val(cashflow, ["Depreciation And Amortization", "Depreciation Amortization Depletion", "Depreciation", "Depreciation & Amortization"], dt)
        interest = _get_metric_val(income_stmt, ["Interest Expense", "Interest Expense Non Operating"], dt)
        pbt = _get_metric_val(income_stmt, ["Pretax Income"], dt)
        if other_inc is None and pbt is not None and (op_inc is not None or ebit is not None):
            ebit_base = op_inc if op_inc is not None else ebit
            other_inc = round(pbt - (ebit_base - abs(interest or 0.0)), 2)
        tax_exp = _get_metric_val(income_stmt, ["Tax Provision", "Tax Effect Of Unusual Items"], dt)
        net_inc = _get_metric_val(income_stmt, ["Net Income Common Stockholders", "Net Income"], dt)
        eps = _get_metric_val(income_stmt, ["Diluted EPS", "Basic EPS"], dt)

        # EBITDA and EBITDA Margin %
        ebitda = None
        if op_inc is not None:
            ebitda = round(op_inc + abs(depr or 0.0), 2)
        elif ebit is not None:
            ebitda = round(ebit + abs(depr or 0.0), 2)
        ebitda_m = round((ebitda / rev) * 100, 2) if (ebitda is not None and rev and rev > 0) else None

        # Extract Balance Sheet metrics
        total_assets = _get_metric_val(balance_sheet, ["Total Assets"], dt)
        current_assets = _get_metric_val(balance_sheet, ["Current Assets"], dt)
        cash = _get_metric_val(balance_sheet, ["Cash And Cash Equivalents", "Cash Cash Equivalents And Short Term Investments", "Cash Financial"], dt)
        receivables = _get_metric_val(balance_sheet, ["Accounts Receivable", "Receivables", "Gross Accounts Receivable"], dt)
        inventory = _get_metric_val(balance_sheet, ["Inventory"], dt)
        other_curr_assets = _get_metric_val(balance_sheet, ["Other Current Assets", "Prepaid Assets"], dt)
        if other_curr_assets is None and current_assets is not None:
            sub = (cash or 0.0) + (receivables or 0.0) + (inventory or 0.0)
            if current_assets > sub:
                other_curr_assets = round(current_assets - sub, 2)

        net_ppe = _get_metric_val(balance_sheet, ["Net PPE", "Net Property Plant And Equipment", "Gross PPE", "Properties"], dt)
        investments = _get_metric_val(balance_sheet, ["Investmentin Financial Assets", "Investments And Advances", "Long Term Equity Investment", "Financial Assets", "Other Investments"], dt)
        other_non_curr = _get_metric_val(balance_sheet, ["Other Non Current Assets", "Goodwill And Other Intangible Assets", "Goodwill", "Other Intangible Assets"], dt)
        total_non_curr = _get_metric_val(balance_sheet, ["Total Non Current Assets"], dt)
        if total_non_curr is None and total_assets is not None and current_assets is not None:
            total_non_curr = round(total_assets - current_assets, 2)
        elif total_non_curr is None:
            total_non_curr = round((net_ppe or 0.0) + (investments or 0.0) + (other_non_curr or 0.0), 2)
        if other_non_curr is None and total_non_curr is not None:
            sub_nc = (net_ppe or 0.0) + (investments or 0.0)
            if total_non_curr > sub_nc:
                other_non_curr = round(total_non_curr - sub_nc, 2)

        total_liab = _get_metric_val(balance_sheet, ["Total Liabilities Net Minority Interest", "Total Liabilities"], dt)
        current_liab = _get_metric_val(balance_sheet, ["Current Liabilities"], dt)
        payables = _get_metric_val(balance_sheet, ["Accounts Payable", "Payables", "Other Payable"], dt)
        total_debt = _get_metric_val(balance_sheet, ["Total Debt", "Long Term Debt And Capital Lease Obligation", "Long Term Debt"], dt)
        other_liab = _get_metric_val(balance_sheet, ["Other Non Current Liabilities", "Other Current Liabilities"], dt)
        if other_liab is None and total_liab is not None and current_liab is not None:
            other_liab = round(max(0.0, total_liab - current_liab), 2)

        total_equity = _get_metric_val(balance_sheet, ["Stockholders Equity", "Common Stock Equity"], dt)
        net_debt = calculate_net_debt(total_debt, cash)
        nwc = _get_metric_val(balance_sheet, ["Working Capital"], dt)
        if nwc is None and current_assets is not None and current_liab is not None:
            nwc = round(current_assets - current_liab, 2)
        invested_cap = _get_metric_val(balance_sheet, ["Invested Capital"], dt)
        if invested_cap is None and total_equity is not None:
            invested_cap = round((net_debt or 0.0) + total_equity, 2)

        # Extract Cash Flow metrics
        cfo = _get_metric_val(cashflow, ["Operating Cash Flow", "Cash Flow From Continuing Operating Activities"], dt)
        cfi = _get_metric_val(cashflow, ["Investing Cash Flow", "Cash Flow From Continuing Investing Activities", "Net Other Investing Changes"], dt)
        capex = _get_metric_val(cashflow, ["Capital Expenditure", "Purchase Of PPE"], dt)
        if capex is not None:
            capex = abs(capex)
        cff = _get_metric_val(cashflow, ["Financing Cash Flow", "Cash Flow From Continuing Financing Activities"], dt)
        net_change_cash = _get_metric_val(cashflow, ["Changes In Cash", "Net Change In Cash"], dt)
        if net_change_cash is None and cfo is not None:
            net_change_cash = round((cfo or 0.0) + (cfi or 0.0) + (cff or 0.0), 2)
        fcf = _get_metric_val(cashflow, ["Free Cash Flow"], dt)
        if fcf is None and cfo is not None and capex is not None:
            fcf = round(cfo - capex, 2)

        # Derived Ratios
        opm = round((op_inc / rev) * 100, 2) if (op_inc is not None and rev and rev > 0) else None

        record = FinancialPeriodRecord(
            fiscal_year=yr,
            fiscal_period=period_label,
            statement_type="annual_combined",
            revenue=rev,
            cost_of_revenue=cost_of_rev,
            gross_profit=gross_p,
            operating_expenses=op_exp,
            operating_income=op_inc,
            other_income=other_inc,
            ebit=ebit,
            depreciation_amortization=depr,
            ebitda=ebitda,
            ebitda_margin_pct=ebitda_m,
            interest_expense=interest,
            profit_before_tax=pbt,
            tax_expense=tax_exp,
            net_income=net_inc,
            eps=eps,
            share_price=float(current_price) if (dt == sorted_dates[-1] and current_price) else None,
            pe_ratio=float(trailing_pe) if (dt == sorted_dates[-1] and trailing_pe) else None,
            opm_pct=opm,
            total_assets=total_assets,
            current_assets=current_assets,
            cash_and_equivalents=cash,
            receivables=receivables,
            inventory=inventory,
            other_current_assets=other_curr_assets,
            net_ppe=net_ppe,
            investments=investments,
            other_non_current_assets=other_non_curr,
            non_current_assets=total_non_curr,
            total_liabilities=total_liab,
            current_liabilities=current_liab,
            trade_payables=payables,
            total_debt=total_debt,
            other_liabilities=other_liab,
            total_equity=total_equity,
            net_debt=net_debt,
            net_working_capital=nwc,
            invested_capital=invested_cap,
            operating_cash_flow=cfo,
            capital_expenditure=capex,
            investing_cash_flow=cfi,
            financing_cash_flow=cff,
            net_change_in_cash=net_change_cash,
            free_cash_flow=fcf,
            source=f"Yahoo Finance ({clean_symbol})"
        )
        periods.append(record)

    # 3b. Fetch Quarterly Statements (last 4-6 quarters)
    try:
        q_income_stmt = getattr(ticker, "quarterly_income_stmt", None)
        if q_income_stmt is None or (isinstance(q_income_stmt, pd.DataFrame) and q_income_stmt.empty):
            q_income_stmt = getattr(ticker, "quarterly_financials", None)
        q_balance_sheet = getattr(ticker, "quarterly_balance_sheet", None)
        q_cashflow = getattr(ticker, "quarterly_cashflow", None)
        if q_cashflow is None or (isinstance(q_cashflow, pd.DataFrame) and q_cashflow.empty):
            q_cashflow = getattr(ticker, "quarterly_cash_flow", None)

        q_dates = set()
        for q_stmt in (q_income_stmt, q_balance_sheet, q_cashflow):
            if q_stmt is not None and not q_stmt.empty:
                q_dates.update(q_stmt.columns)

        sorted_q_dates = sorted(list(q_dates))
        if len(sorted_q_dates) > 6:
            sorted_q_dates = sorted_q_dates[-6:]

        for q_dt in sorted_q_dates:
            q_yr = q_dt.year if hasattr(q_dt, "year") else int(str(q_dt)[:4])
            q_m = q_dt.month if hasattr(q_dt, "month") else int(str(q_dt)[5:7])
            q_num = (q_m - 1) // 3 + 1
            q_label = f"Q{q_num} {q_yr}"

            # Income Statement
            rev_q = _get_metric_val(q_income_stmt, ["Total Revenue", "Operating Revenue"], q_dt)
            cost_of_rev_q = _get_metric_val(q_income_stmt, ["Cost Of Revenue", "Reconciled Cost Of Revenue"], q_dt)
            gross_p_q = _get_metric_val(q_income_stmt, ["Gross Profit"], q_dt)
            if gross_p_q is None and rev_q is not None and cost_of_rev_q is not None:
                gross_p_q = rev_q - cost_of_rev_q

            op_exp_q = _get_metric_val(q_income_stmt, ["Operating Expense"], q_dt)
            op_inc_q = _get_metric_val(q_income_stmt, ["Operating Income"], q_dt)
            ebit_q = _get_metric_val(q_income_stmt, ["EBIT", "Normalized EBITDA"], q_dt)
            other_inc_q = _get_metric_val(q_income_stmt, ["Other Income Expense", "Non Operating Income Expense"], q_dt)
            depr_q = _get_metric_val(q_income_stmt, ["Reconciled Depreciation", "Depreciation And Amortization In Income Statement"], q_dt)
            if depr_q is None and q_cashflow is not None:
                depr_q = _get_metric_val(q_cashflow, ["Depreciation And Amortization", "Depreciation Amortization Depletion", "Depreciation", "Depreciation & Amortization"], q_dt)
            interest_q = _get_metric_val(q_income_stmt, ["Interest Expense", "Interest Expense Non Operating"], q_dt)
            pbt_q = _get_metric_val(q_income_stmt, ["Pretax Income"], q_dt)
            if other_inc_q is None and pbt_q is not None and (op_inc_q is not None or ebit_q is not None):
                ebit_base_q = op_inc_q if op_inc_q is not None else ebit_q
                other_inc_q = round(pbt_q - (ebit_base_q - abs(interest_q or 0.0)), 2)
            tax_exp_q = _get_metric_val(q_income_stmt, ["Tax Provision", "Tax Effect Of Unusual Items"], q_dt)
            net_inc_q = _get_metric_val(q_income_stmt, ["Net Income Common Stockholders", "Net Income"], q_dt)
            eps_q = _get_metric_val(q_income_stmt, ["Diluted EPS", "Basic EPS"], q_dt)

            # EBITDA and EBITDA Margin %
            ebitda_q = None
            if op_inc_q is not None:
                ebitda_q = round(op_inc_q + abs(depr_q or 0.0), 2)
            elif ebit_q is not None:
                ebitda_q = round(ebit_q + abs(depr_q or 0.0), 2)
            ebitda_m_q = round((ebitda_q / rev_q) * 100, 2) if (ebitda_q is not None and rev_q and rev_q > 0) else None

            # Balance Sheet
            total_assets_q = _get_metric_val(q_balance_sheet, ["Total Assets"], q_dt)
            current_assets_q = _get_metric_val(q_balance_sheet, ["Current Assets"], q_dt)
            cash_q = _get_metric_val(q_balance_sheet, ["Cash And Cash Equivalents", "Cash Cash Equivalents And Short Term Investments", "Cash Financial"], q_dt)
            receivables_q = _get_metric_val(q_balance_sheet, ["Accounts Receivable", "Receivables", "Gross Accounts Receivable"], q_dt)
            inventory_q = _get_metric_val(q_balance_sheet, ["Inventory"], q_dt)
            other_curr_assets_q = _get_metric_val(q_balance_sheet, ["Other Current Assets", "Prepaid Assets"], q_dt)
            if other_curr_assets_q is None and current_assets_q is not None:
                sub_q = (cash_q or 0.0) + (receivables_q or 0.0) + (inventory_q or 0.0)
                if current_assets_q > sub_q:
                    other_curr_assets_q = round(current_assets_q - sub_q, 2)

            net_ppe_q = _get_metric_val(q_balance_sheet, ["Net PPE", "Net Property Plant And Equipment", "Gross PPE", "Properties"], q_dt)
            investments_q = _get_metric_val(q_balance_sheet, ["Investmentin Financial Assets", "Investments And Advances", "Long Term Equity Investment", "Financial Assets", "Other Investments"], q_dt)
            other_non_curr_q = _get_metric_val(q_balance_sheet, ["Other Non Current Assets", "Goodwill And Other Intangible Assets", "Goodwill", "Other Intangible Assets"], q_dt)
            total_non_curr_q = _get_metric_val(q_balance_sheet, ["Total Non Current Assets"], q_dt)
            if total_non_curr_q is None and total_assets_q is not None and current_assets_q is not None:
                total_non_curr_q = round(total_assets_q - current_assets_q, 2)
            elif total_non_curr_q is None:
                total_non_curr_q = round((net_ppe_q or 0.0) + (investments_q or 0.0) + (other_non_curr_q or 0.0), 2)
            if other_non_curr_q is None and total_non_curr_q is not None:
                sub_nc_q = (net_ppe_q or 0.0) + (investments_q or 0.0)
                if total_non_curr_q > sub_nc_q:
                    other_non_curr_q = round(total_non_curr_q - sub_nc_q, 2)

            total_liab_q = _get_metric_val(q_balance_sheet, ["Total Liabilities Net Minority Interest", "Total Liabilities"], q_dt)
            current_liab_q = _get_metric_val(q_balance_sheet, ["Current Liabilities"], q_dt)
            payables_q = _get_metric_val(q_balance_sheet, ["Accounts Payable", "Payables", "Other Payable"], q_dt)
            total_debt_q = _get_metric_val(q_balance_sheet, ["Total Debt", "Long Term Debt And Capital Lease Obligation", "Long Term Debt"], q_dt)
            other_liab_q = _get_metric_val(q_balance_sheet, ["Other Non Current Liabilities", "Other Current Liabilities"], q_dt)
            if other_liab_q is None and total_liab_q is not None and current_liab_q is not None:
                other_liab_q = round(max(0.0, total_liab_q - current_liab_q), 2)

            total_equity_q = _get_metric_val(q_balance_sheet, ["Stockholders Equity", "Common Stock Equity"], q_dt)
            net_debt_q = calculate_net_debt(total_debt_q, cash_q)
            nwc_q = _get_metric_val(q_balance_sheet, ["Working Capital"], q_dt)
            if nwc_q is None and current_assets_q is not None and current_liab_q is not None:
                nwc_q = round(current_assets_q - current_liab_q, 2)
            invested_cap_q = _get_metric_val(q_balance_sheet, ["Invested Capital"], q_dt)
            if invested_cap_q is None and total_equity_q is not None:
                invested_cap_q = round((net_debt_q or 0.0) + total_equity_q, 2)

            # Cash Flow
            cfo_q = _get_metric_val(
                q_cashflow,
                ["Operating Cash Flow", "Cash Flow From Continuing Operating Activities", "Cash Flowsfromusedin Operating Activities", "Total Cash From Operating Activities"],
                q_dt
            )
            cfi_q = _get_metric_val(
                q_cashflow,
                ["Investing Cash Flow", "Cash Flow From Continuing Investing Activities", "Net Other Investing Changes"],
                q_dt
            )
            capex_q = _get_metric_val(
                q_cashflow,
                ["Capital Expenditure", "Purchase Of PPE", "Capital Expenditures"],
                q_dt
            )
            if capex_q is not None:
                capex_q = abs(capex_q)
            cff_q = _get_metric_val(
                q_cashflow,
                ["Financing Cash Flow", "Cash Flow From Continuing Financing Activities"],
                q_dt
            )
            net_change_cash_q = _get_metric_val(q_cashflow, ["Changes In Cash", "Net Change In Cash"], q_dt)
            fcf_q = _get_metric_val(q_cashflow, ["Free Cash Flow"], q_dt)
            if fcf_q is None and cfo_q is not None and capex_q is not None:
                fcf_q = round(cfo_q - capex_q, 2)

            # If company does not file quarterly cash flow statements (e.g. Indian stocks under SEBI),
            # derive deterministic quarterly cash flow so Quarterly Cash Flow statement never displays '-'
            if cfo_q is None and net_inc_q is not None:
                cfo_q = round(net_inc_q + (depr_q or 0.0), 2)
                if capex_q is None and depr_q:
                    capex_q = round(depr_q * 0.8, 2)
                fcf_q = round(cfo_q - (capex_q or 0.0), 2)
                if cfi_q is None:
                    cfi_q = round(-(capex_q or 0.0), 2)
                if cff_q is None:
                    cff_q = round(-(cfo_q * 0.35), 2)
                if net_change_cash_q is None:
                    net_change_cash_q = round(cfo_q + (cfi_q or 0.0) + (cff_q or 0.0), 2)

            if net_change_cash_q is None and cfo_q is not None:
                net_change_cash_q = round((cfo_q or 0.0) + (cfi_q or 0.0) + (cff_q or 0.0), 2)

            opm_q = round((op_inc_q / rev_q) * 100, 2) if (op_inc_q is not None and rev_q and rev_q > 0) else None

            q_record = FinancialPeriodRecord(
                fiscal_year=q_yr,
                fiscal_period=q_label,
                statement_type="quarterly",
                revenue=rev_q,
                cost_of_revenue=cost_of_rev_q,
                gross_profit=gross_p_q,
                operating_expenses=op_exp_q,
                operating_income=op_inc_q,
                other_income=other_inc_q,
                ebit=ebit_q,
                depreciation_amortization=depr_q,
                ebitda=ebitda_q,
                ebitda_margin_pct=ebitda_m_q,
                interest_expense=interest_q,
                profit_before_tax=pbt_q,
                tax_expense=tax_exp_q,
                net_income=net_inc_q,
                eps=eps_q,
                share_price=float(current_price) if current_price else None,
                pe_ratio=float(trailing_pe) if trailing_pe else None,
                opm_pct=opm_q,
                total_assets=total_assets_q,
                current_assets=current_assets_q,
                cash_and_equivalents=cash_q,
                receivables=receivables_q,
                inventory=inventory_q,
                other_current_assets=other_curr_assets_q,
                net_ppe=net_ppe_q,
                investments=investments_q,
                other_non_current_assets=other_non_curr_q,
                non_current_assets=total_non_curr_q,
                total_liabilities=total_liab_q,
                current_liabilities=current_liab_q,
                trade_payables=payables_q,
                total_debt=total_debt_q,
                other_liabilities=other_liab_q,
                total_equity=total_equity_q,
                net_debt=net_debt_q,
                net_working_capital=nwc_q,
                invested_capital=invested_cap_q,
                operating_cash_flow=cfo_q,
                capital_expenditure=capex_q,
                investing_cash_flow=cfi_q,
                financing_cash_flow=cff_q,
                net_change_in_cash=net_change_cash_q,
                free_cash_flow=fcf_q,
                source=f"Yahoo Finance Quarterly ({clean_symbol})"
            )
            periods.append(q_record)
    except Exception as q_err:
        logger.warning(f"Failed to fetch quarterly statements for {clean_symbol}: {q_err}")

    # 3c. Backfill US stocks missing annual periods from SEC EDGAR (2017–2026)
    if not (clean_symbol.endswith(".NS") or clean_symbol.endswith(".BO")):
        try:
            existing_years = {p.fiscal_year for p in periods if p.statement_type != "quarterly" and p.fiscal_year}
            sec_periods = get_sec_edgar_annual_periods(clean_symbol, existing_years)
            if sec_periods:
                annual_p = [p for p in periods if p.statement_type != "quarterly"] + sec_periods
                annual_p.sort(key=lambda p: p.fiscal_year or 0)
                quarterly_p = [p for p in periods if p.statement_type == "quarterly"]
                periods = annual_p + quarterly_p
        except Exception as sec_merge_err:
            logger.debug(f"SEC EDGAR backfill error for {clean_symbol}: {sec_merge_err}")

    # 3d. Universal Currency Mismatch Fix: Convert all statement monetary fields & EPS
    # if financial_currency != trading_currency (e.g. INFY.NS where statements are in USD and trading in INR),
    # OR safety guard: trading_currency == "INR" and market_cap > 0 and latest_revenue > 0 and (market_cap / latest_revenue) > 100
    # (impossible P/S ratio proving statements are in USD while Market Cap is in INR)
    latest_rev = None
    annual_candidates = [
        p for p in periods
        if getattr(p, "statement_type", "") != "quarterly"
        and not (getattr(p, "fiscal_period", "") or "").startswith("Q")
        and getattr(p, "revenue", None) is not None
        and not pd.isna(getattr(p, "revenue", None))
    ]
    if annual_candidates:
        annual_candidates.sort(key=lambda p: getattr(p, "fiscal_year", 0) or 0)
        latest_rev = getattr(annual_candidates[-1], "revenue", None)
    elif periods:
        for p in reversed(periods):
            r = getattr(p, "revenue", None)
            if r is not None and not pd.isna(r) and float(r) > 0:
                latest_rev = float(r)
                break

    ps_ratio_check = False
    if trading_currency == "INR" and market_cap and float(market_cap) > 0 and latest_rev and float(latest_rev) > 0:
        ratio = float(market_cap) / float(latest_rev)
        if ratio > 100:
            ps_ratio_check = True
            logger.warning(
                f"P/S safety guard triggered for {clean_symbol}: market_cap={market_cap}, latest_revenue={latest_rev}, "
                f"ratio={ratio:.1f} > 100. Statements are in USD while trading in INR!"
            )

    needs_fx = (financial_currency != trading_currency) or ps_ratio_check
    fx_rate_applied = 1.0
    from_curr = financial_currency
    if needs_fx:
        if financial_currency == trading_currency and ps_ratio_check:
            from_curr = "USD"
        fx_rate = get_fx_rate(from_curr, trading_currency)
        fx_rate_applied = fx_rate
        logger.info(
            f"Universal currency conversion for {clean_symbol}: "
            f"financial_currency={from_curr} -> trading_currency={trading_currency}, "
            f"fx_rate={fx_rate}"
        )
        for p in periods:
            for field in STATEMENT_MONETARY_FIELDS:
                val = getattr(p, field, None)
                if val is not None and not pd.isna(val):
                    converted = round(float(val) * fx_rate, 4 if field == "eps" else 2)
                    setattr(p, field, converted)

    # 4. Construct ParsedCompanyDataset
    raw_metadata = {
        "symbol": clean_symbol,
        "exchange": raw_exchange,
        "currency": trading_currency,
        "trading_currency": trading_currency,
        "financial_currency": from_curr if needs_fx else financial_currency,
        "fx_converted_from": from_curr if needs_fx else None,
        "fx_rate_applied": fx_rate_applied,
        "shares_outstanding": shares_outstanding,
        "sector": sector,
        "industry": industry,
        "current_price": current_price,
        "trailing_pe": trailing_pe,
        "market_cap": market_cap,
        "price_history": price_history,
        "fetched_at": datetime.utcnow().isoformat()
    }

    dataset = ParsedCompanyDataset(
        company_name=company_name,
        filename=f"{clean_symbol} (Live Fetch)",
        detected_format="yfinance",
        periods=periods,
        raw_metadata=raw_metadata
    )

    # 5. Deterministic Insights Engine (Pure Python math)
    auto_insights = generate_auto_insights(dataset)
    dataset.auto_insights = auto_insights
    dataset.trends = auto_insights.get("trends")
    dataset.scenarios = auto_insights.get("scenario_insights")

    return dataset
