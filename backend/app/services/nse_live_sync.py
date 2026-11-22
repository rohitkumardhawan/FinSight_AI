"""
FinSight AI — Live Top 300 NSE Dataset & Auto-Sync Engine
=========================================================
- Fetches official live NSE/Nifty Index constituents from NiftyIndices.
- Upserts top 300 NSE equities into Neon Postgres.
- Fast batched live quotes refresh via yfinance.download (chunks of 50).
- Resumable background sync for multi-year financial statements & pgvector embeddings.
"""

import os
import csv
import io
import time
import logging
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

import httpx
import yfinance as yf
from sqlalchemy.orm import Session
from sqlalchemy import select, or_, func

from app.models.company import Company
from app.models.dataset import FinancialPeriod
from app.services.auto_fetcher import fetch_company_data
from app.services.rag_service import index_company_chunks

logger = logging.getLogger(__name__)

NIFTY_CSV_URL = "https://www.niftyindices.com/IndexConstituent/ind_nifty500list.csv"
FALLBACK_CSV_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "nse300_fallback.csv")

# Standard Featured / Priority Top Indian Companies for Instant Dropdown Display
FEATURED_NSE_SYMBOLS = [
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


def fetch_nse_constituents(limit: int = 300) -> List[Dict[str, str]]:
    """
    Fetches the live NSE constituent list from Nifty Indices CSV.
    Falls back to local fallback CSV if the official endpoint is temporarily unreachable.
    Returns the top `limit` equities formatted with .NS symbol.
    """
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/csv,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }

    csv_text = ""
    try:
        with httpx.Client(timeout=10.0, headers=headers) as client:
            resp = client.get(NIFTY_CSV_URL)
            if resp.status_code == 200 and len(resp.text) > 500:
                csv_text = resp.text
                logger.info(f"Successfully fetched live Nifty constituent list ({len(csv_text)} bytes)")
                # Cache local fallback
                try:
                    os.makedirs(os.path.dirname(FALLBACK_CSV_PATH), exist_ok=True)
                    with open(FALLBACK_CSV_PATH, "w", encoding="utf-8") as f:
                        f.write(csv_text)
                except Exception as save_err:
                    logger.debug(f"Could not save fallback CSV: {save_err}")
    except Exception as ex:
        logger.warning(f"Live Nifty CSV download failed: {ex}. Checking local fallback...")

    if not csv_text and os.path.exists(FALLBACK_CSV_PATH):
        try:
            with open(FALLBACK_CSV_PATH, "r", encoding="utf-8") as f:
                csv_text = f.read()
            logger.info("Using cached local fallback CSV for NSE constituents.")
        except Exception as read_err:
            logger.error(f"Failed reading fallback CSV: {read_err}")

    if not csv_text:
        raise RuntimeError("Unable to obtain NSE constituent list from network or local fallback.")

    # Parse CSV
    reader = csv.DictReader(io.StringIO(csv_text))
    constituents: List[Dict[str, str]] = []

    for row in reader:
        # Standard columns: Company Name, Industry, Symbol, Series, ISIN Code
        raw_sym = row.get("Symbol", "").strip()
        name = row.get("Company Name", "").strip()
        industry = row.get("Industry", "").strip()
        series = row.get("Series", "").strip().upper()

        # Only standard equity series (EQ)
        if not raw_sym or (series and series != "EQ"):
            continue

        sym = f"{raw_sym}.NS"
        constituents.append({
            "symbol": sym,
            "ticker": raw_sym,
            "company_name": name,
            "sector": industry or "General",
            "industry": industry or "General",
            "exchange": "NSE",
            "currency": "INR",
            "country": "India"
        })

        if len(constituents) >= limit:
            break

    return constituents


