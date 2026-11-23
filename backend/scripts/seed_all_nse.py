"""
FinSight AI — All-India NSE Equities Seeder (~2,000+ Companies)
===============================================================
- Downloads the official active equities list from NSE Archives:
  https://nsearchives.nseindia.com/content/equities/EQUITY_L.csv
- Fallback: backend/data/nse_all_equities.csv
- Filters active mainboard equities (SERIES == 'EQ' or 'BE')
- Upserts ALL ~2,000+ companies into Neon Postgres (`companies` table)
  with exchange="NSE", currency="INR", isin, listing_date, and top-10 is_featured.
- Purges non-Indian US tickers to ensure 100% India-dedicated research platform.
"""

import os
import sys
import csv
import io
import logging
from typing import List, Dict, Any

# Ensure backend directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import httpx
from sqlalchemy import text, select
from app.db.session import SessionLocal
from app.models.company import Company
from app.services.ticker_search import FEATURED_NSE_LIST

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("finsight.seed_all_nse")

NSE_EQUITY_L_URL = "https://nsearchives.nseindia.com/content/equities/EQUITY_L.csv"
DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data"))
FALLBACK_CSV_PATH = os.path.join(DATA_DIR, "nse_all_equities.csv")

US_TICKERS_TO_PURGE = ["AAPL", "MSFT", "NVDA", "GOOGL", "META", "AMZN", "AAPL.O", "MSFT.O", "GOOG", "TSLA"]


def fetch_nse_equity_csv() -> str:
    """Fetches EQUITY_L.csv from official NSE endpoint with local fallback."""
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
        logger.info(f"Downloading official NSE full equity list from {NSE_EQUITY_L_URL}...")
        with httpx.Client(timeout=15.0, headers=headers) as client:
            resp = client.get(NSE_EQUITY_L_URL)
            if resp.status_code == 200 and len(resp.text) > 5000:
                csv_text = resp.text
                logger.info(f"Successfully fetched {len(csv_text)} bytes from NSE Archives.")
                os.makedirs(DATA_DIR, exist_ok=True)
                with open(FALLBACK_CSV_PATH, "w", encoding="utf-8") as f:
                    f.write(csv_text)
                logger.info(f"Cached local fallback copy to {FALLBACK_CSV_PATH}")
    except Exception as ex:
        logger.warning(f"Live NSE CSV download failed: {ex}. Checking local fallback...")

    if not csv_text and os.path.exists(FALLBACK_CSV_PATH):
        try:
            with open(FALLBACK_CSV_PATH, "r", encoding="utf-8") as f:
                csv_text = f.read()
            logger.info("Loaded equity list from local fallback CSV.")
        except Exception as read_err:
            logger.error(f"Failed reading fallback CSV: {read_err}")

    if not csv_text:
        raise RuntimeError("Unable to download or load NSE EQUITY_L.csv.")

    return csv_text


def seed_all_nse():
    """Main execution function to seed ~2,000+ NSE companies into Neon Postgres."""
    csv_text = fetch_nse_equity_csv()
    reader = csv.DictReader(io.StringIO(csv_text))

    equities: List[Dict[str, Any]] = []
    for raw_row in reader:
        row = {k.strip(): v.strip() for k, v in raw_row.items() if k}
        sym = row.get("SYMBOL", "").strip().upper()
        name = row.get("NAME OF COMPANY", "").strip()
        series = row.get("SERIES", "").strip().upper()
        listing_date = row.get("DATE OF LISTING", "").strip()
        isin = row.get("ISIN NUMBER", "").strip()
        face_value = row.get("FACE VALUE", "").strip()

        if not sym or not name:
            continue
        # Active mainboard series only
        if series not in ("EQ", "BE"):
            continue

        full_ticker = f"{sym}.NS"
        is_featured = (full_ticker in FEATURED_NSE_LIST) or (sym in FEATURED_NSE_LIST)

        equities.append({
            "symbol": full_ticker,
            "ticker": full_ticker,
            "company_name": name,
            "series": series,
            "listing_date": listing_date,
            "isin": isin,
            "face_value": face_value,
            "is_featured": is_featured,
        })

    logger.info(f"Parsed {len(equities)} active mainboard NSE equities from CSV.")

    db = SessionLocal()
    try:
        # 1. Purge non-Indian US tickers to ensure 100% India focus
        logger.info("Purging non-Indian US tickers and non-NSE records...")
        from sqlalchemy import delete, or_
        from sqlalchemy.dialects.postgresql import insert as pg_insert
        purge_stmt = delete(Company).where(
            or_(
                Company.exchange != "NSE",
                Company.symbol.in_(US_TICKERS_TO_PURGE),
                Company.ticker.in_(US_TICKERS_TO_PURGE)
            )
        )
        db.execute(purge_stmt)
        db.commit()

        # 2. Fast Bulk Upsert using PostgreSQL ON CONFLICT (symbol) DO UPDATE
        logger.info(f"Upserting {len(equities)} equities in bulk batches...")
        batch_size = 500
        total_batches = (len(equities) + batch_size - 1) // batch_size

        for b_idx in range(total_batches):
            chunk = equities[b_idx * batch_size : (b_idx + 1) * batch_size]
            values_list = []
            for eq in chunk:
                sym = eq["symbol"]
                c_name = eq["company_name"]
                isin_val = eq["isin"]
                listing_val = eq["listing_date"]
                is_feat = eq["is_featured"]
                values_list.append({
                    "symbol": sym,
                    "ticker": sym,
                    "company_name": c_name,
                    "exchange": "NSE",
                    "currency": "INR",
                    "country": "India",
                    "data_source": "nse_archive",
                    "isin": isin_val,
                    "listing_date": listing_val,
                    "is_featured": is_feat,
                    "metadata_json": {
                        "isin": isin_val,
                        "listing_date": listing_val,
                        "series": eq["series"],
                        "quote": {
                            "symbol": sym,
                            "exchange": "NSE",
                            "currency": "INR",
                            "trading_currency": "INR",
                            "company_name": c_name
                        }
                    }
                })

            stmt = pg_insert(Company).values(values_list)
            stmt = stmt.on_conflict_do_update(
                index_elements=["ticker"],
                set_={
                    "company_name": stmt.excluded.company_name,
                    "symbol": stmt.excluded.symbol,
                    "exchange": stmt.excluded.exchange,
                    "currency": stmt.excluded.currency,
                    "isin": stmt.excluded.isin,
                    "listing_date": stmt.excluded.listing_date,
                    "is_featured": stmt.excluded.is_featured,
                }
            )
            db.execute(stmt)
            db.commit()
            logger.info(f"Committed batch {b_idx + 1}/{total_batches} ({min((b_idx + 1) * batch_size, len(equities))}/{len(equities)} equities)")

        # 3. Final verification count
        total_nse = db.execute(text("SELECT COUNT(*) FROM companies WHERE exchange = 'NSE';")).scalar()
        logger.info(f"=== SEEDING COMPLETE ===")
        logger.info(f"Total NSE companies in Neon Postgres: {total_nse}")
        logger.info(f"Successfully processed {len(equities)} equities.")

        if total_nse < 1800:
            raise RuntimeError(f"Expected >= 1,800 NSE companies, found {total_nse}!")

        print(f"\n==========================================")
        print(f"VERIFICATION: companies with exchange='NSE': {total_nse}")
        print(f"==========================================")
        print("SUCCESS: 2,000+ NSE companies successfully seeded into Neon Postgres!")

    except Exception as e:
        logger.error(f"Error during NSE seeding: {e}", exc_info=True)
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_all_nse()
