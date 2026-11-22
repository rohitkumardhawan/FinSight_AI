/**
 * FinSight AI — Institutional Financial Formatters
 * ================================================
 * Formats financial metrics strictly by company currency:
 * - INR (₹): Raw values divided by 1e7 and displayed in Crores (₹XX,XXX.XX Cr).
 * - USD ($) / Other: Formatted in B (>= 1e9) or M (>= 1e6) or K with matching symbol.
 * - Per-share (Price, EPS): Currency symbol + 2 decimal places (₹45.11 / $45.11).
 * - Multiples & Percentages (P/E, OPM, Margins): Max 2 decimal places (51.69x, 15.78%).
 * - Exchange Normalization: NSI -> NSE, BOM -> BSE, NMS/NYQ -> NASDAQ/NYSE.
 */

export function normalizeExchange(exchange?: string | null, symbol?: string | null): string {
  const ex = (exchange || '').trim().toUpperCase();
  const sym = (symbol || '').trim().toUpperCase();

  if (sym.endsWith('.NS') || ex === 'NSI' || ex === 'NSE') {
    return 'NSE';
  }
  if (sym.endsWith('.BO') || ex === 'BOM' || ex === 'BSE') {
    return 'BSE';
  }
  if (['NMS', 'NGS', 'NGM', 'NAS', 'NASDAQ'].includes(ex)) {
    return 'NASDAQ';
  }
  if (['NYQ', 'NYS', 'NYSE'].includes(ex)) {
    return 'NYSE';
  }
  if (ex.includes('LSE') || sym.endsWith('.L')) {
    return 'LSE';
  }
  return ex || (sym.endsWith('.NS') ? 'NSE' : sym.endsWith('.BO') ? 'BSE' : 'GLOBAL');
}

export function getCurrencySymbol(currency?: string | null): string {
  const cur = (currency || '').trim().toUpperCase();
  if (cur === 'INR' || cur === '₹') return '₹';
  if (cur === 'EUR' || cur === '€') return '€';
  if (cur === 'GBP' || cur === '£') return '£';
  if (cur === 'JPY' || cur === '¥') return '¥';
  return '$';
}

export function getUnitLabel(currency?: string | null): string {
  const cur = (currency || '').trim().toUpperCase();
  return cur === 'INR' ? '₹ Cr' : '$M';
}

/**
 * Formats aggregate financial values (Revenue, Assets, Net Income, etc.)
 * - For INR: Divide by 1e7 (Crores) and display as ₹XX,XXX.XX Cr
 * - For USD / others: Auto B (>= 1e9), M (>= 1e6)
 */
export function formatFinancialValue(
  value: number | string | null | undefined,
  currency?: string | null,
  options?: { showUnit?: boolean }
): string {
  if (value === null || value === undefined || value === '') return '—';
  const num = typeof value === 'number' ? value : parseFloat(value);
  if (isNaN(num)) return '—';

  const cur = (currency || '').trim().toUpperCase();
  const symbol = getCurrencySymbol(cur);
  const showUnit = options?.showUnit !== false;

  // INR: Convert raw Rupees to Crores (1 Cr = 1e7)
  if (cur === 'INR') {
    const isNegative = num < 0;
    const absVal = Math.abs(num);
    const inCrores = absVal / 1e7;
    const formatted = inCrores.toLocaleString('en-IN', {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    });
    const prefix = isNegative ? '-' : '';
    return showUnit ? `${prefix}${symbol}${formatted} Cr` : `${prefix}${symbol}${formatted}`;
  }

  // USD / Global: Auto Scale
  const isNegative = num < 0;
  const absVal = Math.abs(num);
  const prefix = isNegative ? '-' : '';

  if (absVal >= 1e9) {
    const inBillions = (absVal / 1e9).toFixed(2);
    return `${prefix}${symbol}${Number(inBillions).toLocaleString()}B`;
  }
  if (absVal >= 1e6) {
    const inMillions = (absVal / 1e6).toFixed(2);
    return `${prefix}${symbol}${Number(inMillions).toLocaleString()}M`;
  }
  if (absVal >= 1e3) {
    const inThousands = (absVal / 1e3).toFixed(2);
    return `${prefix}${symbol}${Number(inThousands).toLocaleString()}K`;
  }

  return `${prefix}${symbol}${absVal.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

/**
 * Formats Per-Share Metrics (Stock Price, EPS, Target Price)
 * Always uses company's currency symbol rounded to 2 decimal places.
 */
export function formatPerShare(
  value: number | string | null | undefined,
  currency?: string | null
): string {
  if (value === null || value === undefined || value === '') return '—';
  const num = typeof value === 'number' ? value : parseFloat(value);
  if (isNaN(num)) return '—';

  const cur = (currency || '').trim().toUpperCase();
  const symbol = getCurrencySymbol(cur);
  const isNegative = num < 0;
  const absVal = Math.abs(num);
  const prefix = isNegative ? '-' : '';

  const locale = cur === 'INR' ? 'en-IN' : 'en-US';
  const formatted = absVal.toLocaleString(locale, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });

  return `${prefix}${symbol}${formatted}`;
}

/**
 * Formats Valuation Multiples (P/E, EV/EBITDA, P/B, Debt/Equity)
 * Always max 2 decimal places (e.g. 51.69x, never 51.69045x).
 */
export function formatMultiple(value: number | string | null | undefined): string {
  if (value === null || value === undefined || value === '') return '—';
  const num = typeof value === 'number' ? value : parseFloat(value);
  if (isNaN(num)) return '—';
  return `${num.toFixed(2)}x`;
}

/**
 * Formats Percentages (OPM %, ROE, Margin, Growth)
 * Always max 2 decimal places (e.g. 15.78%, +5.20%).
 */
export function formatPercent(
  value: number | string | null | undefined,
  options?: { isDecimal?: boolean; showSign?: boolean }
): string {
  if (value === null || value === undefined || value === '') return '—';
  let num = typeof value === 'number' ? value : parseFloat(value);
  if (isNaN(num)) return '—';

  // If passed as decimal ratio (e.g. 0.1578 for 15.78%)
  if (options?.isDecimal || (Math.abs(num) <= 1 && num !== 0)) {
    num = num * 100;
  }

  const sign = options?.showSign && num > 0 ? '+' : '';
  return `${sign}${num.toFixed(2)}%`;
}
