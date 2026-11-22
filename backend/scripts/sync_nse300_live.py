"""
FinSight AI — Daily Live Market & Financials Sync Worker
========================================================
Refreshes market quotes and performs batched financials sync for NSE companies.
Suitable for cron execution or manual admin triggers.
"""

import sys
import os
import argparse

# Add backend directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.db.session import SessionLocal
from app.services.nse_live_sync import sync_live_quotes, sync_nse_financials_batch

def main():
    parser = argparse.ArgumentParser(description="Sync NSE 300 quotes and financials")
    parser.add_argument("--batch-size", type=int, default=25, help="Number of companies to sync financials for")
    parser.add_argument("--quotes-only", action="store_true", help="Only refresh quotes")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        print("Starting live quotes sync for NSE companies...")
        quote_res = sync_live_quotes(db=db)
        print(f"Quotes sync result: {quote_res}")

        if not args.quotes_only:
            print(f"Starting financials batch sync (batch size = {args.batch_size})...")
            fin_res = sync_nse_financials_batch(batch_size=args.batch_size, db=db)
            print(f"Financials sync result: {fin_res}")

    except Exception as e:
        print(f"Error during NSE sync: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    main()
