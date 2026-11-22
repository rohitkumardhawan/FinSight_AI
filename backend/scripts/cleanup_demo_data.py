"""
FinSight AI — One-Time Demo Data Cleanup Script
==============================================
Safely cleans up Phase 1 demo/mock rows from Neon PostgreSQL:
1. Deletes demo research_records, financial_ratios, financial_statements where source='DEMO DATASET' or is_demo_data=True.
2. Removes demo seed companies that have 0 financial_periods and were part of the initial mock seed (e.g. AMZN, TSLA, NVDA if empty).
3. Preserves real companies with real statements/periods (like ASIANPAINT.NS, ASIANPAINT, AAPL).
4. Normalizes any exchange codes (e.g. NSI -> NSE).
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import text
from app.db.session import SessionLocal

def run_cleanup():
    db = SessionLocal()
    try:
        print("Starting targeted demo data cleanup on Neon Postgres...")

        # 1. Delete demo research records
        res_del = db.execute(text("DELETE FROM research_records WHERE source = 'DEMO DATASET';"))
        print(f"Deleted demo research records: {res_del.rowcount}")

        # 2. Delete demo financial ratios
        ratio_del = db.execute(text("DELETE FROM financial_ratios WHERE source = 'DEMO DATASET';"))
        print(f"Deleted demo financial ratios: {ratio_del.rowcount}")

        # 3. Delete demo financial statements
        stmt_del = db.execute(text("DELETE FROM financial_statements WHERE source = 'DEMO DATASET' OR is_demo_data = true;"))
        print(f"Deleted demo financial statements: {stmt_del.rowcount}")

        # 4. Normalize any NSI exchange codes to NSE
        norm_res = db.execute(text("UPDATE companies SET exchange = 'NSE' WHERE exchange = 'NSI' OR symbol LIKE '%.NS';"))
        print(f"Normalized exchange codes to NSE: {norm_res.rowcount}")

        # 5. Normalize BOM exchange codes to BSE
        norm_bse = db.execute(text("UPDATE companies SET exchange = 'BSE' WHERE exchange = 'BOM' OR symbol LIKE '%.BO';"))
        print(f"Normalized exchange codes to BSE: {norm_bse.rowcount}")

        # 6. Delete purely demo seed companies that have no periods and no uploaded docs
        comp_del = db.execute(text("""
            DELETE FROM companies 
            WHERE id NOT IN (SELECT DISTINCT company_id FROM financial_periods)
              AND id NOT IN (SELECT DISTINCT company_id FROM uploaded_documents)
              AND (data_source = 'DEMO DATASET' OR (symbol IN ('NVDA', 'AMZN', 'TSLA') AND data_source = 'yfinance' AND last_synced_at IS NULL));
        """))
        print(f"Deleted demo placeholder companies: {comp_del.rowcount}")

        db.commit()
        print("Demo data cleanup committed successfully.")

        # Print remaining companies
        remaining = db.execute(text("SELECT id, symbol, company_name, exchange, currency FROM companies ORDER BY id;")).fetchall()
        print(f"Remaining active companies in DB ({len(remaining)}):")
        for r in remaining:
            print(f"  ID {r[0]}: {r[1]} ({r[2]}) - Exchange: {r[3]}, Currency: {r[4]}")

    except Exception as e:
        db.rollback()
        print(f"Cleanup error: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    run_cleanup()
