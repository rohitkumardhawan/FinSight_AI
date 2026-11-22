"""
FinSight AI — Ticker Search Service
===================================
Resolves company names/symbols across Indian (NSE .NS, BSE .BO) and
US/Global markets via high-speed async Yahoo Finance search merged with
cached Neon Postgres records.
"""

from typing import List, Dict, Any, Optional
import logging
import asyncio
import httpx
from sqlalchemy.orm import Session
from sqlalchemy import select, or_, func

from app.models.company import Company

logger = logging.getLogger(__name__)

FEATURED_NSE_LIST = [
    "RELIANCE.NS",
    "TCS.NS",
    "HDFCBANK.NS",
    "INFY.NS",
    "ICICIBANK.NS",
    "ASIANPAINT.NS",
    "ITC.NS",
    "SBIN.NS",
    "BHARTIARTL.NS",
    "LT.NS"
]


def _normalize_exchange(symbol: str, raw_exchange: str) -> str:
    """Normalizes exchange identifiers to standard badges (NSE, BSE, NASDAQ, NYSE, etc.)."""
    s_upper = symbol.upper()
    ex_upper = (raw_exchange or "").upper()

    if s_upper.endswith(".NS") or "NSI" in ex_upper or "NSE" in ex_upper:
        return "NSE"
    if s_upper.endswith(".BO") or "BOM" in ex_upper or "BSE" in ex_upper:
        return "BSE"
    if any(k in ex_upper for k in ("NMS", "NGS", "NAS", "NASDAQ")):
        return "NASDAQ"
    if any(k in ex_upper for k in ("NYQ", "NYS", "NYSE")):
        return "NYSE"
    if "LSE" in ex_upper or s_upper.endswith(".L"):
        return "LSE"
    return ex_upper or ("NSE" if s_upper.endswith(".NS") else "GLOBAL")


def _get_featured_companies(db: Session, limit: int = 10) -> List[Dict[str, Any]]:
    """Returns top 8-10 featured Indian companies with live cached prices from Neon Postgres."""
    try:
        companies = db.execute(
            select(Company).where(Company.symbol.in_(FEATURED_NSE_LIST))
        ).scalars().all()

        comp_dict = {c.symbol: c for c in companies if c.symbol}
        ordered: List[Dict[str, Any]] = []

        for sym in FEATURED_NSE_LIST:
            comp = comp_dict.get(sym)
            if not comp:
                continue

            meta = comp.metadata_json or {}
            quote = meta.get("quote", {})
            current_price = quote.get("current_price")
            change_percent = quote.get("change_percent")

            ordered.append({
                "symbol": comp.symbol,
                "name": comp.company_name,
                "exchange": "NSE",
                "sector": comp.sector or "Nifty 50",
                "currency": "INR",
                "quote_type": "EQUITY",
                "is_cached": True,
                "data_source": "neon_db",
                "price": current_price,
                "change_percent": change_percent
            })
            if len(ordered) >= limit:
                break

        return ordered
    except Exception as e:
        logger.warning(f"Featured companies lookup warning: {e}")
        return []


def _query_db_companies(db: Session, query: str, limit: int = 10) -> List[Dict[str, Any]]:
    """Synchronous database query for cached/NSE companies in Neon Postgres."""
    try:
        q_lower = query.strip().lower()
        search_pattern = f"%{q_lower}%"
        stmt = (
            select(Company)
            .where(
                or_(
                    func.lower(Company.symbol).like(search_pattern),
                    func.lower(Company.ticker).like(search_pattern),
                    func.lower(Company.company_name).like(search_pattern)
                )
            )
            .order_by(
                func.lower(Company.symbol).startswith(q_lower).desc(),
                Company.company_name.asc()
            )
            .limit(limit)
        )
        local_companies = db.execute(stmt).scalars().all()
        mapped = []
        for comp in local_companies:
            sym = (comp.symbol or comp.ticker or f"ID-{comp.id}").strip()
            exch = _normalize_exchange(sym, comp.exchange or "NSE")
            currency = comp.currency or ("INR" if (sym.endswith(".NS") or sym.endswith(".BO") or exch in ("NSE", "BSE")) else "USD")
            meta = comp.metadata_json or {}
            quote = meta.get("quote", {})

            mapped.append({
                "symbol": sym,
                "name": comp.company_name,
                "exchange": exch,
                "sector": comp.sector or "Indian Equities",
                "currency": currency,
                "quote_type": "EQUITY",
                "is_cached": True,
                "data_source": comp.data_source or "neon_db",
                "price": quote.get("current_price"),
                "change_percent": quote.get("change_percent")
            })
        return mapped
    except Exception as e:
        logger.warning(f"Database ticker lookup warning: {e}")
        return []


