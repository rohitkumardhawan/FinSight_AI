import { NextResponse } from 'next/server';
import { sql } from '@/lib/db';

export const dynamic = 'force-dynamic';

export async function GET() {
  try {
    // 1. Ensure table exists in Neon PostgreSQL
    await sql`
      CREATE TABLE IF NOT EXISTS demo_equity_coverage (
        id SERIAL PRIMARY KEY,
        ticker VARCHAR(10) UNIQUE NOT NULL,
        name VARCHAR(100) NOT NULL,
        sector VARCHAR(50) NOT NULL,
        industry VARCHAR(100) NOT NULL,
        market_cap VARCHAR(20) NOT NULL,
        is_demo_data BOOLEAN DEFAULT TRUE,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
      )
    `;

    // 2. Seed initial demo data if empty
    await sql`
      INSERT INTO demo_equity_coverage (ticker, name, sector, industry, market_cap)
      VALUES 
        ('AAPL', 'Apple Inc.', 'Technology', 'Consumer Electronics', '$3.54T'),
        ('NVDA', 'NVIDIA Corporation', 'Technology', 'Semiconductors', '$3.48T'),
        ('MSFT', 'Microsoft Corporation', 'Technology', 'Software & Cloud', '$3.15T'),
        ('GOOGL', 'Alphabet Inc.', 'Communication Services', 'Internet Media', '$2.12T'),
        ('AMZN', 'Amazon.com, Inc.', 'Consumer Cyclical', 'E-Commerce & Cloud', '$2.10T'),
        ('TSLA', 'Tesla, Inc.', 'Consumer Cyclical', 'Automotive & Energy', '$840B')
      ON CONFLICT (ticker) DO NOTHING
    `;

    // 3. Query all covered tickers
    const rows = await sql`
      SELECT ticker, name, sector, industry, market_cap, is_demo_data
      FROM demo_equity_coverage
      ORDER BY ticker ASC
    `;

    return NextResponse.json({
      status: 'success',
      source: 'Neon PostgreSQL (Production Branch)',
      count: rows.length,
      companies: rows,
    });
  } catch (err: any) {
    return NextResponse.json(
      {
        status: 'error',
        message: err.message,
      },
      { status: 500 }
    );
  }
}
