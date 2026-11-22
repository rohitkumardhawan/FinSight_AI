import { neon } from '@neondatabase/serverless';

/**
 * Returns clean connection string from environment variables,
 * stripping any quotation marks pulled by the CLI.
 */
function getDatabaseUrl(): string {
  const rawUrl = process.env.DATABASE_URL || '';
  return rawUrl.replace(/^"(.*)"$/, '$1').trim();
}

/**
 * Neon Serverless SQL Client
 * Uses HTTP transport for fast, connection-pool-friendly queries on Vercel / Next.js.
 */
export const sql = neon(getDatabaseUrl());