async def _fetch_yahoo_quotes(query: str, limit: int) -> List[Dict[str, Any]]:
    """Asynchronous HTTP query to Yahoo Finance search endpoint."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    url = f"https://query2.finance.yahoo.com/v1/finance/search?q={query}&quotesCount={limit}&newsCount=0"
    quotes_out = []
    try:
        async with httpx.AsyncClient(timeout=4.0, headers=headers) as client:
            resp = await client.get(url)
            if resp.status_code == 200:
                data = resp.json()
                raw_quotes = data.get("quotes", [])
                for q in raw_quotes:
                    symbol = q.get("symbol", "").strip()
                    if not symbol:
                        continue

                    quote_type = q.get("quoteType", "").upper()
                    if quote_type not in ("EQUITY", ""):
                        continue

                    name = q.get("longname") or q.get("shortname") or symbol
                    raw_exch = q.get("exchDisp") or q.get("exchange") or "GLOBAL"
                    exch = _normalize_exchange(symbol, raw_exch)
                    sector = q.get("sector") or q.get("sectorDisp") or "General"
                    currency = "INR" if (symbol.endswith(".NS") or symbol.endswith(".BO") or exch in ("NSE", "BSE")) else "USD"

                    quotes_out.append({
                        "symbol": symbol,
                        "name": name,
                        "exchange": exch,
                        "sector": sector,
                        "currency": currency,
                        "quote_type": quote_type or "EQUITY",
                        "is_cached": False,
                        "data_source": "yfinance"
                    })
    except Exception as ex:
        logger.warning(f"Yahoo Search HTTP warning: {ex}")
    return quotes_out


async def search_tickers(
    query: Optional[str] = None,
    limit: int = 15,
    db: Optional[Session] = None
) -> List[Dict[str, Any]]:
    """
    Search for equities across Indian (NSE/BSE), US, and Global exchanges.
    - If query is empty: Returns top 8-10 featured NSE companies with cached prices.
    - If query is provided: Searches Neon Postgres first (up to 10), then Yahoo Finance.
    """
    cleaned_query = (query or "").strip()

    # Empty query behavior: Top 8-10 featured NSE companies
    if not cleaned_query:
        if db:
            return _get_featured_companies(db, limit=min(limit, 10))
        return []

    # Run DB query and Yahoo query concurrently
    tasks = []
    if db:
        tasks.append(asyncio.to_thread(_query_db_companies, db, cleaned_query, 10))
    else:
        tasks.append(asyncio.sleep(0, result=[]))

    tasks.append(_fetch_yahoo_quotes(cleaned_query, limit))

    results_db, results_yahoo = await asyncio.gather(*tasks)

    # Merge and deduplicate, prioritizing DB results
    results: List[Dict[str, Any]] = []
    seen_symbols = set()

    for item in results_db:
        sym = item["symbol"].upper()
        if sym not in seen_symbols:
            seen_symbols.add(sym)
            results.append(item)

    for item in results_yahoo:
        sym = item["symbol"].upper()
        if sym not in seen_symbols:
            seen_symbols.add(sym)
            results.append(item)
            if len(results) >= limit:
                break

    return results
