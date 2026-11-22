"""
FinSight AI — Phase 4 Database Migration Script
Applies safe, additive, non-destructive schema updates to Neon PostgreSQL.
"""
from sqlalchemy import text
from app.db.session import engine

def migrate():
    print("Connecting to Neon PostgreSQL...")
    with engine.begin() as conn:
        print("Enabling vector extension...")
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))

        print("Adding columns to companies...")
        conn.execute(text("ALTER TABLE companies ADD COLUMN IF NOT EXISTS symbol VARCHAR(50);"))
        conn.execute(text("ALTER TABLE companies ADD COLUMN IF NOT EXISTS data_source VARCHAR(50) DEFAULT 'yfinance';"))
        conn.execute(text("ALTER TABLE companies ADD COLUMN IF NOT EXISTS last_synced_at TIMESTAMP WITH TIME ZONE;"))
        conn.execute(text("ALTER TABLE companies ADD COLUMN IF NOT EXISTS metadata_json JSON;"))

        print("Updating existing companies rows with symbol = ticker...")
        conn.execute(text("UPDATE companies SET symbol = ticker WHERE symbol IS NULL AND ticker IS NOT NULL;"))
        conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_companies_symbol ON companies(symbol) WHERE symbol IS NOT NULL;"))

        print("Adding company_id to financial_periods...")
        conn.execute(text("ALTER TABLE financial_periods ADD COLUMN IF NOT EXISTS company_id INTEGER REFERENCES companies(id) ON DELETE CASCADE;"))
        conn.execute(text("ALTER TABLE financial_periods ALTER COLUMN dataset_id DROP NOT NULL;"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_financial_periods_company_id ON financial_periods(company_id);"))

        print("Adding company_id to rag_chunks...")
        conn.execute(text("ALTER TABLE rag_chunks ADD COLUMN IF NOT EXISTS company_id INTEGER REFERENCES companies(id) ON DELETE CASCADE;"))
        conn.execute(text("ALTER TABLE rag_chunks ALTER COLUMN dataset_id DROP NOT NULL;"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_rag_chunks_company_id ON rag_chunks(company_id);"))
        
        print("Ensuring HNSW index on rag_chunks embedding...")
        try:
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_rag_chunks_embedding_hnsw ON rag_chunks USING hnsw ((embedding::halfvec(3072)) halfvec_cosine_ops);"))
        except Exception as e:
            print("Notice on HNSW index:", e)

    print("Phase 4 Database Migration completed successfully!")

if __name__ == "__main__":
    migrate()
