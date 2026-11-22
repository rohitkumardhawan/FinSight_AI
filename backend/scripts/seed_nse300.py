"""
FinSight AI — Top 300 NSE Seeding Script
========================================
Fetches live NSE constituent list from Nifty Indices and populates
top 300 equities into Neon Postgres.
"""

import sys
import os

# Add backend directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import text
from app.db.session import SessionLocal
from app.services.nse_live_sync import seed_nse300, sync_live_quotes, FEATURED_NSE_SYMBOLS

def main():
    print("Connecting to Neon Postgres...")
    db = SessionLocal()
    try:
        print("Fetching official NSE constituents and seeding Top 300 equities...")
        res = seed_nse300(db, limit=300)
        print(f"Result: {res}")

        print("Updating live quotes for featured top NSE companies...")
        quote_res = sync_live_quotes(symbols=FEATURED_NSE_SYMBOLS, db=db)
        print(f"Featured quotes update: {quote_res}")

        # Verification count
        count = db.execute(text("SELECT COUNT(*) FROM companies WHERE exchange = 'NSE';")).scalar()
        print(f"\n==========================================")
        print(f"VERIFICATION: companies with exchange='NSE': {count}")
        print(f"==========================================")
        if count >= 300:
            print("SUCCESS: 300+ NSE companies successfully seeded into Neon Postgres!")
        else:
            print(f"WARNING: Count is {count}, expected >= 300.")

    except Exception as e:
        print(f"Error seeding NSE 300: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    main()
