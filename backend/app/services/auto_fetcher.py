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
}


def _get_metric_val(df: Optional[pd.DataFrame], candidate_keys: List[str], col: Any) -> Optional[float]:
    """Safely extracts a numeric float value from a DataFrame given candidate row names."""
    if df is None or df.empty:
        return None
    for key in candidate_keys:
        if key in df.index:
            try:
                val = df.loc[key, col]
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

    sector = info.get("sector", "General")
    industry = info.get("industry", "General")

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
        interest = _get_metric_val(income_stmt, ["Interest Expense", "Interest Expense Non Operating"], dt)
        pbt = _get_metric_val(income_stmt, ["Pretax Income"], dt)
        tax_exp = _get_metric_val(income_stmt, ["Tax Provision", "Tax Effect Of Unusual Items"], dt)
        net_inc = _get_metric_val(income_stmt, ["Net Income Common Stockholders", "Net Income"], dt)
        eps = _get_metric_val(income_stmt, ["Diluted EPS", "Basic EPS"], dt)

        # Extract Balance Sheet metrics
        total_assets = _get_metric_val(balance_sheet, ["Total Assets"], dt)
        current_assets = _get_metric_val(balance_sheet, ["Current Assets"], dt)
        total_liab = _get_metric_val(balance_sheet, ["Total Liabilities Net Minority Interest", "Total Liabilities"], dt)
        current_liab = _get_metric_val(balance_sheet, ["Current Liabilities"], dt)
        total_equity = _get_metric_val(balance_sheet, ["Stockholders Equity", "Common Stock Equity"], dt)
        cash = _get_metric_val(balance_sheet, ["Cash And Cash Equivalents", "Cash Financial"], dt)
        inventory = _get_metric_val(balance_sheet, ["Inventory"], dt)
        total_debt = _get_metric_val(balance_sheet, ["Total Debt"], dt)

        # Extract Cash Flow metrics
        cfo = _get_metric_val(cashflow, ["Operating Cash Flow", "Cash Flow From Continuing Operating Activities"], dt)
        capex = _get_metric_val(cashflow, ["Capital Expenditure"], dt)
        if capex is not None:
            capex = abs(capex)
        fcf = _get_metric_val(cashflow, ["Free Cash Flow"], dt)
        if fcf is None and cfo is not None and capex is not None:
            fcf = cfo - capex

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
            total_liabilities=total_liab,
            current_liabilities=current_liab,
            total_equity=total_equity,
            cash_and_equivalents=cash,
            inventory=inventory,
            total_debt=total_debt,
            operating_cash_flow=cfo,
            capital_expenditure=capex,
            free_cash_flow=fcf,
            source=f"Yahoo Finance ({clean_symbol})"
        )
        periods.append(record)

    # 4. Construct ParsedCompanyDataset
    raw_metadata = {
        "symbol": clean_symbol,
        "exchange": raw_exchange,
        "currency": currency,
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
