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
    "ASIANPAINT.NS",
    "RELIANCE.NS",
    "TCS.NS",
    "HDFCBANK.NS",
    "INFY.NS",
    "ICICIBANK.NS",
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
            market_cap = quote.get("market_cap") or meta.get("market_cap")

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
                "change_percent": change_percent,
                "market_cap": market_cap
            })
            if len(ordered) >= limit:
                break

        return ordered
    except Exception as e:
        logger.warning(f"Featured companies lookup warning: {e}")
        return []


def _query_db_companies(db: Session, query: str, limit: int = 12) -> List[Dict[str, Any]]:
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
                    func.lower(Company.company_name).like(search_pattern),
                    func.lower(Company.isin).like(search_pattern),
                )
            )
            .order_by(
                (func.lower(Company.symbol) == q_lower).desc(),
                (func.lower(Company.ticker) == q_lower).desc(),
                func.lower(Company.symbol).startswith(q_lower).desc(),
                func.lower(Company.company_name).startswith(q_lower).desc(),
                Company.company_name.asc()
            )
            .limit(limit)
        )
        local_companies = db.execute(stmt).scalars().all()
        mapped = []
        for comp in local_companies:
            sym = (comp.symbol or comp.ticker or f"ID-{comp.id}").strip()
            exch = _normalize_exchange(sym, comp.exchange or "NSE")
            currency = comp.currency or ("INR" if (sym.endswith(".NS") or sym.endswith(".BO") or exch in ("NSE", "BSE")) else "INR")
            meta = comp.metadata_json or {}
            quote = meta.get("quote", {})
            market_cap = quote.get("market_cap") or meta.get("market_cap")

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
                "change_percent": quote.get("change_percent"),
                "market_cap": market_cap
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
                    
                    # Strictly restrict to Indian equities (NSE / BSE / INR)
                    is_indian = (
                        symbol.endswith(".NS")
                        or symbol.endswith(".BO")
                        or exch in ("NSE", "BSE")
                        or "NSI" in (raw_exch or "").upper()
                        or "BOM" in (raw_exch or "").upper()
                    )
                    if not is_indian:
                        continue

                    sector = q.get("sector") or q.get("sectorDisp") or "Indian Equities"
                    currency = "INR"

                    quotes_out.append({
                        "symbol": symbol,
                        "name": name,
                        "exchange": exch,
                        "sector": sector,
                        "currency": currency,
                        "quote_type": quote_type or "EQUITY",
                        "is_cached": False,
                        "data_source": "yfinance",
                        "market_cap": q.get("marketCap")
                    })
    except Exception as ex:
        logger.warning(f"Yahoo Search HTTP warning: {ex}")
    return quotes_out


def _calculate_search_rank(item: Dict[str, Any], query: str) -> tuple:
    """
    Ranks search results deterministically:
    0: Exact symbol match (e.g. AAPL == AAPL, TCS == TCS.NS)
    1: Prefix symbol match (e.g. ASIANPAINT -> ASIANPAINT.NS)
    2: Exact company name match
    3: Prefix company name match
    4: Substring symbol match
    5: Substring company name match
    6: Other matches
    Within each tier, cached items and shorter symbols are preferred.
    """
    q = query.strip().upper()
    q_root = q[:-3] if (q.endswith(".NS") or q.endswith(".BO")) else q

    sym = (item.get("symbol") or "").strip().upper()
    sym_root = sym[:-3] if (sym.endswith(".NS") or sym.endswith(".BO")) else sym
    name = (item.get("name") or "").strip().upper()

    # Tier 0: Exact symbol match
    if sym == q or sym_root == q or sym == f"{q}.NS" or sym == f"{q}.BO" or sym_root == q_root:
        tier = 0
    # Tier 1: Prefix symbol match
    elif sym.startswith(q) or sym_root.startswith(q) or sym.startswith(q_root) or sym_root.startswith(q_root):
        tier = 1
    # Tier 2: Exact company name match
    elif name == q or name == q_root:
        tier = 2
    # Tier 3: Prefix company name match
    elif name.startswith(q) or name.startswith(q_root):
        tier = 3
    # Tier 4: Substring symbol match
    elif q in sym or q_root in sym:
        tier = 4
    # Tier 5: Substring company name match
    elif q in name or q_root in name:
        tier = 5
    else:
        tier = 6

    # Prefer cached items (0 before 1), prefer NSE (.NS) over BSE (.BO), then shorter symbols
    is_cached_score = 0 if item.get("is_cached") else 1
    exch_pref = 0 if sym.endswith(".NS") else 1 if not (sym.endswith(".BO") or sym.endswith(".L")) else 2
    return (tier, is_cached_score, exch_pref, len(sym), sym)


async def search_tickers(
    query: Optional[str] = None,
    limit: int = 15,
    db: Optional[Session] = None
) -> List[Dict[str, Any]]:
    """
    Search for equities across Indian (NSE/BSE), US, and Global exchanges.
    - If query is empty: Returns top 8-10 featured NSE companies with cached prices.
    - If query is provided: Searches Neon Postgres first, then Yahoo Finance,
      and ranks exact ticker matches and prefix matches strictly at the top.
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
        tasks.append(asyncio.to_thread(_query_db_companies, db, cleaned_query, 12))
    else:
        tasks.append(asyncio.sleep(0, result=[]))

    tasks.append(_fetch_yahoo_quotes(cleaned_query, limit))

    results_db, results_yahoo = await asyncio.gather(*tasks)

    # Merge and deduplicate, prioritizing DB results
    all_candidates: List[Dict[str, Any]] = []
    seen_symbols = set()

    for item in results_db:
        sym = item["symbol"].upper()
        if sym not in seen_symbols:
            seen_symbols.add(sym)
            all_candidates.append(item)

    for item in results_yahoo:
        sym = item["symbol"].upper()
        if sym not in seen_symbols:
            seen_symbols.add(sym)
            all_candidates.append(item)

    # Strictly rank exact matches and prefix matches at the very top
    all_candidates.sort(key=lambda it: _calculate_search_rank(it, cleaned_query))

    return all_candidates[:limit]