def seed_nse300(db: Session, limit: int = 300) -> Dict[str, Any]:
    """
    Upserts the Top 300 NSE companies into Neon Postgres in high-speed batch.
    Preserves existing financial data if already fetched.
    """
    constituents = fetch_nse_constituents(limit=limit)
    seeded_count = 0
    updated_count = 0

    # High-speed pre-load of all existing companies into in-memory dictionary
    all_existing = db.execute(select(Company)).scalars().all()
    existing_map: Dict[str, Company] = {}
    for c in all_existing:
        if c.symbol:
            existing_map[c.symbol.upper()] = c
        if c.ticker:
            existing_map[c.ticker.upper()] = c

    for item in constituents:
        sym = item["symbol"].upper()
        ticker = item["ticker"].upper()

        company = existing_map.get(sym) or existing_map.get(ticker)

        if not company:
            company = Company(
                symbol=item["symbol"],
                ticker=item["symbol"],
                company_name=item["company_name"],
                exchange="NSE",
                currency="INR",
                sector=item["sector"],
                industry=item["industry"],
                country="India",
                data_source="nse_index",
                metadata_json={"quote": {"exchange": "NSE", "currency": "INR", "country": "India"}}
            )
            db.add(company)
            existing_map[sym] = company
            seeded_count += 1
        else:
            # Normalize existing record to canonical NSE & INR
            company.symbol = item["symbol"]
            company.ticker = item["symbol"]
            company.exchange = "NSE"
            company.currency = "INR"
            company.country = "India"
            if not company.company_name or company.company_name == sym:
                company.company_name = item["company_name"]
            if not company.sector:
                company.sector = item["sector"]
            if not company.industry:
                company.industry = item["industry"]
            updated_count += 1

    db.commit()
    logger.info(f"NSE 300 Seeding complete: {seeded_count} newly added, {updated_count} normalized.")
    return {
        "status": "success",
        "total_constituents": len(constituents),
        "newly_seeded": seeded_count,
        "updated_or_normalized": updated_count
    }


def sync_live_quotes(symbols: Optional[List[str]] = None, db: Optional[Session] = None) -> Dict[str, Any]:
    """
    Fast batched quotes refresh using yfinance.download in chunks of 50.
    Updates live price and daily % change for NSE companies in Neon DB.
    """
    if db is None:
        from app.db.session import SessionLocal
        db = SessionLocal()
        should_close = True
    else:
        should_close = False

    try:
        if not symbols:
            # Query all NSE companies in DB
            rows = db.execute(
                select(Company.symbol).where(
                    or_(Company.exchange == "NSE", Company.symbol.like("%.NS"))
                )
            ).scalars().all()
            symbols = [r for r in rows if r]

        if not symbols:
            return {"status": "no_symbols", "updated": 0}

        chunk_size = 50
        total_updated = 0
        now_utc = datetime.now(timezone.utc)

        # Pre-load companies for fast in-memory quote attachment
        all_companies = db.execute(
            select(Company).where(
                or_(Company.exchange == "NSE", Company.symbol.like("%.NS"))
            )
        ).scalars().all()
        comp_map: Dict[str, Company] = {c.symbol.upper(): c for c in all_companies if c.symbol}

        for i in range(0, len(symbols), chunk_size):
            chunk = symbols[i : i + chunk_size]
            try:
                data = yf.download(chunk, period="5d", group_by="ticker", threads=True, progress=False)
                if data is None or data.empty:
                    continue

                for sym in chunk:
                    close_series = None
                    try:
                        if len(chunk) == 1:
                            close_series = data["Close"].dropna()
                        elif sym in data.columns.levels[0]:
                            close_series = data[sym]["Close"].dropna()
                    except Exception:
                        continue

                    if close_series is None or len(close_series) < 1:
                        continue

                    last_price = float(close_series.iloc[-1])
                    prev_close = float(close_series.iloc[-2]) if len(close_series) >= 2 else last_price
                    change_pct = round(((last_price - prev_close) / prev_close) * 100, 2) if prev_close > 0 else 0.0

                    comp = comp_map.get(sym.upper())
                    if comp:
                        meta = comp.metadata_json or {}
                        quote = meta.get("quote", {})
                        quote.update({
                            "current_price": last_price,
                            "previous_close": prev_close,
                            "change_percent": change_pct,
                            "quote_updated_at": now_utc.isoformat(),
                            "currency": "INR",
                            "exchange": "NSE"
                        })
                        meta["quote"] = quote
                        comp.metadata_json = meta
                        total_updated += 1

                db.commit()
            except Exception as batch_err:
                logger.warning(f"Batch quotes sync error for chunk {i}: {batch_err}")

        return {"status": "success", "total_symbols": len(symbols), "quotes_updated": total_updated}
    finally:
        if should_close:
            db.close()


