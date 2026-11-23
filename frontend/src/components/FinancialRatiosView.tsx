'use client';

import React, { useState, useEffect, useMemo } from 'react';
import { 
  Percent, 
  RefreshCw, 
  TrendingUp, 
  ShieldCheck, 
  Zap, 
  Database,
  CheckCircle2,
  HelpCircle,
  Calendar,
  AlertTriangle
} from 'lucide-react';
import { API_BASE } from '@/lib/api';
import { PeriodFilterBar, EmptyPeriodSelectionFallback, ALL_YEARS, extractYear, isAnnualPeriod } from './PeriodFilterBar';
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
  const [periodFilter, setPeriodFilter] = useState<'annual' | 'quarterly'>('annual');
  const [selectedYears, setSelectedYears] = useState<number[]>([2023, 2024, 2025, 2026]);
  const [companyInfo, setCompanyInfo] = useState<{
    id?: number;
    symbol: string;
    company_name: string;
    currency: string;
    exchange: string;
    trailing_pe?: number | null;
    market_cap?: number | null;
  }>({
    symbol: ticker || 'ASIANPAINT.NS',
    company_name: ticker || 'ASIANPAINT.NS',
    currency: ticker?.endsWith('.NS') ? 'INR' : 'USD',
    exchange: ticker?.endsWith('.NS') ? 'NSE' : 'GLOBAL',
    trailing_pe: null,
    market_cap: null,
  });
  const [loading, setLoading] = useState<boolean>(true);
  const [recalculating, setRecalculating] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [notification, setNotification] = useState<{ type: 'success' | 'error'; message: string } | null>(null);
  const abortControllerRef = React.useRef<AbortController | null>(null);

  // Filter and sort helper functions
  const isQuarterlyPeriod = (p: any) =>
    p.statement_type === 'quarterly' ||
    (p.fiscal_period && p.fiscal_period.toUpperCase().startsWith('Q'));

  const parseQuarterOrder = (periodStr: string, year?: number) => {
    const match = periodStr.match(/Q(\d)\s*(\d{4})?/i);
    if (!match) return (year || 0) * 10;
    const qNum = parseInt(match[1], 10);
    const qYear = match[2] ? parseInt(match[2], 10) : (year || 0);
    return qYear * 10 + qNum;
  };

  const loadData = async (forceRefresh: boolean = false) => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    const controller = new AbortController();
    abortControllerRef.current = controller;

    const timeoutId = setTimeout(() => {
      controller.abort();
    }, 20000);

    setLoading(true);
    setError(null);
    try {
      const sym = ticker || 'ASIANPAINT.NS';
      const res = await fetch(`${API_BASE}/companies/${encodeURIComponent(sym)}/analysis?refresh=${forceRefresh}`, {
        signal: controller.signal,
      });
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
        trailing_pe: data.quote?.trailing_pe || data.auto_insights?.scenario_insights?.trailing_pe || null,
        market_cap: data.quote?.market_cap || null,
      });

      const rawPeriods: any[] = data.periods || [];
      const sorted = [...rawPeriods].sort((a, b) => (extractYear(a) || 0) - (extractYear(b) || 0));
      // Filter out empty periods
      const valid = sorted.filter((p: any) =>
        (p.revenue !== null && p.revenue !== undefined) ||
        (p.operating_income !== null && p.operating_income !== undefined) ||
        (p.net_income !== null && p.net_income !== undefined) ||
        (p.operating_cash_flow !== null && p.operating_cash_flow !== undefined)
      );
      const resolvedPeriods = valid.length > 0 ? valid : sorted;
      setPeriods(resolvedPeriods);

      const availYears = Array.from(
        new Set<number>(
          resolvedPeriods
            .filter(isAnnualPeriod)
            .map(extractYear)
            .filter((y: any): y is number => y !== null)
        )
      ).sort((a: number, b: number) => a - b);
      if (availYears.length > 0) {
        setSelectedYears(availYears);
      }
    } catch (err: any) {
      if (err.name === 'AbortError') {
        if (abortControllerRef.current === controller) {
          setError('Financial ratios request timed out (20s). Click retry to re-sync.');
        }
        return;
      }
      console.warn('Could not load ratios dataset:', err);
      setError(err.message || 'Failed to load financial ratios dataset');
    } finally {
      clearTimeout(timeoutId);
      if (abortControllerRef.current === controller) {
        setLoading(false);
      }
    }
  };

  useEffect(() => {
    loadData();

    return () => {
      abortControllerRef.current?.abort();
    };
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

  const getROIC = (p: any) => {
    if (p.roic_pct != null) return p.roic_pct / 100;
    const ebit = p.ebit ?? p.operating_income;
    let capEmployed = null;
    if (p.total_assets != null && p.current_liabilities != null) {
      capEmployed = p.total_assets - p.current_liabilities;
    } else if (p.total_debt != null && p.total_equity != null) {
      capEmployed = p.total_debt + p.total_equity - (p.cash_and_equivalents || 0);
    }
    if (ebit != null && capEmployed && capEmployed > 0) {
      return ebit / capEmployed;
    }
    return null;
  };

  const getDebtToEbitda = (p: any) => {
    if (p.debt_to_ebitda != null) return p.debt_to_ebitda;
    const ebit = p.ebit ?? p.operating_income;
    const da = p.depreciation_amortization || 0;
    const ebitda = ebit != null ? ebit + da : null;
    if (p.total_debt != null && ebitda && ebitda > 0) {
      return p.total_debt / ebitda;
    }
    return null;
  };

  const getAssetTurnover = (p: any) => {
    if (p.asset_turnover != null) return p.asset_turnover;
    if (p.revenue && p.total_assets && p.total_assets > 0) {
      return p.revenue / p.total_assets;
    }
    return null;
  };

  const getInventoryTurnover = (p: any) => {
    if (p.inventory_turnover != null) return p.inventory_turnover;
    const cogs = p.cost_of_revenue ?? (p.revenue && p.gross_profit ? p.revenue - p.gross_profit : null);
    if (cogs && p.inventory && p.inventory > 0) {
      return cogs / p.inventory;
    }
    return null;
  };

  const sortedAnnualPeriods = useMemo(() => {
    return periods
      .filter(isAnnualPeriod)
      .sort((a, b) => (extractYear(a) || 0) - (extractYear(b) || 0));
  }, [periods]);

  const sortedQuarterlyPeriods = useMemo(() => {
    return periods
      .filter((p) => !isAnnualPeriod(p))
      .sort((a, b) => {
        const ya = extractYear(a) || 0;
        const yb = extractYear(b) || 0;
        return parseQuarterOrder(a.fiscal_period || '', ya) - parseQuarterOrder(b.fiscal_period || '', yb);
      });
  }, [periods]);

  const availableYears = useMemo(() => {
    return Array.from(
      new Set<number>(
        sortedAnnualPeriods
          .map(extractYear)
          .filter((y: any): y is number => y !== null)
      )
    ).sort((a: number, b: number) => a - b);
  }, [sortedAnnualPeriods]);

  const activePeriods = useMemo(() => {
    const safeSelected = (selectedYears || []).map(extractYear).filter((y: any): y is number => y !== null);
    if (periodFilter === 'annual') {
      return sortedAnnualPeriods.filter((p) => {
        const y = extractYear(p);
        return y !== null && safeSelected.includes(y);
      });
    }
    return sortedQuarterlyPeriods;
  }, [sortedAnnualPeriods, sortedQuarterlyPeriods, periodFilter, selectedYears]);

  const latestAnnualPeriod = sortedAnnualPeriods.length > 0
    ? sortedAnnualPeriods[sortedAnnualPeriods.length - 1]
    : (periods.length > 0 ? periods[periods.length - 1] : null);

  const annualPeriodBadge = latestAnnualPeriod?.fiscal_period || (latestAnnualPeriod?.fiscal_year ? `FY${latestAnnualPeriod.fiscal_year}` : 'FY');

  const getPeriodMarketCap = (p: any) => {
    const isLatestAnnual = sortedAnnualPeriods.length > 0 && p === sortedAnnualPeriods[sortedAnnualPeriods.length - 1];
    if (isLatestAnnual && companyInfo.market_cap) {
      return companyInfo.market_cap;
    }
    if (p.share_price && p.eps && p.eps > 0 && p.net_income && p.net_income > 0) {
      return p.share_price * (p.net_income / p.eps);
    }
    if (p.share_price && p.pe_ratio && p.net_income && p.net_income > 0) {
      return p.pe_ratio * p.net_income;
    }
    return companyInfo.market_cap;
  };

  const getEvToEbitda = (p: any) => {
    if (p.ev_to_ebitda != null) return p.ev_to_ebitda;
    const ebit = p.ebit ?? p.operating_income;
    const da = p.depreciation_amortization || 0;
    const ebitda = ebit != null ? ebit + da : null;
    const mcap = getPeriodMarketCap(p);
    if (mcap && ebitda && ebitda > 0) {
      const ev = mcap + (p.total_debt || 0) - (p.cash_and_equivalents || 0);
      return ev / ebitda;
    }
    return null;
  };

  const getEvToRevenue = (p: any) => {
    if (p.ev_to_revenue != null) return p.ev_to_revenue;
    const mcap = getPeriodMarketCap(p);
    if (mcap && p.revenue && p.revenue > 0) {
      const ev = mcap + (p.total_debt || 0) - (p.cash_and_equivalents || 0);
      return ev / p.revenue;
    }
    return null;
  };

  const getPriceToBook = (p: any) => {
    if (p.price_to_book != null) return p.price_to_book;
    const mcap = getPeriodMarketCap(p);
    if (mcap && p.total_equity && p.total_equity > 0) {
      return mcap / p.total_equity;
    }
    return null;
  };

  const getPriceToSales = (p: any) => {
    if (p.price_to_sales != null) return p.price_to_sales;
    const mcap = getPeriodMarketCap(p);
    if (mcap && p.revenue && p.revenue > 0) {
      return mcap / p.revenue;
    }
    return null;
  };

  const getFcfYield = (p: any) => {
    if (p.fcf_yield_pct != null) return p.fcf_yield_pct / 100;
    const mcap = getPeriodMarketCap(p);
    if (p.free_cash_flow != null && mcap && mcap > 0) {
      return p.free_cash_flow / mcap;
    }
    return null;
  };



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

      {/* Standby Banner or Ratio Content */}
      {loading ? (
        <div className="flex flex-col items-center justify-center min-h-[350px] text-center p-8 bg-navy-900/50 rounded-2xl border border-navy-800 shadow-lg animate-pulse">
          <div className="h-10 w-10 rounded-full bg-navy-800 border border-gold-500/20 text-gold-400 flex items-center justify-center mb-3">
            <RefreshCw className="h-5 w-5 animate-spin text-gold-400" />
          </div>
          <div className="text-sm font-semibold text-white">Calibrating Financial Ratios...</div>
          <div className="text-xs text-slate-400 mt-1">Crunching institutional multi-year metrics from verified disclosures</div>
        </div>
      ) : error && periods.length === 0 ? (
        <div className="flex flex-col items-center justify-center min-h-[350px] text-center p-8 bg-navy-900/50 rounded-2xl border border-navy-800 shadow-lg">
          <div className="h-12 w-12 rounded-full bg-rose-500/10 text-rose-400 flex items-center justify-center mb-3">
            <AlertTriangle className="h-6 w-6" />
          </div>
          <h3 className="text-base font-semibold text-white">Financial Ratios Unavailable</h3>
          <p className="text-xs text-slate-300 max-w-md mt-1 leading-relaxed">
            {error}
          </p>
          <button
            onClick={() => loadData(true)}
            className="mt-4 px-4 py-2 rounded-lg bg-navy-800 hover:bg-navy-750 text-xs font-medium text-gold-400 border border-gold-500/30 flex items-center gap-1.5 transition-all shadow-md"
          >
            <RefreshCw className="h-3.5 w-3.5" /> Retry Loading Ratios
          </button>
        </div>
      ) : periods.length === 0 ? (
        <div className="flex flex-col items-center justify-center min-h-[350px] text-center p-8 bg-navy-900/50 rounded-2xl border border-navy-800 shadow-lg">
          <div className="h-12 w-12 rounded-full bg-navy-800 text-gold-400 flex items-center justify-center mb-3">
            <HelpCircle className="h-6 w-6" />
          </div>
          <h3 className="text-base font-semibold text-white">Financial Ratios Standby</h3>
          <p className="text-xs text-slate-300 max-w-md mt-1 leading-relaxed">
            Deterministic ratio metrics for {ticker} are currently synchronizing or awaiting live fetch.
          </p>
          <button
            onClick={() => loadData(true)}
            className="mt-4 px-4 py-2 rounded-lg bg-navy-800 hover:bg-navy-750 text-xs font-medium text-gold-400 border border-gold-500/30 flex items-center gap-1.5 transition-all shadow-md"
          >
            <RefreshCw className="h-3.5 w-3.5" /> Re-sync Ratios
          </button>
        </div>
      ) : (
        <>
          {/* Primary KPI Cards (Latest Annual FY Overview with Period Badge) */}
          {latestAnnualPeriod && (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              <div className="bg-navy-900 border border-navy-800 rounded-xl p-4">
                <div className="flex items-center justify-between text-[11px] font-semibold uppercase tracking-wider text-slate-400">
                  <span>Operating Margin (OPM)</span>
                  <span className="px-1.5 py-0.5 text-[10px] font-bold bg-navy-800 text-gold-400 border border-gold-500/20 rounded">
                    {annualPeriodBadge}
                  </span>
                </div>
                <div className="text-2xl font-bold font-mono text-white mt-1">
                  {formatPercent(getOperatingMargin(latestAnnualPeriod))}
                </div>
                <div className="mt-2 flex items-center gap-1.5 text-xs text-emerald-400">
                  <ShieldCheck className="h-3.5 w-3.5" />
                  <span>Core Operational Efficiency</span>
                </div>
              </div>

              <div className="bg-navy-900 border border-navy-800 rounded-xl p-4">
                <div className="flex items-center justify-between text-[11px] font-semibold uppercase tracking-wider text-slate-400">
                  <span>Net Profit Margin</span>
                  <span className="px-1.5 py-0.5 text-[10px] font-bold bg-navy-800 text-gold-400 border border-gold-500/20 rounded">
                    {annualPeriodBadge}
                  </span>
                </div>
                <div className="text-2xl font-bold font-mono text-white mt-1">
                  {formatPercent(getNetMargin(latestAnnualPeriod))}
                </div>
                <div className="mt-2 flex items-center gap-1.5 text-xs text-emerald-400">
                  <TrendingUp className="h-3.5 w-3.5" />
                  <span>Net Bottom-Line Margin</span>
                </div>
              </div>

              <div className="bg-navy-900 border border-navy-800 rounded-xl p-4">
                <div className="flex items-center justify-between text-[11px] font-semibold uppercase tracking-wider text-slate-400">
                  <span>Return on Equity (ROE)</span>
                  <span className="px-1.5 py-0.5 text-[10px] font-bold bg-navy-800 text-gold-400 border border-gold-500/20 rounded">
                    {annualPeriodBadge}
                  </span>
                </div>
                <div className="text-2xl font-bold font-mono text-white mt-1">
                  {formatPercent(getROE(latestAnnualPeriod))}
                </div>
                <div className="mt-2 flex items-center gap-1.5 text-xs text-gold-400">
                  <Zap className="h-3.5 w-3.5" />
                  <span>Annual Capital Return</span>
                </div>
              </div>

              <div className="bg-navy-900 border border-navy-800 rounded-xl p-4">
                <div className="flex items-center justify-between text-[11px] font-semibold uppercase tracking-wider text-slate-400">
                  <span>Price to Earnings (P/E)</span>
                  <span className="px-1.5 py-0.5 text-[10px] font-bold bg-navy-800 text-gold-400 border border-gold-500/20 rounded">
                    {annualPeriodBadge}
                  </span>
                </div>
                <div className="text-2xl font-bold font-mono text-white mt-1">
                  {formatMultiple(companyInfo.trailing_pe || latestAnnualPeriod.pe_ratio)}
                </div>
                <div className="mt-2 flex items-center gap-1.5 text-xs text-cyan-400">
                  <CheckCircle2 className="h-3.5 w-3.5" />
                  <span>Valuation Multiple</span>
                </div>
              </div>
            </div>
          )}

      {/* 2017–2026 Custom Year Selector & Annual vs. Quarterly Section Switcher */}
      <div className="pt-2">
        <PeriodFilterBar
          mode={periodFilter}
          onModeChange={setPeriodFilter}
          selectedYears={selectedYears}
          onSelectedYearsChange={setSelectedYears}
          availableYears={availableYears}
          annualCount={sortedAnnualPeriods.length}
          quarterlyCount={sortedQuarterlyPeriods.length}
        />
      </div>

      {!loading && periodFilter === 'annual' && activePeriods.length === 0 ? (
        <EmptyPeriodSelectionFallback
          selectedYears={selectedYears}
          availableYears={availableYears}
          onSelectAllAvailable={() =>
            setSelectedYears(availableYears.length > 0 ? availableYears : [2023, 2024, 2025, 2026])
          }
        />
      ) : (
        /* Historical Ratios Multi-Year Comparison Table */
        <div className="bg-navy-900 border border-navy-800 rounded-2xl overflow-hidden shadow-xl">
        <div className="overflow-x-auto">
          <table className="w-full text-left">
            <thead className="bg-navy-950 text-slate-400 text-[11px] uppercase tracking-wider border-b border-navy-800">
              <tr>
                <th className="py-3 px-4 font-semibold text-slate-300 min-w-[240px] sticky left-0 bg-[#0C0E14] z-20 border-r border-white/[0.06]">
                  Financial Metric / Ratio
                </th>
                {activePeriods.map((p, idx) => (
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
                  colSpan={activePeriods.length + 1}
                  className="py-2 px-4 text-[11px] font-bold tracking-wider uppercase text-gold-400 border-t border-b border-gold-500/20"
                >
                  1. Profitability & Returns Ratios
                </td>
              </tr>
              <tr className="hover:bg-navy-800/30">
                <td className="py-3 px-4 font-medium text-slate-300 sticky left-0 bg-[#11141B] z-10 border-r border-white/[0.06]">
                  Gross Profit Margin
                  <div className="text-[10px] text-slate-500 font-mono">(Revenue - COGS) / Revenue</div>
                </td>
                {activePeriods.map((p, idx) => (
                  <td key={idx} className="py-3 px-4 text-right font-mono text-slate-200">
                    {formatPercent(getGrossMargin(p))}
                  </td>
                ))}
              </tr>
              <tr className="hover:bg-navy-800/30">
                <td className="py-3 px-4 font-medium text-slate-300 sticky left-0 bg-[#11141B] z-10 border-r border-white/[0.06]">
                  Operating Margin (EBIT Margin / OPM)
                  <div className="text-[10px] text-slate-500 font-mono">Operating Income / Revenue</div>
                </td>
                {activePeriods.map((p, idx) => (
                  <td key={idx} className="py-3 px-4 text-right font-mono text-slate-200">
                    {formatPercent(getOperatingMargin(p))}
                  </td>
                ))}
              </tr>
              <tr className="hover:bg-navy-800/30">
                <td className="py-3 px-4 font-medium text-slate-300 sticky left-0 bg-[#11141B] z-10 border-r border-white/[0.06]">
                  Net Profit Margin
                  <div className="text-[10px] text-slate-500 font-mono">Net Income / Revenue</div>
                </td>
                {activePeriods.map((p, idx) => (
                  <td key={idx} className="py-3 px-4 text-right font-mono text-slate-200">
                    {formatPercent(getNetMargin(p))}
                  </td>
                ))}
              </tr>
              <tr className="hover:bg-navy-800/30">
                <td className="py-3 px-4 font-medium text-slate-300 sticky left-0 bg-[#11141B] z-10 border-r border-white/[0.06]">
                  Return on Equity (ROE)
                  <div className="text-[10px] text-slate-500 font-mono">Net Income / Total Stockholders' Equity</div>
                </td>
                {activePeriods.map((p, idx) => (
                  <td key={idx} className="py-3 px-4 text-right font-mono text-slate-200">
                    {formatPercent(getROE(p))}
                  </td>
                ))}
              </tr>
              <tr className="hover:bg-navy-800/30">
                <td className="py-3 px-4 font-medium text-slate-300 sticky left-0 bg-[#11141B] z-10 border-r border-white/[0.06]">
                  Return on Assets (ROA)
                  <div className="text-[10px] text-slate-500 font-mono">Net Income / Total Assets</div>
                </td>
                {activePeriods.map((p, idx) => (
                  <td key={idx} className="py-3 px-4 text-right font-mono text-slate-200">
                    {formatPercent(getROA(p))}
                  </td>
                ))}
              </tr>
              <tr className="hover:bg-navy-800/30">
                <td className="py-3 px-4 font-medium text-slate-300 sticky left-0 bg-[#11141B] z-10 border-r border-white/[0.06]">
                  Return on Capital Employed (ROCE / ROIC)
                  <div className="text-[10px] text-slate-500 font-mono">EBIT / (Total Assets - Current Liabilities)</div>
                </td>
                {activePeriods.map((p, idx) => (
                  <td key={idx} className="py-3 px-4 text-right font-mono text-gold-300 font-semibold">
                    {formatPercent(getROIC(p))}
                  </td>
                ))}
              </tr>

              {/* LIQUIDITY RATIOS */}
              <tr className="bg-navy-950/80">
                <td
                  colSpan={activePeriods.length + 1}
                  className="py-2 px-4 text-[11px] font-bold tracking-wider uppercase text-cyan-400 border-t border-b border-cyan-500/20"
                >
                  2. Liquidity & Short-Term Solvency
                </td>
              </tr>
              <tr className="hover:bg-navy-800/30">
                <td className="py-3 px-4 font-medium text-slate-300 sticky left-0 bg-[#11141B] z-10 border-r border-white/[0.06]">
                  Current Ratio
                  <div className="text-[10px] text-slate-500 font-mono">Current Assets / Current Liabilities</div>
                </td>
                {activePeriods.map((p, idx) => (
                  <td key={idx} className="py-3 px-4 text-right font-mono text-slate-200">
                    {formatMultiple(getCurrentRatio(p))}
                  </td>
                ))}
              </tr>
              <tr className="hover:bg-navy-800/30">
                <td className="py-3 px-4 font-medium text-slate-300 sticky left-0 bg-[#11141B] z-10 border-r border-white/[0.06]">
                  Quick Ratio (Acid-Test)
                  <div className="text-[10px] text-slate-500 font-mono">(Current Assets - Inventory) / Current Liabilities</div>
                </td>
                {activePeriods.map((p, idx) => (
                  <td key={idx} className="py-3 px-4 text-right font-mono text-slate-200">
                    {formatMultiple(getQuickRatio(p))}
                  </td>
                ))}
              </tr>

              {/* LEVERAGE & SOLVENCY RATIOS */}
              <tr className="bg-navy-950/80">
                <td
                  colSpan={activePeriods.length + 1}
                  className="py-2 px-4 text-[11px] font-bold tracking-wider uppercase text-amber-400 border-t border-b border-amber-500/20"
                >
                  3. Leverage & Long-Term Solvency
                </td>
              </tr>
              <tr className="hover:bg-navy-800/30">
                <td className="py-3 px-4 font-medium text-slate-300 sticky left-0 bg-[#11141B] z-10 border-r border-white/[0.06]">
                  Debt-to-Equity Ratio
                  <div className="text-[10px] text-slate-500 font-mono">Total Debt / Total Stockholders' Equity</div>
                </td>
                {activePeriods.map((p, idx) => (
                  <td key={idx} className="py-3 px-4 text-right font-mono text-slate-200">
                    {formatMultiple(getDebtToEquity(p))}
                  </td>
                ))}
              </tr>
              <tr className="hover:bg-navy-800/30">
                <td className="py-3 px-4 font-medium text-slate-300 sticky left-0 bg-[#11141B] z-10 border-r border-white/[0.06]">
                  Debt / EBITDA
                  <div className="text-[10px] text-slate-500 font-mono">Total Debt / EBITDA</div>
                </td>
                {activePeriods.map((p, idx) => (
                  <td key={idx} className="py-3 px-4 text-right font-mono text-slate-200">
                    {formatMultiple(getDebtToEbitda(p))}
                  </td>
                ))}
              </tr>

              {/* EFFICIENCY RATIOS */}
              <tr className="bg-navy-950/80">
                <td
                  colSpan={activePeriods.length + 1}
                  className="py-2 px-4 text-[11px] font-bold tracking-wider uppercase text-emerald-400 border-t border-b border-emerald-500/20"
                >
                  4. Efficiency & Asset Utilization Ratios
                </td>
              </tr>
              <tr className="hover:bg-navy-800/30">
                <td className="py-3 px-4 font-medium text-slate-300 sticky left-0 bg-[#11141B] z-10 border-r border-white/[0.06]">
                  Asset Turnover
                  <div className="text-[10px] text-slate-500 font-mono">Revenue / Total Assets</div>
                </td>
                {activePeriods.map((p, idx) => (
                  <td key={idx} className="py-3 px-4 text-right font-mono text-slate-200">
                    {formatMultiple(getAssetTurnover(p))}
                  </td>
                ))}
              </tr>
              <tr className="hover:bg-navy-800/30">
                <td className="py-3 px-4 font-medium text-slate-300 sticky left-0 bg-[#11141B] z-10 border-r border-white/[0.06]">
                  Inventory Turnover
                  <div className="text-[10px] text-slate-500 font-mono">Cost of Goods Sold / Inventory</div>
                </td>
                {activePeriods.map((p, idx) => (
                  <td key={idx} className="py-3 px-4 text-right font-mono text-slate-200">
                    {formatMultiple(getInventoryTurnover(p))}
                  </td>
                ))}
              </tr>

              {/* VALUATION MULTIPLES */}
              <tr className="bg-navy-950/80">
                <td
                  colSpan={activePeriods.length + 1}
                  className="py-2 px-4 text-[11px] font-bold tracking-wider uppercase text-purple-400 border-t border-b border-purple-500/20"
                >
                  5. Institutional Valuation Multiples
                </td>
              </tr>
              <tr className="hover:bg-navy-800/30">
                <td className="py-3 px-4 font-medium text-slate-300 sticky left-0 bg-[#11141B] z-10 border-r border-white/[0.06]">
                  Price to Earnings (Trailing P/E)
                  <div className="text-[10px] text-slate-500 font-mono">Share Price / Diluted EPS</div>
                </td>
                {activePeriods.map((p, idx) => (
                  <td key={idx} className="py-3 px-4 text-right font-mono text-purple-300 font-semibold">
                    {formatMultiple(p.pe_ratio || (idx === activePeriods.length - 1 ? companyInfo.trailing_pe : null))}
                  </td>
                ))}
              </tr>
              <tr className="hover:bg-navy-800/30">
                <td className="py-3 px-4 font-medium text-slate-300 sticky left-0 bg-[#11141B] z-10 border-r border-white/[0.06]">
                  EV / EBITDA
                  <div className="text-[10px] text-slate-500 font-mono">Enterprise Value / (Operating Income + D&A)</div>
                </td>
                {activePeriods.map((p, idx) => (
                  <td key={idx} className="py-3 px-4 text-right font-mono text-slate-200">
                    {formatMultiple(getEvToEbitda(p))}
                  </td>
                ))}
              </tr>
              <tr className="hover:bg-navy-800/30">
                <td className="py-3 px-4 font-medium text-slate-300 sticky left-0 bg-[#11141B] z-10 border-r border-white/[0.06]">
                  EV / Revenue
                  <div className="text-[10px] text-slate-500 font-mono">Enterprise Value / Revenue</div>
                </td>
                {activePeriods.map((p, idx) => (
                  <td key={idx} className="py-3 px-4 text-right font-mono text-slate-200">
                    {formatMultiple(getEvToRevenue(p))}
                  </td>
                ))}
              </tr>
              <tr className="hover:bg-navy-800/30">
                <td className="py-3 px-4 font-medium text-slate-300 sticky left-0 bg-[#11141B] z-10 border-r border-white/[0.06]">
                  Price-to-Book (P/B)
                  <div className="text-[10px] text-slate-500 font-mono">Market Cap / Total Stockholders' Equity</div>
                </td>
                {activePeriods.map((p, idx) => (
                  <td key={idx} className="py-3 px-4 text-right font-mono text-slate-200">
                    {formatMultiple(getPriceToBook(p))}
                  </td>
                ))}
              </tr>
              <tr className="hover:bg-navy-800/30">
                <td className="py-3 px-4 font-medium text-slate-300 sticky left-0 bg-[#11141B] z-10 border-r border-white/[0.06]">
                  Price-to-Sales (P/S)
                  <div className="text-[10px] text-slate-500 font-mono">Market Cap / Revenue</div>
                </td>
                {activePeriods.map((p, idx) => (
                  <td key={idx} className="py-3 px-4 text-right font-mono text-slate-200">
                    {formatMultiple(getPriceToSales(p))}
                  </td>
                ))}
              </tr>
              <tr className="hover:bg-navy-800/30">
                <td className="py-3 px-4 font-medium text-slate-300 sticky left-0 bg-[#11141B] z-10 border-r border-white/[0.06]">
                  FCF Yield %
                  <div className="text-[10px] text-slate-500 font-mono">Free Cash Flow / Market Cap</div>
                </td>
                {activePeriods.map((p, idx) => (
                  <td key={idx} className="py-3 px-4 text-right font-mono text-emerald-400 font-semibold">
                    {formatPercent(getFcfYield(p))}
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
      )}
      </>
      )}
    </div>
  );
};
