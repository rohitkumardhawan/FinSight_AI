'use client';

import React, { useState, useEffect } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import {
  ArrowLeftRight,
  TrendingUp,
  TrendingDown,
  Building2,
  RefreshCw,
  Search,
  ExternalLink,
  CheckCircle2,
  Scale,
  ShieldAlert,
  AlertTriangle,
  Calculator,
  HelpCircle
} from 'lucide-react';
import { API_BASE } from '@/lib/api';
import {
  formatFinancialValue,
  formatPerShare,
  formatMultiple,
  formatPercent,
  normalizeExchange
} from '@/lib/formatters';

interface CompanyCompareViewProps {
  initialA?: string;
  initialB?: string;
  onSelectTicker?: (ticker: string) => void;
}

interface CompanyMetricSummary {
  symbol: string;
  name: string;
  exchange: string;
  currency: string;
  price: number | null;
  marketCap: number | null;
  revenue: number | null;
  revenueGrowth: number | null;
  opm: number | null;
  netMargin: number | null;
  roe: number | null;
  pe: number | null;
  debtToEquity: number | null;
  dcfUpside: number | null;
  dcfIntrinsic: number | null;
}

export const CompanyCompareView: React.FC<CompanyCompareViewProps> = ({
  initialA = 'ASIANPAINT.NS',
  initialB = 'BERGEPAINT.NS',
  onSelectTicker,
}) => {
  const router = useRouter();
  const searchParams = useSearchParams();

  const paramA = searchParams?.get('a') || initialA;
  const paramB = searchParams?.get('b') || initialB;

  const [symbolA, setSymbolA] = useState<string>(paramA);
  const [symbolB, setSymbolB] = useState<string>(paramB);

  const [searchQueryA, setSearchQueryA] = useState<string>('');
  const [searchQueryB, setSearchQueryB] = useState<string>('');
  const [searchResultsA, setSearchResultsA] = useState<any[]>([]);
  const [searchResultsB, setSearchResultsB] = useState<any[]>([]);
  const [isSearchingA, setIsSearchingA] = useState<boolean>(false);
  const [isSearchingB, setIsSearchingB] = useState<boolean>(false);

  const [dataA, setDataA] = useState<CompanyMetricSummary | null>(null);
  const [dataB, setDataB] = useState<CompanyMetricSummary | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Search autocomplete for A
  useEffect(() => {
    let active = true;
    if (!searchQueryA.trim()) {
      setSearchResultsA([]);
      return;
    }
    const timer = setTimeout(async () => {
      setIsSearchingA(true);
      try {
        const res = await fetch(`${API_BASE}/companies/search?q=${encodeURIComponent(searchQueryA)}&limit=6`);
        if (res.ok && active) {
          const json = await res.json();
          setSearchResultsA(json.results || []);
        }
      } catch (err) {
        console.debug('Search A error:', err);
      } finally {
        if (active) setIsSearchingA(false);
      }
    }, 250);
    return () => {
      active = false;
      clearTimeout(timer);
    };
  }, [searchQueryA]);

  // Search autocomplete for B
  useEffect(() => {
    let active = true;
    if (!searchQueryB.trim()) {
      setSearchResultsB([]);
      return;
    }
    const timer = setTimeout(async () => {
      setIsSearchingB(true);
      try {
        const res = await fetch(`${API_BASE}/companies/search?q=${encodeURIComponent(searchQueryB)}&limit=6`);
        if (res.ok && active) {
          const json = await res.json();
          setSearchResultsB(json.results || []);
        }
      } catch (err) {
        console.debug('Search B error:', err);
      } finally {
        if (active) setIsSearchingB(false);
      }
    }, 250);
    return () => {
      active = false;
      clearTimeout(timer);
    };
  }, [searchQueryB]);

  // Helper to extract and normalize metrics from analysis + DCF payloads
  const fetchCompanyMetrics = async (sym: string): Promise<CompanyMetricSummary> => {
    const cleanSym = sym ? sym.trim().toUpperCase() : '';
    
    // Fetch analysis and DCF in parallel
    const [analysisRes, dcfRes] = await Promise.allSettled([
      fetch(`${API_BASE}/companies/${encodeURIComponent(cleanSym)}/analysis`),
      fetch(`${API_BASE}/companies/${encodeURIComponent(cleanSym)}/dcf`)
    ]);

    let analysis: any = {};
    if (analysisRes.status === 'fulfilled' && analysisRes.value.ok) {
      analysis = await analysisRes.value.json();
    }

    let dcf: any = {};
    if (dcfRes.status === 'fulfilled' && dcfRes.value.ok) {
      dcf = await dcfRes.value.json();
    }

    const periods: any[] = (analysis.periods || []).filter(
      (p: any) => p.statement_type !== 'quarterly' && (!p.fiscal_period || p.fiscal_period.toUpperCase().startsWith('FY'))
    );
    periods.sort((a, b) => (a.fiscal_year || 0) - (b.fiscal_year || 0));

    const latest = periods[periods.length - 1] || {};
    const prev = periods.length >= 2 ? periods[periods.length - 2] : null;

    const quote = analysis.quote || {};
    const price = quote.current_price || latest.share_price || null;
    const marketCap = quote.market_cap || null;
    const pe = quote.trailing_pe || latest.pe_ratio || null;

    const revenue = latest.revenue || null;
    let revenueGrowth: number | null = null;
    if (latest.revenue && prev && prev.revenue && prev.revenue > 0) {
      revenueGrowth = ((latest.revenue - prev.revenue) / Math.abs(prev.revenue)) * 100;
    }

    const opm = latest.opm_pct ?? (latest.operating_income && latest.revenue ? (latest.operating_income / latest.revenue) * 100 : null);
    const netMargin = latest.revenue && latest.net_income ? (latest.net_income / latest.revenue) * 100 : null;
    const roe = latest.total_equity && latest.net_income && latest.total_equity > 0 ? (latest.net_income / latest.total_equity) * 100 : null;

    let debtToEquity: number | null = null;
    if (latest.total_equity && latest.total_debt !== undefined && latest.total_equity > 0) {
      debtToEquity = latest.total_debt / latest.total_equity;
    }

    // DCF intrinsic upside
    let dcfIntrinsic: number | null = null;
    let dcfUpside: number | null = null;
    if (dcf?.base_case?.intrinsic_value_per_share) {
      dcfIntrinsic = Number(dcf.base_case.intrinsic_value_per_share);
    } else if (analysis.scenarios?.base_case_price) {
      dcfIntrinsic = Number(analysis.scenarios.base_case_price);
    }

    if (dcfIntrinsic !== null && !isNaN(dcfIntrinsic) && price && price > 0) {
      dcfUpside = ((dcfIntrinsic - price) / price) * 100;
    }

    return {
      symbol: cleanSym,
      name: analysis.company_name || cleanSym,
      exchange: normalizeExchange(analysis.exchange, cleanSym),
      currency: analysis.currency || (cleanSym.endsWith('.NS') ? 'INR' : 'USD'),
      price,
      marketCap,
      revenue,
      revenueGrowth,
      opm,
      netMargin,
      roe,
      pe,
      debtToEquity,
      dcfUpside,
      dcfIntrinsic
    };
  };

  const loadComparison = async () => {
    setLoading(true);
    setError(null);
    try {
      const [resA, resB] = await Promise.all([
        fetchCompanyMetrics(symbolA),
        fetchCompanyMetrics(symbolB)
      ]);
      setDataA(resA);
      setDataB(resB);
    } catch (err: any) {
      console.error('Comparison load error:', err);
      setError(err.message || 'Failed to load side-by-side comparison data.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadComparison();
  }, [symbolA, symbolB]);

  const handleSwap = () => {
    const temp = symbolA;
    setSymbolA(symbolB);
    setSymbolB(temp);
    router.push(`/compare?a=${encodeURIComponent(symbolB)}&b=${encodeURIComponent(temp)}`);
  };

  const handleSelectA = (sym: string) => {
    setSymbolA(sym);
    setSearchQueryA('');
    setSearchResultsA([]);
    router.push(`/compare?a=${encodeURIComponent(sym)}&b=${encodeURIComponent(symbolB)}`);
  };

  const handleSelectB = (sym: string) => {
    setSymbolB(sym);
    setSearchQueryB('');
    setSearchResultsB([]);
    router.push(`/compare?a=${encodeURIComponent(symbolA)}&b=${encodeURIComponent(sym)}`);
  };

  // Compare metric helper (returns 1 if A wins, -1 if B wins, 0 if tie/null)
  const getWinner = (
    valA?: number | null,
    valB?: number | null,
    isLowerBetter: boolean = false,
    isCurrency: boolean = false
  ): number => {
    if (valA === null || valA === undefined || valB === null || valB === undefined) return 0;
    if (isCurrency && dataA?.currency && dataB?.currency && dataA.currency.toUpperCase() !== dataB.currency.toUpperCase()) {
      return 0; // Cross-currency absolute values cannot be compared directly without FX normalization
    }
    if (valA === valB) return 0;
    if (isLowerBetter) {
      return valA < valB ? 1 : -1;
    }
    return valA > valB ? 1 : -1;
  };

  // Calculate score tally
  const metricsList = [
    { key: 'revenue', label: 'Annual Revenue', isLowerBetter: false, isCurrency: true },
    { key: 'revenueGrowth', label: 'YoY Revenue Growth', isLowerBetter: false, isPercent: true },
    { key: 'opm', label: 'Operating Margin (OPM)', isLowerBetter: false, isPercent: true },
    { key: 'netMargin', label: 'Net Profit Margin', isLowerBetter: false, isPercent: true },
    { key: 'roe', label: 'Return on Equity (ROE)', isLowerBetter: false, isPercent: true },
    { key: 'pe', label: 'P/E Multiple (Valuation)', isLowerBetter: true, isMultiple: true },
    { key: 'debtToEquity', label: 'Debt-to-Equity (Leverage)', isLowerBetter: true, isMultiple: true },
    { key: 'dcfUpside', label: 'DCF Intrinsic Upside', isLowerBetter: false, isPercent: true },
  ];

  let winsA = 0;
  let winsB = 0;
  if (dataA && dataB) {
    metricsList.forEach((m) => {
      const w = getWinner((dataA as any)[m.key], (dataB as any)[m.key], m.isLowerBetter, m.isCurrency);
      if (w === 1) winsA++;
      else if (w === -1) winsB++;
    });
  }

  return (
    <div className="space-y-6">
      {/* 1. TOP HEADER & EQUITIES SELECTOR */}
      <div className="bg-navy-900 border border-navy-800 rounded-2xl p-5 sm:p-6 shadow-xl relative overflow-hidden">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 pb-4 border-b border-navy-800">
          <div>
            <div className="flex items-center gap-2">
              <span className="h-6 px-2.5 rounded bg-gold-500/10 text-gold-400 border border-gold-500/30 text-[11px] font-bold flex items-center gap-1.5 uppercase tracking-wider">
                <Scale className="h-3.5 w-3.5" />
                Institutional Head-to-Head
              </span>
              <span className="text-xs text-slate-400 font-medium">Side-by-Side Equity Comparison</span>
            </div>
            <h1 className="text-2xl font-bold tracking-tight text-white mt-1.5 flex items-center gap-2.5">
              <span>{dataA?.name || symbolA}</span>
              <span className="text-slate-500 text-lg font-normal">vs</span>
              <span>{dataB?.name || symbolB}</span>
              {loading && <RefreshCw className="h-4 w-4 animate-spin text-gold-400" />}
            </h1>
          </div>

          <button
            type="button"
            onClick={loadComparison}
            disabled={loading}
            className="self-start lg:self-auto flex items-center gap-1.5 px-3 py-2 rounded-xl bg-navy-800 hover:bg-navy-750 border border-navy-700 text-xs font-semibold text-slate-300 hover:text-white transition-colors"
          >
            <RefreshCw className={`h-3.5 w-3.5 text-gold-400 ${loading ? 'animate-spin' : ''}`} />
            <span>Re-analyze</span>
          </button>
        </div>

        {/* Dynamic Selector Bar with Autocomplete */}
        <div className="grid grid-cols-1 md:grid-cols-11 gap-3 items-center mt-5">
          {/* Company A Search */}
          <div className="md:col-span-5 relative">
            <label className="text-[11px] text-slate-400 font-medium mb-1 block">
              Company A (Primary)
            </label>
            <div className="relative">
              <Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-500" />
              <input
                type="text"
                value={searchQueryA}
                onChange={(e) => setSearchQueryA(e.target.value)}
                placeholder={`Search or change (${symbolA})...`}
                className="w-full bg-navy-950 border border-navy-750 focus:border-gold-500/50 rounded-xl pl-9 pr-3 py-2 text-xs text-white placeholder-slate-500 focus:outline-none transition-colors"
              />
              {isSearchingA && (
                <RefreshCw className="absolute right-3 top-2.5 h-3.5 w-3.5 animate-spin text-gold-400" />
              )}
            </div>

            {/* Dropdown A */}
            {searchResultsA.length > 0 && (
              <div className="absolute left-0 right-0 top-full mt-1.5 bg-navy-950 border border-navy-700 rounded-xl shadow-2xl z-30 overflow-hidden divide-y divide-navy-800">
                {searchResultsA.map((item: any) => (
                  <button
                    key={item.symbol}
                    type="button"
                    onClick={() => handleSelectA(item.symbol)}
                    className="w-full text-left px-3.5 py-2 hover:bg-navy-850 flex items-center justify-between text-xs transition-colors"
                  >
                    <div>
                      <div className="font-semibold text-white">{item.company_name}</div>
                      <div className="text-[10px] text-gold-400 font-mono">{item.symbol}</div>
                    </div>
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-navy-800 text-slate-300">
                      {item.exchange || 'NSE'}
                    </span>
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Swap Button */}
          <div className="md:col-span-1 flex justify-center pt-5">
            <button
              type="button"
              onClick={handleSwap}
              className="p-2.5 rounded-xl bg-navy-950 hover:bg-navy-800 border border-navy-750 hover:border-gold-500/40 text-gold-400 transition-all shadow-sm active:scale-95"
              title="Swap Company A and B"
            >
              <ArrowLeftRight className="h-4 w-4" />
            </button>
          </div>

          {/* Company B Search */}
          <div className="md:col-span-5 relative">
            <label className="text-[11px] text-slate-400 font-medium mb-1 block">
              Company B (Benchmark)
            </label>
            <div className="relative">
              <Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-500" />
              <input
                type="text"
                value={searchQueryB}
                onChange={(e) => setSearchQueryB(e.target.value)}
                placeholder={`Search or change (${symbolB})...`}
                className="w-full bg-navy-950 border border-navy-750 focus:border-gold-500/50 rounded-xl pl-9 pr-3 py-2 text-xs text-white placeholder-slate-500 focus:outline-none transition-colors"
              />
              {isSearchingB && (
                <RefreshCw className="absolute right-3 top-2.5 h-3.5 w-3.5 animate-spin text-gold-400" />
              )}
            </div>

            {/* Dropdown B */}
            {searchResultsB.length > 0 && (
              <div className="absolute left-0 right-0 top-full mt-1.5 bg-navy-950 border border-navy-700 rounded-xl shadow-2xl z-30 overflow-hidden divide-y divide-navy-800">
                {searchResultsB.map((item: any) => (
                  <button
                    key={item.symbol}
                    type="button"
                    onClick={() => handleSelectB(item.symbol)}
                    className="w-full text-left px-3.5 py-2 hover:bg-navy-850 flex items-center justify-between text-xs transition-colors"
                  >
                    <div>
                      <div className="font-semibold text-white">{item.company_name}</div>
                      <div className="text-[10px] text-gold-400 font-mono">{item.symbol}</div>
                    </div>
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-navy-800 text-slate-300">
                      {item.exchange || 'NSE'}
                    </span>
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* 2. SUMMARY TALLY & HEAD-TO-HEAD CARDS */}
      {dataA && dataB && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {/* Card A */}
          <div className="bg-navy-900 border border-navy-800 rounded-2xl p-5 shadow-lg relative overflow-hidden">
            <div className="flex items-center justify-between">
              <div>
                <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-navy-950 text-gold-400 border border-navy-750">
                  {dataA.symbol}
                </span>
                <h3 className="text-lg font-bold text-white mt-1 truncate">{dataA.name}</h3>
                <div className="text-xs text-slate-400 font-mono mt-0.5">
                  {dataA.exchange} • {dataA.currency}
                </div>
              </div>

              <div className="text-right">
                <div className="text-xl font-bold font-mono text-white">
                  {formatPerShare(dataA.price, dataA.currency)}
                </div>
                <div className="text-xs text-slate-400 font-mono">
                  Cap: {formatFinancialValue(dataA.marketCap, dataA.currency)}
                </div>
              </div>
            </div>

            <div className="mt-4 pt-3 border-t border-navy-800 flex items-center justify-between text-xs">
              <span className="text-slate-400 font-medium">Head-to-Head Score:</span>
              <span className="font-bold text-gold-400 font-mono text-sm px-2.5 py-0.5 rounded bg-gold-500/10 border border-gold-500/20">
                {winsA} Categories Won
              </span>
            </div>
          </div>

          {/* Card B */}
          <div className="bg-navy-900 border border-navy-800 rounded-2xl p-5 shadow-lg relative overflow-hidden">
            <div className="flex items-center justify-between">
              <div>
                <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-navy-950 text-cyan-400 border border-navy-750">
                  {dataB.symbol}
                </span>
                <h3 className="text-lg font-bold text-white mt-1 truncate">{dataB.name}</h3>
                <div className="text-xs text-slate-400 font-mono mt-0.5">
                  {dataB.exchange} • {dataB.currency}
                </div>
              </div>

              <div className="text-right">
                <div className="text-xl font-bold font-mono text-white">
                  {formatPerShare(dataB.price, dataB.currency)}
                </div>
                <div className="text-xs text-slate-400 font-mono">
                  Cap: {formatFinancialValue(dataB.marketCap, dataB.currency)}
                </div>
              </div>
            </div>

            <div className="mt-4 pt-3 border-t border-navy-800 flex items-center justify-between text-xs">
              <span className="text-slate-400 font-medium">Head-to-Head Score:</span>
              <span className="font-bold text-cyan-400 font-mono text-sm px-2.5 py-0.5 rounded bg-cyan-500/10 border border-cyan-500/20">
                {winsB} Categories Won
              </span>
            </div>
          </div>
        </div>
      )}

      {/* Cross-Currency Warning Banner */}
      {dataA && dataB && dataA.currency && dataB.currency && dataA.currency.toUpperCase() !== dataB.currency.toUpperCase() && (
        <div className="bg-amber-500/10 border border-amber-500/30 rounded-2xl p-4 flex items-start gap-3 text-xs text-amber-200 shadow-md">
          <AlertTriangle className="h-4 w-4 text-amber-400 flex-shrink-0 mt-0.5" />
          <div className="space-y-1">
            <div className="font-semibold text-amber-300">
              Cross-Currency Comparison Notice ({dataA.currency} vs {dataB.currency})
            </div>
            <p className="text-slate-300 leading-relaxed text-[11px]">
              Absolute monetary metrics (such as <span className="font-semibold text-white">Annual Revenue</span> and <span className="font-semibold text-white">Market Cap</span>) are displayed in each company&apos;s native reporting currency ({dataA.currency} for {dataA.symbol}, {dataB.currency} for {dataB.symbol}). Financial percentage margins, growth rates, returns (OPM %, Net Margin %, ROE %), and valuation multiples (P/E, Debt-to-Equity) are fully normalized and directly comparable.
            </p>
          </div>
        </div>
      )}

      {/* 3. DETAILED METRIC COMPARISON TABLE & VISUAL BARS */}
      {dataA && dataB && (
        <div className="bg-navy-900 border border-navy-800 rounded-2xl shadow-xl overflow-hidden">
          <div className="p-4 sm:p-5 border-b border-navy-800 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Scale className="h-4 w-4 text-gold-400" />
              <h2 className="text-sm font-bold uppercase tracking-wider text-white">
                Core Financial & Valuation Comparison
              </h2>
            </div>
            <div className="text-[11px] text-slate-400 flex items-center gap-2 font-mono">
              <span className="text-gold-400 font-bold">{dataA.symbol}</span>
              <span>vs</span>
              <span className="text-cyan-400 font-bold">{dataB.symbol}</span>
            </div>
          </div>

          <div className="divide-y divide-navy-800/60">
            {metricsList.map((m) => {
              const valA = (dataA as any)[m.key];
              const valB = (dataB as any)[m.key];
              const winner = getWinner(valA, valB, m.isLowerBetter, m.isCurrency);

              // Format text
              const textA = m.isCurrency
                ? formatFinancialValue(valA, dataA.currency)
                : m.isPercent
                ? formatPercent(valA)
                : m.isMultiple
                ? formatMultiple(valA)
                : valA !== null && valA !== undefined
                ? String(valA)
                : '—';

              const textB = m.isCurrency
                ? formatFinancialValue(valB, dataB.currency)
                : m.isPercent
                ? formatPercent(valB)
                : m.isMultiple
                ? formatMultiple(valB)
                : valB !== null && valB !== undefined
                ? String(valB)
                : '—';

              // Visual bar ratios
              const numA = typeof valA === 'number' ? Math.abs(valA) : 0;
              const numB = typeof valB === 'number' ? Math.abs(valB) : 0;
              const maxNum = Math.max(numA, numB, 0.0001);
              const widthPctA = Math.max(12, Math.min(100, (numA / maxNum) * 100));
              const widthPctB = Math.max(12, Math.min(100, (numB / maxNum) * 100));

              return (
                <div key={m.key} className="p-4 hover:bg-navy-850/40 transition-colors">
                  <div className="flex items-center justify-between text-xs mb-2">
                    {/* Val A */}
                    <div className="flex items-center gap-2">
                      <span className={`font-mono font-bold text-sm ${winner === 1 ? 'text-gold-300' : 'text-slate-300'}`}>
                        {textA}
                      </span>
                      {winner === 1 && (
                        <span className="inline-flex items-center gap-0.5 text-[9px] font-bold px-1.5 py-0.2 rounded bg-gold-500/20 text-gold-300 uppercase">
                          <CheckCircle2 className="h-2.5 w-2.5" /> Leads
                        </span>
                      )}
                    </div>

                    {/* Metric Label */}
                    <div className="text-center font-medium text-slate-300 text-xs">
                      {m.label}
                    </div>

                    {/* Val B */}
                    <div className="flex items-center gap-2">
                      {winner === -1 && (
                        <span className="inline-flex items-center gap-0.5 text-[9px] font-bold px-1.5 py-0.2 rounded bg-cyan-500/20 text-cyan-300 uppercase">
                          <CheckCircle2 className="h-2.5 w-2.5" /> Leads
                        </span>
                      )}
                      <span className={`font-mono font-bold text-sm ${winner === -1 ? 'text-cyan-300' : 'text-slate-300'}`}>
                        {textB}
                      </span>
                    </div>
                  </div>

                  {/* Dual Proportional Bar Visualization */}
                  <div className="grid grid-cols-2 gap-2 mt-2">
                    {/* Bar A (fills from right to left) */}
                    <div className="flex justify-end bg-navy-950/60 rounded-full h-2.5 overflow-hidden p-0.5">
                      <div
                        className={`h-full rounded-full transition-all duration-500 ${
                          winner === 1 ? 'bg-gold-500 shadow-sm shadow-gold-500/40' : 'bg-slate-600'
                        }`}
                        style={{ width: `${widthPctA}%` }}
                      />
                    </div>

                    {/* Bar B (fills from left to right) */}
                    <div className="flex justify-start bg-navy-950/60 rounded-full h-2.5 overflow-hidden p-0.5">
                      <div
                        className={`h-full rounded-full transition-all duration-500 ${
                          winner === -1 ? 'bg-cyan-400 shadow-sm shadow-cyan-400/40' : 'bg-slate-600'
                        }`}
                        style={{ width: `${widthPctB}%` }}
                      />
                    </div>
                  </div>
                </div>
              );
            })}
          </div>

          {/* Quick Deep Dive Links */}
          <div className="p-4 bg-navy-950/80 border-t border-navy-800 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs">
            <button
              type="button"
              onClick={() => {
                if (onSelectTicker) onSelectTicker(dataA.symbol);
                else router.push(`/company/${encodeURIComponent(dataA.symbol)}?tab=company-analysis`);
              }}
              className="flex items-center gap-1.5 px-3 py-2 rounded-xl bg-navy-900 hover:bg-navy-850 border border-gold-500/30 text-gold-400 font-semibold transition-colors"
            >
              <span>Analyze {dataA.name} ({dataA.symbol})</span>
              <ExternalLink className="h-3.5 w-3.5" />
            </button>

            <button
              type="button"
              onClick={() => {
                if (onSelectTicker) onSelectTicker(dataB.symbol);
                else router.push(`/company/${encodeURIComponent(dataB.symbol)}?tab=company-analysis`);
              }}
              className="flex items-center gap-1.5 px-3 py-2 rounded-xl bg-navy-900 hover:bg-navy-850 border border-cyan-500/30 text-cyan-400 font-semibold transition-colors"
            >
              <span>Analyze {dataB.name} ({dataB.symbol})</span>
              <ExternalLink className="h-3.5 w-3.5" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
};
