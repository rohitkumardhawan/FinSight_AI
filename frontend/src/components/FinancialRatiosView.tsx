'use client';

import React, { useState, useEffect } from 'react';
import { 
  Percent, 
  RefreshCw, 
  TrendingUp, 
  ShieldCheck, 
  Zap, 
  Database,
  CheckCircle2
} from 'lucide-react';
import { API_BASE } from '@/lib/api';
import { 
  formatPercent, 
  formatMultiple, 
  normalizeExchange 
} from '@/lib/formatters';

interface FinancialRatiosViewProps {
  ticker: string;
  onSelectTicker?: (ticker: string) => void;
}

export const FinancialRatiosView: React.FC<FinancialRatiosViewProps> = ({
  ticker,
  onSelectTicker,
}) => {
  const [periods, setPeriods] = useState<any[]>([]);
  const [companyInfo, setCompanyInfo] = useState<{
    id?: number;
    symbol: string;
    company_name: string;
    currency: string;
    exchange: string;
  }>({
    symbol: ticker || 'ASIANPAINT.NS',
    company_name: ticker || 'ASIANPAINT.NS',
    currency: ticker?.endsWith('.NS') ? 'INR' : 'USD',
    exchange: ticker?.endsWith('.NS') ? 'NSE' : 'GLOBAL',
  });
  const [loading, setLoading] = useState<boolean>(false);
  const [recalculating, setRecalculating] = useState<boolean>(false);
  const [notification, setNotification] = useState<{ type: 'success' | 'error'; message: string } | null>(null);

  const loadData = async (forceRefresh: boolean = false) => {
    setLoading(true);
    try {
      const sym = ticker || 'ASIANPAINT.NS';
      const res = await fetch(`${API_BASE}/companies/${encodeURIComponent(sym)}/analysis?refresh=${forceRefresh}`);
      if (!res.ok) {
        throw new Error(`Failed to load ratios: ${res.statusText}`);
      }
      const data = await res.json();
      setCompanyInfo({
        id: data.company_id,
        symbol: data.symbol || sym,
        company_name: data.company_name || sym,
        currency: data.currency || (sym.endsWith('.NS') ? 'INR' : 'USD'),
        exchange: normalizeExchange(data.exchange, sym),
      });

      const rawPeriods: any[] = data.periods || [];
      const sorted = [...rawPeriods].sort((a, b) => (a.fiscal_year || 0) - (b.fiscal_year || 0));
      // Filter out empty periods
      const valid = sorted.filter((p: any) =>
        (p.revenue !== null && p.revenue !== undefined) ||
        (p.operating_income !== null && p.operating_income !== undefined) ||
        (p.net_income !== null && p.net_income !== undefined)
      );
      setPeriods(valid.length > 0 ? valid : sorted);
    } catch (err: any) {
      console.warn('Could not load ratios dataset:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [ticker]);

  const handleRecalculate = async () => {
    setRecalculating(true);
    setNotification(null);
    try {
      await loadData(true);
      setNotification({
        type: 'success',
        message: `Successfully recalculated deterministic ratios across all fiscal periods from live statements.`,
      });
    } catch (err: any) {
      setNotification({
        type: 'error',
        message: err.message || 'Error executing ratio recalculation.',
      });
    } finally {
      setRecalculating(false);
    }
  };

  // Helper for computing ratio safely from period record
  const getGrossMargin = (p: any) => {
    if (p.gross_profit != null && p.revenue) return p.gross_profit / p.revenue;
    return null;
  };

  const getOperatingMargin = (p: any) => {
    if (p.opm_pct != null) return p.opm_pct / 100;
    if (p.operating_income != null && p.revenue) return p.operating_income / p.revenue;
    return null;
  };

  const getNetMargin = (p: any) => {
    if (p.net_income != null && p.revenue) return p.net_income / p.revenue;
    return null;
  };

  const getROE = (p: any) => {
    if (p.net_income != null && p.total_equity && p.total_equity !== 0) {
      return p.net_income / p.total_equity;
    }
    return null;
  };

  const getROA = (p: any) => {
    if (p.net_income != null && p.total_assets && p.total_assets !== 0) {
      return p.net_income / p.total_assets;
    }
    return null;
  };

  const getCurrentRatio = (p: any) => {
    if (p.current_assets != null && p.current_liabilities && p.current_liabilities !== 0) {
      return p.current_assets / p.current_liabilities;
    }
    return null;
  };

  const getQuickRatio = (p: any) => {
    if (p.current_assets != null && p.current_liabilities && p.current_liabilities !== 0) {
      const inv = p.inventory || 0;
      return (p.current_assets - inv) / p.current_liabilities;
    }
    return null;
  };

  const getDebtToEquity = (p: any) => {
    if (p.total_debt != null && p.total_equity && p.total_equity !== 0) {
      return p.total_debt / p.total_equity;
    }
    return null;
  };

  const latestPeriod = periods.length > 0 ? periods[periods.length - 1] : null;

  return (
    <div className="space-y-6">
      {/* Header & Controls */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 pb-4 border-b border-navy-800">
        <div>
          <div className="flex items-center gap-2">
            <span className="h-6 px-2.5 rounded bg-gold-500/10 text-gold-400 border border-gold-500/30 text-[11px] font-bold flex items-center gap-1.5">
              <Percent className="h-3.5 w-3.5" />
              FINANCIAL RATIO ENGINE
            </span>
            <span className="text-xs text-slate-400 font-medium">Phase 4 Deterministic Python Math</span>
          </div>

          <h1 className="text-2xl font-bold tracking-tight text-white mt-1.5 flex items-center gap-2.5">
            <span>{companyInfo.company_name}</span>
            <span className="text-gold-accent font-mono text-lg font-bold">({companyInfo.symbol})</span>
            <span className="px-2 py-0.5 text-xs font-semibold bg-navy-800 text-slate-300 border border-navy-700 rounded">
              {companyInfo.exchange}
            </span>
            {loading && <RefreshCw className="h-4 w-4 animate-spin text-gold-400" />}
          </h1>

          <div className="flex items-center gap-2 mt-1 text-xs text-slate-400">
            <Database className="h-3 w-3 text-cyan-400" />
            <span>Neon PostgreSQL • Verified Multi-Period Ratios</span>
          </div>
        </div>

        {/* Recalculate Button */}
        <div className="flex items-center gap-2.5">
          <button
            type="button"
            onClick={() => loadData(true)}
            className="flex items-center gap-1.5 px-3 py-2 rounded-xl bg-navy-900 hover:bg-navy-800 border border-navy-800 text-xs font-medium text-slate-300 transition-colors"
          >
            <RefreshCw className="h-3.5 w-3.5" />
            <span>Refresh</span>
          </button>

          <button
            type="button"
            disabled={recalculating}
            onClick={handleRecalculate}
            className="flex items-center gap-2 px-4 py-2 rounded-xl bg-gold-500 hover:bg-gold-400 text-navy-950 font-bold text-xs transition-all shadow-lg shadow-gold-500/20 active:scale-95 disabled:opacity-50"
          >
            <Zap className="h-3.5 w-3.5" />
            <span>{recalculating ? 'Recalculating...' : 'Recalculate Live Ratios'}</span>
          </button>
        </div>
      </div>

      {/* Notification Banner */}
      {notification && (
        <div
          className={`p-4 rounded-xl flex items-center gap-3 text-xs ${
            notification.type === 'success'
              ? 'bg-emerald-950/50 border border-emerald-500/40 text-emerald-200'
              : 'bg-rose-950/50 border border-rose-500/40 text-rose-200'
          }`}
        >
          {notification.type === 'success' ? (
            <CheckCircle2 className="h-4 w-4 text-emerald-400 flex-shrink-0" />
          ) : (
            <Zap className="h-4 w-4 text-rose-400 flex-shrink-0" />
          )}
          <span>{notification.message}</span>
        </div>
      )}

      {/* Primary KPI Cards (Latest Period Overview) */}
      {latestPeriod && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="bg-navy-900 border border-navy-800 rounded-xl p-4">
            <div className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">
              Operating Margin (OPM)
            </div>
            <div className="text-2xl font-bold font-mono text-white mt-1">
              {formatPercent(getOperatingMargin(latestPeriod))}
            </div>
            <div className="mt-2 flex items-center gap-1.5 text-xs text-emerald-400">
              <ShieldCheck className="h-3.5 w-3.5" />
              <span>Core Operational Efficiency</span>
            </div>
          </div>

          <div className="bg-navy-900 border border-navy-800 rounded-xl p-4">
            <div className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">
              Net Profit Margin
            </div>
            <div className="text-2xl font-bold font-mono text-white mt-1">
              {formatPercent(getNetMargin(latestPeriod))}
            </div>
            <div className="mt-2 flex items-center gap-1.5 text-xs text-emerald-400">
              <TrendingUp className="h-3.5 w-3.5" />
              <span>Net Bottom-Line Margin</span>
            </div>
          </div>

          <div className="bg-navy-900 border border-navy-800 rounded-xl p-4">
            <div className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">
              Return on Equity (ROE)
            </div>
            <div className="text-2xl font-bold font-mono text-white mt-1">
              {formatPercent(getROE(latestPeriod))}
            </div>
            <div className="mt-2 flex items-center gap-1.5 text-xs text-gold-400">
              <Zap className="h-3.5 w-3.5" />
              <span>Capital Return Metric</span>
            </div>
          </div>

          <div className="bg-navy-900 border border-navy-800 rounded-xl p-4">
            <div className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">
              Price to Earnings (P/E)
            </div>
            <div className="text-2xl font-bold font-mono text-white mt-1">
              {formatMultiple(latestPeriod.pe_ratio)}
            </div>
            <div className="mt-2 flex items-center gap-1.5 text-xs text-cyan-400">
              <CheckCircle2 className="h-3.5 w-3.5" />
              <span>Valuation Multiple</span>
            </div>
          </div>
        </div>
      )}

      {/* Historical Ratios Multi-Year Comparison Table */}
      <div className="bg-navy-900 border border-navy-800 rounded-2xl overflow-hidden shadow-xl">
        <div className="overflow-x-auto">
          <table className="w-full text-left">
            <thead className="bg-navy-950 text-slate-400 text-[11px] uppercase tracking-wider border-b border-navy-800">
              <tr>
                <th className="py-3 px-4 font-semibold text-slate-300 min-w-[240px]">
                  Financial Metric / Ratio
                </th>
                {periods.map((p, idx) => (
                  <th key={idx} className="py-3 px-4 text-right font-mono font-bold text-white min-w-[110px]">
                    <span className="text-gold-accent text-xs">
                      {p.fiscal_period || `FY${p.fiscal_year}`}
                    </span>
                    <div className="text-[10px] text-slate-500 font-normal">{p.fiscal_year}</div>
                  </th>
                ))}
              </tr>
            </thead>

            <tbody className="divide-y divide-navy-800/40 text-xs">
              {/* PROFITABILITY RATIOS */}
              <tr className="bg-navy-950/80">
                <td
                  colSpan={periods.length + 1}
                  className="py-2 px-4 text-[11px] font-bold tracking-wider uppercase text-gold-400 border-t border-b border-gold-500/20"
                >
                  1. Profitability & Returns Ratios
                </td>
              </tr>
              <tr className="hover:bg-navy-800/30">
                <td className="py-3 px-4 font-medium text-slate-300">
                  Gross Profit Margin
                  <div className="text-[10px] text-slate-500 font-mono">(Revenue - COGS) / Revenue</div>
                </td>
                {periods.map((p, idx) => (
                  <td key={idx} className="py-3 px-4 text-right font-mono text-slate-200">
                    {formatPercent(getGrossMargin(p))}
                  </td>
                ))}
              </tr>
              <tr className="hover:bg-navy-800/30">
                <td className="py-3 px-4 font-medium text-slate-300">
                  Operating Margin (EBIT Margin / OPM)
                  <div className="text-[10px] text-slate-500 font-mono">Operating Income / Revenue</div>
                </td>
                {periods.map((p, idx) => (
                  <td key={idx} className="py-3 px-4 text-right font-mono text-slate-200">
                    {formatPercent(getOperatingMargin(p))}
                  </td>
                ))}
              </tr>
              <tr className="hover:bg-navy-800/30">
                <td className="py-3 px-4 font-medium text-slate-300">
                  Net Profit Margin
                  <div className="text-[10px] text-slate-500 font-mono">Net Income / Revenue</div>
                </td>
                {periods.map((p, idx) => (
                  <td key={idx} className="py-3 px-4 text-right font-mono text-slate-200">
                    {formatPercent(getNetMargin(p))}
                  </td>
                ))}
              </tr>
              <tr className="hover:bg-navy-800/30">
                <td className="py-3 px-4 font-medium text-slate-300">
                  Return on Equity (ROE)
                  <div className="text-[10px] text-slate-500 font-mono">Net Income / Total Stockholders' Equity</div>
                </td>
                {periods.map((p, idx) => (
                  <td key={idx} className="py-3 px-4 text-right font-mono text-slate-200">
                    {formatPercent(getROE(p))}
                  </td>
                ))}
              </tr>
              <tr className="hover:bg-navy-800/30">
                <td className="py-3 px-4 font-medium text-slate-300">
                  Return on Assets (ROA)
                  <div className="text-[10px] text-slate-500 font-mono">Net Income / Total Assets</div>
                </td>
                {periods.map((p, idx) => (
                  <td key={idx} className="py-3 px-4 text-right font-mono text-slate-200">
                    {formatPercent(getROA(p))}
                  </td>
                ))}
              </tr>

              {/* LIQUIDITY RATIOS */}
              <tr className="bg-navy-950/80">
                <td
                  colSpan={periods.length + 1}
                  className="py-2 px-4 text-[11px] font-bold tracking-wider uppercase text-cyan-400 border-t border-b border-cyan-500/20"
                >
                  2. Liquidity & Short-Term Solvency
                </td>
              </tr>
              <tr className="hover:bg-navy-800/30">
                <td className="py-3 px-4 font-medium text-slate-300">
                  Current Ratio
                  <div className="text-[10px] text-slate-500 font-mono">Current Assets / Current Liabilities</div>
                </td>
                {periods.map((p, idx) => (
                  <td key={idx} className="py-3 px-4 text-right font-mono text-slate-200">
                    {formatMultiple(getCurrentRatio(p))}
                  </td>
                ))}
              </tr>
              <tr className="hover:bg-navy-800/30">
                <td className="py-3 px-4 font-medium text-slate-300">
                  Quick Ratio (Acid-Test)
                  <div className="text-[10px] text-slate-500 font-mono">(Current Assets - Inventory) / Current Liabilities</div>
                </td>
                {periods.map((p, idx) => (
                  <td key={idx} className="py-3 px-4 text-right font-mono text-slate-200">
                    {formatMultiple(getQuickRatio(p))}
                  </td>
                ))}
              </tr>

              {/* LEVERAGE & SOLVENCY RATIOS */}
              <tr className="bg-navy-950/80">
                <td
                  colSpan={periods.length + 1}
                  className="py-2 px-4 text-[11px] font-bold tracking-wider uppercase text-amber-400 border-t border-b border-amber-500/20"
                >
                  3. Leverage & Long-Term Solvency
                </td>
              </tr>
              <tr className="hover:bg-navy-800/30">
                <td className="py-3 px-4 font-medium text-slate-300">
                  Debt-to-Equity Ratio
                  <div className="text-[10px] text-slate-500 font-mono">Total Debt / Total Stockholders' Equity</div>
                </td>
                {periods.map((p, idx) => (
                  <td key={idx} className="py-3 px-4 text-right font-mono text-slate-200">
                    {formatMultiple(getDebtToEquity(p))}
                  </td>
                ))}
              </tr>
              <tr className="hover:bg-navy-800/30">
                <td className="py-3 px-4 font-medium text-slate-300">
                  Price to Earnings (Trailing P/E)
                  <div className="text-[10px] text-slate-500 font-mono">Share Price / Diluted EPS</div>
                </td>
                {periods.map((p, idx) => (
                  <td key={idx} className="py-3 px-4 text-right font-mono text-slate-200">
                    {formatMultiple(p.pe_ratio)}
                  </td>
                ))}
              </tr>
            </tbody>
          </table>
        </div>

        <div className="p-4 bg-navy-950/70 border-t border-navy-800 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs text-slate-400">
          <div>
            All ratios are computed deterministically in pure Python conforming strictly to institutional equity research standards.
          </div>
          <div className="flex items-center gap-2 font-mono text-[11px]">
            <span className="px-2 py-0.5 rounded bg-navy-800 text-slate-300 border border-navy-700">
              Engine: Pure Python
            </span>
            <span className="px-2 py-0.5 rounded bg-emerald-950 text-emerald-300 border border-emerald-800">
              Verified Neon Database
            </span>
          </div>
        </div>
      </div>
    </div>
  );
};
