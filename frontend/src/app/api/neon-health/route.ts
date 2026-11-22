import { NextResponse } from 'next/server';
import { sql } from '@/lib/db';

export const dynamic = 'force-dynamic';

export async function GET() {
  try {
    const start = Date.now();
    const rows = await sql`
      SELECT 
        NOW() as current_time, 
        current_database() as database,
        current_user as user,
        version() as version
    `;
    const latency = Date.now() - start;

    return NextResponse.json({
      status: 'connected',
      service: 'Neon Lakebase Postgres',
      branch: process.env.NEON_BRANCH || 'production',
      branch_id: process.env.NEON_BRANCH_ID || 'br-gentle-hat-beg2xire',
      database: rows[0].database,
      latency_ms: latency,
      postgres_version: String(rows[0].version).split(',')[0],
      server_time: rows[0].current_time,
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