def sync_nse_financials_batch(batch_size: int = 25, db: Optional[Session] = None) -> Dict[str, Any]:
    """
    Resumable background worker:
    Syncs full multi-year financial statements, deterministic ratios,
    and pgvector embeddings for stale or un-analyzed NSE companies.
    Applies rate limiting (0.5s pause) with exponential backoff on HTTP 429.
    """
    if db is None:
        from app.db.session import SessionLocal
        db = SessionLocal()
        should_close = True
    else:
        should_close = False

    try:
        now_utc = datetime.now(timezone.utc)
        # Find companies missing periods or with last_synced_at older than 24h
        # Prioritize companies with 0 periods first
        candidates = db.execute(
            select(Company)
            .where(
                or_(Company.exchange == "NSE", Company.symbol.like("%.NS"))
            )
            .order_by(Company.last_synced_at.asc().nullsfirst())
            .limit(batch_size)
        ).scalars().all()

        synced_symbols: List[str] = []
        errors: Dict[str, str] = {}

        for comp in candidates:
            sym = comp.symbol or comp.ticker
            if not sym:
                continue

            # Ensure .NS suffix
            clean_sym = sym if sym.endswith(".NS") else f"{sym}.NS"

            backoff = 1.0
            max_retries = 3
            success = False

            for attempt in range(max_retries):
                try:
                    parsed = fetch_company_data(clean_sym)

                    # Update company
                    comp.company_name = parsed.company_name
                    comp.exchange = "NSE"
                    comp.currency = "INR"
                    comp.data_source = "yfinance"
                    comp.last_synced_at = now_utc
                    comp.metadata_json = {
                        "trends": parsed.trends,
                        "scenarios": parsed.scenarios,
                        "auto_insights": parsed.auto_insights,
                        "quote": parsed.raw_metadata
                    }

                    # Persist Financial Periods
                    db.query(FinancialPeriod).filter(FinancialPeriod.company_id == comp.id).delete()
                    for p in parsed.periods:
                        fp = FinancialPeriod(
                            company_id=comp.id,
                            fiscal_year=p.fiscal_year,
                            fiscal_period=p.fiscal_period,
                            statement_type=p.statement_type,
                            metrics_json=p.model_dump()
                        )
                        db.add(fp)

                    db.commit()

                    # Index RAG chunks into pgvector
                    try:
                        index_company_chunks(db, comp.id, parsed)
                    except Exception as rag_err:
                        logger.warning(f"RAG indexing warning for {clean_sym}: {rag_err}")

                    synced_symbols.append(clean_sym)
                    success = True
                    break
                except Exception as ex:
                    err_msg = str(ex)
                    if "429" in err_msg or "Too Many Requests" in err_msg:
                        logger.warning(f"Rate limited on {clean_sym}. Backing off {backoff}s...")
                        time.sleep(backoff)
                        backoff *= 2
                    else:
                        errors[clean_sym] = err_msg
                        break

            # Polite pause between tickers to stay well under rate limits
            time.sleep(0.6)

        return {
            "status": "completed",
            "batch_processed": len(candidates),
            "synced_count": len(synced_symbols),
            "synced_symbols": synced_symbols,
            "errors": errors
        }
    finally:
        if should_close:
            db.close()
