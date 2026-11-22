'use client';

import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import {
  TrendingUp,
  TrendingDown,
  RefreshCw,
  Building2,
  DollarSign,
  BarChart3,
  Calendar,
  Layers,
  Sparkles,
  Send,
  ExternalLink,
  ChevronRight,
  Database,
  ArrowUpRight,
  ArrowDownRight,
  ShieldCheck,
  HelpCircle,
  FileSpreadsheet,
  Users,
  Star,
  Newspaper,
  Clock
} from 'lucide-react';
import { API_BASE } from '@/lib/api';
import {
  formatFinancialValue,
  formatPerShare,
  formatMultiple,
  formatPercent,
  normalizeExchange,
  getCurrencySymbol,
  getUnitLabel
} from '@/lib/formatters';

interface CitationItem {
  source_ref: string;
  chunk_type: string;
  snippet: string;
}

interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  citations?: CitationItem[];
}

interface CompanyDashboardViewProps {
  symbolOrId: string;
  initialData?: any;
  onRefresh?: () => void;
  onSelectTicker?: (ticker: string) => void;
}

export const CompanyDashboardView: React.FC<CompanyDashboardViewProps> = ({
  symbolOrId,
  initialData,
  onRefresh,
  onSelectTicker,
}) => {
  const router = useRouter();
  const [data, setData] = useState<any>(initialData || null);
  const [loading, setLoading] = useState<boolean>(!initialData);
  const [isSlowLoading, setIsSlowLoading] = useState<boolean>(false);
  const [refreshing, setRefreshing] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'income' | 'balance' | 'cashflow' | 'trends' | 'scenarios'>('income');

  // Sector Peer Comparison State (Feature 1)
  const [peerData, setPeerData] = useState<any>(null);
  const [loadingPeers, setLoadingPeers] = useState<boolean>(false);

  // Live Market News State (Analyst News Feed)
  const [newsItems, setNewsItems] = useState<any[]>([]);
  const [loadingNews, setLoadingNews] = useState<boolean>(false);

  // Watchlist Star State
  const [isWatchlisted, setIsWatchlisted] = useState<boolean>(false);

  // Cold-start notification timer for Render free-tier wake up (>5s)
  useEffect(() => {
    let timer: NodeJS.Timeout | null = null;
    if (loading) {
      setIsSlowLoading(false);
      timer = setTimeout(() => {
        setIsSlowLoading(true);
      }, 5000);
    } else {
      setIsSlowLoading(false);
    }
    return () => {
      if (timer) clearTimeout(timer);
    };
  }, [loading]);

  // AI Research Chat state
  const [question, setQuestion] = useState('');
  const [asking, setAsking] = useState(false);
  const [chatHistory, setChatHistory] = useState<ChatMessage[]>([]);

  // 1. Fetch analysis data from backend
  const fetchAnalysis = async (forceRefresh: boolean = false) => {
    if (forceRefresh) setRefreshing(true);
    else setLoading(true);
    setError(null);

    try {
      const url = `${API_BASE}/companies/${encodeURIComponent(symbolOrId)}/analysis?refresh=${forceRefresh}`;
      const res = await fetch(url);
      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}));
        throw new Error(errJson.detail || `Server returned ${res.status}`);
      }
      const json = await res.json();
      setData(json);

      if (typeof document !== 'undefined' && json.company_name && json.symbol) {
        document.title = `${json.company_name} (${json.symbol}) | FinSight AI`;
      }

      // Seed initial research message
      if (chatHistory.length === 0 && json.auto_insights?.summary_narrative) {
        let narrative = json.auto_insights.summary_narrative;
        if (json.currency === 'INR') {
          narrative = narrative.replace(/\$([0-9,.]+)\s*M/g, (match: string, p1: string) => {
            const rawVal = parseFloat(p1.replace(/,/g, ''));
            return !isNaN(rawVal) ? formatFinancialValue(rawVal, 'INR') : match;
          });
          narrative = narrative.replace(/\$([0-9,.]+)/g, (match: string, p1: string) => {
            const rawVal = parseFloat(p1.replace(/,/g, ''));
            return !isNaN(rawVal) ? formatPerShare(rawVal, 'INR') : match;
          });
        }
        setChatHistory([
          {
            role: 'assistant',
            content: narrative,
            citations: [
              {
                source_ref: `${json.company_name} | Profile Overview`,
                chunk_type: 'profile',
                snippet: 'Grounded multi-period financial analysis'
              }
            ]
          }
        ]);
      }
    } catch (err: any) {
      console.error('Failed to load analysis:', err);
      setError(err.message || 'Failed to load company analysis.');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    if (symbolOrId) {
      fetchAnalysis(false);
    }
  }, [symbolOrId]);

  // Fetch Sector Peers from Neon Postgres
  useEffect(() => {
    let isCancelled = false;
    const fetchPeers = async () => {
      setLoadingPeers(true);
      try {
        const res = await fetch(`${API_BASE}/companies/${encodeURIComponent(symbolOrId)}/peers`);
        if (res.ok) {
          const json = await res.json();
          if (!isCancelled) setPeerData(json);
        }
      } catch (err) {
        console.warn('Could not fetch peer comparison:', err);
      } finally {
        if (!isCancelled) setLoadingPeers(false);
      }
    };
    if (symbolOrId) {
      fetchPeers();
    }
    return () => {
      isCancelled = true;
    };
  }, [symbolOrId]);

  // Sync Watchlist state with localStorage & custom event
  useEffect(() => {
    const checkWatchlist = () => {
      try {
        const raw = localStorage.getItem('finsight_watchlist');
        if (raw) {
          const parsed = JSON.parse(raw);
          if (Array.isArray(parsed)) {
            const syms = parsed.map((x: any) => (typeof x === 'string' ? x : x.symbol));
            const currentSym = (data?.symbol || symbolOrId || '').toUpperCase();
            setIsWatchlisted(syms.some((s: string) => s.toUpperCase() === currentSym));
          }
        }
      } catch {}
    };

    checkWatchlist();
    window.addEventListener('watchlistUpdated', checkWatchlist);
    window.addEventListener('storage', checkWatchlist);
    return () => {
      window.removeEventListener('watchlistUpdated', checkWatchlist);
      window.removeEventListener('storage', checkWatchlist);
    };
  }, [data?.symbol, symbolOrId]);

  const toggleWatchlist = () => {
    try {
      const raw = localStorage.getItem('finsight_watchlist');
      let list: string[] = raw ? JSON.parse(raw) : ['ASIANPAINT.NS', 'RELIANCE.NS', 'TCS.NS'];
      list = list.map((x: any) => (typeof x === 'string' ? x : x.symbol));
      const targetSym = (data?.symbol || symbolOrId).trim().toUpperCase();
      if (list.some((s) => s.toUpperCase() === targetSym)) {
        list = list.filter((s) => s.toUpperCase() !== targetSym);
        setIsWatchlisted(false);
      } else {
        list.push(targetSym);
        setIsWatchlisted(true);
      }
      localStorage.setItem('finsight_watchlist', JSON.stringify(list));
      window.dispatchEvent(new Event('watchlistUpdated'));
    } catch (err) {
      console.error('Failed to toggle watchlist:', err);
    }
  };

  // Fetch Live Company Market News (30-min cache)
  useEffect(() => {
    let isCancelled = false;
    const fetchNews = async () => {
      setLoadingNews(true);
      try {
        const res = await fetch(`${API_BASE}/companies/${encodeURIComponent(symbolOrId)}/news?limit=6`);
        if (res.ok) {
          const json = await res.json();
          if (!isCancelled && Array.isArray(json.news)) {
            setNewsItems(json.news);
          }
        }
      } catch (err) {
        console.warn('Could not fetch market news:', err);
      } finally {
        if (!isCancelled) setLoadingNews(false);
      }
    };

    if (symbolOrId) {
      fetchNews();
    }
    return () => {
      isCancelled = true;
    };
  }, [symbolOrId]);

  const handleSelectPeer = (peerSymbol: string) => {
    if (onSelectTicker) {
      onSelectTicker(peerSymbol);
    } else {
      router.push(`/company/${encodeURIComponent(peerSymbol)}?tab=company-analysis`);
    }
  };

  const renderMetricComparison = (
    val?: number | null,
    median?: number | null,
    isPercentage: boolean = false,
    isLowerBetter: boolean = false,
    currencyForVal?: string
  ) => {
    if (val === null || val === undefined) {
      return <span className="text-slate-500 font-mono text-xs">—</span>;
    }

    const formattedVal = isPercentage
      ? formatPercent(val)
      : isLowerBetter
      ? formatMultiple(val)
      : currencyForVal
      ? formatFinancialValue(val, currencyForVal)
      : val.toLocaleString();

    if (median === null || median === undefined) {
      return <span className="text-slate-200 font-mono text-xs">{formattedVal}</span>;
    }

    const diff = val - median;
    const beatsMedian = isLowerBetter ? diff < 0 : diff > 0;
    const trailsMedian = isLowerBetter ? diff > 0 : diff < 0;

    return (
      <div className="flex flex-col items-end gap-0.5">
        <span className={`font-mono text-xs font-semibold ${beatsMedian ? 'text-emerald-300' : trailsMedian ? 'text-rose-300' : 'text-slate-200'}`}>
          {formattedVal}
        </span>
        {Math.abs(diff) > 0.01 && (
          <span
            className={`inline-flex items-center gap-0.5 text-[9px] font-mono px-1 py-0.2 rounded ${
              beatsMedian
                ? 'text-emerald-400 bg-emerald-950/40'
                : trailsMedian
                ? 'text-rose-400 bg-rose-950/40'
                : 'text-slate-400 bg-navy-800'
            }`}
          >
            {beatsMedian ? '▲ Beats' : '▼ Trails'} ({isPercentage ? `${diff > 0 ? '+' : ''}${diff.toFixed(1)}%` : `${diff > 0 ? '+' : ''}${diff.toFixed(1)}`})
          </span>
        )}
      </div>
    );
  };

  // 2. Submit Question to Gemini RAG API
  const handleAsk = async (userPrompt?: string) => {
    const qText = userPrompt || question.trim();
    if (!qText || !data?.company_id || asking) return;

    const newMsg: ChatMessage = { role: 'user', content: qText };
    setChatHistory((prev) => [...prev, newMsg]);
    if (!userPrompt) setQuestion('');
    setAsking(true);

    try {
      const res = await fetch(`${API_BASE}/companies/${data.company_id}/ask`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ dataset_id: data.company_id, question: qText })
      });

      if (!res.ok) {
        throw new Error('AI research query failed.');
      }

      const resJson = await res.json();
      setChatHistory((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: resJson.answer,
          citations: resJson.citations
        }
      ]);
    } catch (e: any) {
      setChatHistory((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: 'Unable to complete AI inquiry. Please ensure your backend is running and GEMINI_API_KEY is configured.'
        }
      ]);
    } finally {
      setAsking(false);
    }
  };

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[500px] text-center p-8 bg-navy-900/50 rounded-2xl border border-navy-800">
        <RefreshCw className="h-8 w-8 text-gold-400 animate-spin mb-4" />
        <h3 className="text-lg font-semibold text-white">Analyzing Financial Statements...</h3>
        <p className="text-xs text-slate-400 max-w-sm mt-1">
          Auto-fetching multi-year statements, computing deterministic ratios, and indexing pgvector chunks.
        </p>
        {isSlowLoading && (
          <div className="mt-4 px-4 py-2.5 rounded-lg bg-navy-850 border border-gold-500/30 text-gold-400 text-xs animate-pulse max-w-md shadow-lg shadow-gold-500/5">
            Waking up live market server on Render (first load may take ~20–30s)...
          </div>
        )}
      </div>
    );
  }

  if (error || !data) {
    const isColdStart = error && (
      error.toLowerCase().includes('failed to fetch') ||
      error.toLowerCase().includes('network') ||
      error.toLowerCase().includes('504') ||
      error.toLowerCase().includes('502') ||
      error.toLowerCase().includes('load failed') ||
      error.toLowerCase().includes('timed out')
    );

    return (
      <div className="flex flex-col items-center justify-center min-h-[400px] text-center p-8 bg-navy-900/60 rounded-2xl border border-navy-800 shadow-xl">
        <div className={`h-12 w-12 rounded-full ${isColdStart ? 'bg-amber-500/10 text-amber-400' : 'bg-red-500/10 text-red-400'} flex items-center justify-center mb-3`}>
          {isColdStart ? <RefreshCw className={`h-6 w-6 ${refreshing ? 'animate-spin' : ''}`} /> : <HelpCircle className="h-6 w-6" />}
        </div>
        <h3 className="text-base font-semibold text-white">
          {isColdStart ? 'Waking Up Market Engine...' : 'Analysis Unavailable'}
        </h3>
        <p className="text-xs text-slate-300 max-w-md mt-1 leading-relaxed">
          {isColdStart
            ? 'The live market backend on Render spins down during idle periods and takes ~20–30s to initialize. Click below or wait to reconnect.'
            : (error || 'No financial records found for this company.')}
        </p>
        <button
          onClick={() => fetchAnalysis(true)}
          disabled={refreshing}
          className="mt-4 px-4 py-2 rounded-lg bg-navy-800 hover:bg-navy-750 text-xs font-medium text-gold-400 border border-gold-500/30 flex items-center gap-1.5 transition-all shadow-md"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${refreshing ? 'animate-spin' : ''}`} />
          <span>{refreshing ? 'Connecting...' : 'Reconnect Live Server'}</span>
        </button>
      </div>
    );
  }

  const {
    company_name,
    symbol,
    exchange,
    currency,
    data_source,
    is_cached,
    last_synced_at,
    quote,
    periods = [],
    trends,
    scenarios,
    auto_insights
  } = data;

  const kpis = auto_insights?.kpis || auto_insights?.kpi_cards || [];
  const curSymbol = getCurrencySymbol(currency);
  const normExchange = normalizeExchange(exchange, symbol);

  // Filter out periods where core financial metrics (revenue, op_income, net_income) are all null/empty
  const validPeriods = periods.filter((p: any) =>
    (p.revenue !== null && p.revenue !== undefined) ||
    (p.operating_income !== null && p.operating_income !== undefined) ||
    (p.net_income !== null && p.net_income !== undefined)
  );
  const displayPeriods = validPeriods.length > 0 ? validPeriods : periods;

  return (
    <div className="space-y-6">
      {/* 1. INSTITUTIONAL COMPANY HEADER */}
      <div className="bg-navy-900/80 backdrop-blur border border-navy-800 rounded-2xl p-5 sm:p-6 shadow-xl relative overflow-hidden">
        <div className="absolute top-0 right-0 h-40 w-40 bg-gradient-to-br from-gold-500/5 to-transparent rounded-full blur-2xl pointer-events-none" />

        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2.5 flex-wrap">
              <h1 className="text-xl sm:text-2xl font-bold text-white tracking-tight">
                {company_name}
              </h1>
              <button
                type="button"
                onClick={toggleWatchlist}
                className={`p-1.5 rounded-lg border transition-all ${
                  isWatchlisted
                    ? 'bg-gold-500/15 border-gold-500/40 text-gold-400 shadow-sm shadow-gold-500/20'
                    : 'bg-navy-950/80 border-navy-700 text-slate-400 hover:text-gold-300 hover:border-gold-500/30'
                }`}
                title={isWatchlisted ? 'Remove from Watchlist' : 'Add to Personal Watchlist'}
              >
                <Star className={`h-4 w-4 ${isWatchlisted ? 'fill-gold-400 text-gold-400' : 'text-slate-400'}`} />
              </button>
              <span className="px-2 py-0.5 text-xs font-mono font-bold bg-navy-950 text-gold-400 border border-navy-700 rounded">
                {symbol || 'EQUITY'}
              </span>
              <span className="px-2 py-0.5 text-xs font-semibold bg-navy-800 text-slate-300 border border-navy-700 rounded">
                {normExchange}
              </span>
              {is_cached && (
                <span className="px-2 py-0.5 text-xs font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 rounded flex items-center gap-1">
                  <Database className="h-3 w-3" /> Neon Cache
                </span>
              )}
              <span className="px-2 py-0.5 text-xs font-medium bg-blue-500/10 text-blue-300 border border-blue-500/30 rounded">
                {data_source?.replace('_', ' ').toUpperCase()}
              </span>
            </div>

            <p className="text-xs text-slate-400 mt-1 flex items-center gap-3">
              <span>Currency: <strong className="text-slate-200">{currency} ({curSymbol})</strong></span>
              {quote?.sector && <span>• Sector: <strong className="text-slate-200">{quote.sector}</strong></span>}
              {last_synced_at && (
                <span>• Last synced: <strong className="text-slate-300 font-mono text-[11px]">{new Date(last_synced_at).toLocaleString()}</strong></span>
              )}
            </p>
          </div>

          {/* Price, Valuation & Refresh Button */}
          <div className="flex items-center gap-3">
            {quote?.current_price && (
              <div className="text-right pr-4 border-r border-navy-800">
                <div className="text-xs text-slate-400 font-medium">Market Price</div>
                <div className="text-lg font-bold font-mono text-white">
                  {formatPerShare(quote.current_price, currency)}
                </div>
                {quote?.trailing_pe && (
                  <div className="text-[10px] text-gold-400 font-mono">
                    P/E: {formatMultiple(quote.trailing_pe)}
                  </div>
                )}
              </div>
            )}

            <button
              onClick={() => fetchAnalysis(true)}
              disabled={refreshing}
              className="px-3.5 py-2 rounded-xl bg-navy-800 hover:bg-navy-750 text-slate-200 hover:text-white border border-navy-700 text-xs font-medium flex items-center gap-1.5 transition-all shadow-sm"
            >
              <RefreshCw className={`h-3.5 w-3.5 text-gold-400 ${refreshing ? 'animate-spin' : ''}`} />
              <span>{refreshing ? 'Syncing...' : 'Refresh Live Data'}</span>
            </button>
          </div>
        </div>
      </div>

      {/* 2. INSTITUTIONAL KPI SUMMARY STRIP */}
      {kpis.length > 0 && (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
          {kpis.map((kpi: any, i: number) => {
            let displayVal = kpi.value || 'N/A';
            const isRatio = kpi.label.includes('P/E') || kpi.label.includes('ROE') || kpi.label.includes('Margin') || kpi.label.includes('%');

            if (kpi.raw_value !== undefined && kpi.raw_value !== null && !isRatio) {
              displayVal = formatFinancialValue(kpi.raw_value, currency);
            } else if (currency === 'INR') {
              if (typeof displayVal === 'string' && displayVal.startsWith('$') && displayVal.endsWith('M')) {
                const numericStr = displayVal.replace('$', '').replace('M', '').replace(/,/g, '');
                const num = parseFloat(numericStr);
                if (!isNaN(num)) {
                  displayVal = formatFinancialValue(num, 'INR');
                }
              }
            } else if (!isRatio && typeof displayVal === 'string') {
              const cleanStr = displayVal.replace(/[$,]/g, '').trim();
              const num = parseFloat(cleanStr);
              if (!isNaN(num) && (Math.abs(num) >= 1e6 || displayVal.includes('$'))) {
                displayVal = formatFinancialValue(num, currency || 'USD');
              }
            }
            return (
              <div
                key={i}
                className="bg-navy-900/90 border border-navy-800 rounded-xl p-3.5 flex flex-col justify-between hover:border-navy-700 transition-all shadow-md"
              >
                <div className="text-[11px] font-medium text-slate-400 truncate">{kpi.label}</div>
                <div className="text-base sm:text-lg font-bold font-mono text-white mt-1">
                  {displayVal}
                </div>
                {kpi.change && (
                  <div
                    className={`text-[10px] font-semibold flex items-center gap-0.5 mt-1 ${
                      kpi.is_positive ? 'text-emerald-400' : 'text-amber-400'
                    }`}
                  >
                    {kpi.is_positive ? <TrendingUp className="h-2.5 w-2.5" /> : <TrendingDown className="h-2.5 w-2.5" />}
                    <span>{kpi.change}</span>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* 3. DETERMINISTIC SCENARIO CARDS (Trailing vs Base Case vs Best Case vs Worst Case) */}
      {scenarios && (
        <div className="bg-navy-900/70 border border-navy-800 rounded-2xl p-5 shadow-lg">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <ShieldCheck className="h-4 w-4 text-gold-400" />
              <h2 className="text-sm font-bold uppercase tracking-wider text-white">
                Valuation & Scenario Analysis
              </h2>
            </div>
            <span className="text-[10px] text-slate-400 font-mono">
              HISTORICAL AVG P/E: {scenarios.historical_avg_pe ? formatMultiple(scenarios.historical_avg_pe) : 'N/A'}
            </span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {/* Trailing */}
            <div className="bg-navy-950/80 border border-navy-800 rounded-xl p-4">
              <div className="text-[10px] uppercase font-bold text-slate-400 tracking-wider">Trailing Price</div>
              <div className="text-xl font-bold font-mono text-white mt-1">
                {formatPerShare(scenarios.trailing_price, currency)}
              </div>
              <div className="text-[10px] text-slate-400 mt-1">
                Multiple: <strong className="text-slate-200">{scenarios.trailing_pe ? formatMultiple(scenarios.trailing_pe) : 'N/A'}</strong>
              </div>
            </div>

            {/* Base Case */}
            {scenarios.base_case_price && (
              <div className="bg-navy-950/80 border border-blue-500/20 rounded-xl p-4">
                <div className="text-[10px] uppercase font-bold text-blue-400 tracking-wider">Base Case Target</div>
                <div className="text-xl font-bold font-mono text-blue-300 mt-1">
                  {formatPerShare(scenarios.base_case_price, currency)}
                </div>
                <div className="text-[10px] text-slate-400 mt-1">
                  Median Growth & Valuation Multiple
                </div>
              </div>
            )}

            {/* Best Case */}
            <div className="bg-navy-950/80 border border-emerald-500/30 rounded-xl p-4 relative overflow-hidden">
              <div className="flex items-center justify-between">
                <span className="text-[10px] uppercase font-bold text-emerald-400 tracking-wider">Best Case Target</span>
                {scenarios.upside_best_pct !== undefined && scenarios.upside_best_pct !== null && (
                  <span className="text-[10px] font-bold px-1.5 py-0.2 rounded bg-emerald-500/20 text-emerald-300">
                    {scenarios.upside_best_pct > 0 ? `+${Number(scenarios.upside_best_pct).toFixed(2)}%` : `${Number(scenarios.upside_best_pct).toFixed(2)}%`}
                  </span>
                )}
              </div>
              <div className="text-xl font-bold font-mono text-emerald-300 mt-1">
                {formatPerShare(scenarios.best_case_price, currency)}
              </div>
              <div className="text-[10px] text-slate-400 mt-1">
                Optimistic multiple expansion & sales growth
              </div>
            </div>

            {/* Worst Case */}
            <div className="bg-navy-950/80 border border-amber-500/30 rounded-xl p-4 relative overflow-hidden">
              <div className="flex items-center justify-between">
                <span className="text-[10px] uppercase font-bold text-amber-400 tracking-wider">Worst Case Floor</span>
                {scenarios.downside_worst_pct !== undefined && scenarios.downside_worst_pct !== null && (
                  <span className="text-[10px] font-bold px-1.5 py-0.2 rounded bg-amber-500/20 text-amber-300">
                    {Number(scenarios.downside_worst_pct).toFixed(2)}%
                  </span>
                )}
              </div>
              <div className="text-xl font-bold font-mono text-amber-300 mt-1">
                {formatPerShare(scenarios.worst_case_price, currency)}
              </div>
              <div className="text-[10px] text-slate-400 mt-1">
                Margin compression & conservative multiple
              </div>
            </div>
          </div>
        </div>
      )}

      {/* 3b. AUTOMATIC SECTOR PEER COMPARISON TABLE (Feature 1) */}
      <div className="bg-navy-900/90 border border-navy-800 rounded-2xl p-5 sm:p-6 shadow-xl space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-navy-800 pb-3">
          <div>
            <div className="flex items-center gap-2">
              <span className="h-5 px-2 rounded bg-cyan-500/10 text-cyan-400 border border-cyan-500/30 text-[10px] font-bold uppercase tracking-wider flex items-center gap-1">
                <Users className="h-3 w-3" />
                Institutional Peer Universe
              </span>
              <span className="text-xs text-slate-400 font-medium">
                {peerData?.sector || quote?.sector || 'Sector'} Benchmark ({peerData?.count || 6} Equities)
              </span>
            </div>
            <h2 className="text-base font-bold text-white mt-1 flex items-center gap-2">
              <span>Automatic Sector Peer Comparison</span>
              {loadingPeers && <RefreshCw className="h-3.5 w-3.5 animate-spin text-gold-400" />}
            </h2>
          </div>

          <div className="flex items-center gap-2 text-[11px] text-slate-400 font-medium">
            <span className="flex items-center gap-1">
              <span className="inline-block h-2 w-2 rounded-full bg-emerald-400" />
              <span>Beats Median</span>
            </span>
            <span>•</span>
            <span className="flex items-center gap-1">
              <span className="inline-block h-2 w-2 rounded-full bg-rose-400" />
              <span>Trails Median</span>
            </span>
            <span>•</span>
            <span className="text-slate-500">Click peer to switch</span>
          </div>
        </div>

        {loadingPeers && !peerData ? (
          <div className="py-8 flex flex-col items-center justify-center text-center text-xs text-slate-400">
            <RefreshCw className="h-5 w-5 animate-spin text-gold-400 mb-2" />
            <span>Querying Neon Postgres 301-company universe for {quote?.sector || 'sector'} peers...</span>
          </div>
        ) : !peerData ? (
          <div className="py-6 text-center text-xs text-slate-400">
            Sector peer data currently calibrating.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-xs text-left">
              <thead>
                <tr className="border-b border-navy-800 text-slate-400 text-[11px] font-mono uppercase bg-navy-950/60">
                  <th className="py-2.5 px-3 font-semibold min-w-[200px]">Company</th>
                  <th className="py-2.5 px-3 text-right font-semibold">Price</th>
                  <th className="py-2.5 px-3 text-right font-semibold">Market Cap</th>
                  <th className="py-2.5 px-3 text-right font-semibold">P/E</th>
                  <th className="py-2.5 px-3 text-right font-semibold">OPM %</th>
                  <th className="py-2.5 px-3 text-right font-semibold">Net Margin %</th>
                  <th className="py-2.5 px-3 text-right font-semibold">ROE %</th>
                  <th className="py-2.5 px-3 text-right font-semibold">YoY Rev Growth</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-navy-800/40 font-mono">
                {/* Active Company Highlight Row */}
                {peerData.target && (
                  <tr className="bg-gold-500/10 border-l-4 border-l-gold-500 hover:bg-gold-500/15 transition-colors">
                    <td className="py-3 px-3">
                      <div className="flex items-center gap-2">
                        <span className="px-1.5 py-0.5 rounded text-[9px] font-bold bg-gold-500 text-navy-950 uppercase tracking-wider">
                          Active
                        </span>
                        <div>
                          <div className="font-sans font-bold text-white text-xs">
                            {peerData.target.name}
                          </div>
                          <div className="text-[10px] text-gold-400 font-mono font-medium">
                            {peerData.target.symbol}
                          </div>
                        </div>
                      </div>
                    </td>
                    <td className="py-3 px-3 text-right text-white font-semibold">
                      {formatPerShare(peerData.target.price, peerData.target.currency)}
                    </td>
                    <td className="py-3 px-3 text-right text-slate-200">
                      {formatFinancialValue(peerData.target.market_cap, peerData.target.currency)}
                    </td>
                    <td className="py-3 px-3 text-right">
                      {renderMetricComparison(peerData.target.pe_ratio, peerData.sector_median?.pe_ratio, false, true)}
                    </td>
                    <td className="py-3 px-3 text-right">
                      {renderMetricComparison(peerData.target.opm_pct, peerData.sector_median?.opm_pct, true, false)}
                    </td>
                    <td className="py-3 px-3 text-right">
                      {renderMetricComparison(peerData.target.net_margin_pct, peerData.sector_median?.net_margin_pct, true, false)}
                    </td>
                    <td className="py-3 px-3 text-right">
                      {renderMetricComparison(peerData.target.roe_pct, peerData.sector_median?.roe_pct, true, false)}
                    </td>
                    <td className="py-3 px-3 text-right">
                      {renderMetricComparison(peerData.target.revenue_growth_pct, peerData.sector_median?.revenue_growth_pct, true, false)}
                    </td>
                  </tr>
                )}

                {/* Peer Companies Rows */}
                {(peerData.peers || []).map((peer: any, idx: number) => (
                  <tr
                    key={idx}
                    onClick={() => handleSelectPeer(peer.symbol)}
                    className="hover:bg-navy-800/60 cursor-pointer transition-colors group"
                    title={`Click to analyze ${peer.name} (${peer.symbol})`}
                  >
                    <td className="py-3 px-3">
                      <div className="flex items-center gap-1.5">
                        <ChevronRight className="h-3 w-3 text-slate-500 group-hover:text-gold-400 transition-colors" />
                        <div>
                          <div className="font-sans font-medium text-slate-200 group-hover:text-gold-300 transition-colors flex items-center gap-1">
                            <span>{peer.name}</span>
                            <ExternalLink className="h-2.5 w-2.5 text-slate-500 group-hover:text-gold-400" />
                          </div>
                          <div className="text-[10px] text-slate-400 font-mono">
                            {peer.symbol}
                          </div>
                        </div>
                      </div>
                    </td>
                    <td className="py-3 px-3 text-right text-slate-300 font-mono">
                      {formatPerShare(peer.price, peer.currency)}
                    </td>
                    <td className="py-3 px-3 text-right text-slate-300 font-mono">
                      {formatFinancialValue(peer.market_cap, peer.currency)}
                    </td>
                    <td className="py-3 px-3 text-right">
                      {renderMetricComparison(peer.pe_ratio, peerData.sector_median?.pe_ratio, false, true)}
                    </td>
                    <td className="py-3 px-3 text-right">
                      {renderMetricComparison(peer.opm_pct, peerData.sector_median?.opm_pct, true, false)}
                    </td>
                    <td className="py-3 px-3 text-right">
                      {renderMetricComparison(peer.net_margin_pct, peerData.sector_median?.net_margin_pct, true, false)}
                    </td>
                    <td className="py-3 px-3 text-right">
                      {renderMetricComparison(peer.roe_pct, peerData.sector_median?.roe_pct, true, false)}
                    </td>
                    <td className="py-3 px-3 text-right">
                      {renderMetricComparison(peer.revenue_growth_pct, peerData.sector_median?.revenue_growth_pct, true, false)}
                    </td>
                  </tr>
                ))}

                {/* Sector Median Benchmark Row */}
                {peerData.sector_median && (
                  <tr className="bg-navy-950/90 border-t-2 border-t-gold-500/40 font-bold">
                    <td className="py-3 px-3">
                      <div className="flex items-center gap-2">
                        <span className="px-2 py-0.5 rounded text-[9px] font-bold bg-cyan-950 text-cyan-300 border border-cyan-800 font-mono">
                          MEDIAN
                        </span>
                        <div className="font-sans text-xs text-white">
                          {peerData.sector_median.name}
                        </div>
                      </div>
                    </td>
                    <td className="py-3 px-3 text-right text-cyan-300 font-mono">
                      {formatPerShare(peerData.sector_median.price, peerData.sector_median.currency)}
                    </td>
                    <td className="py-3 px-3 text-right text-cyan-300 font-mono">
                      {formatFinancialValue(peerData.sector_median.market_cap, peerData.sector_median.currency)}
                    </td>
                    <td className="py-3 px-3 text-right text-cyan-300 font-mono">
                      {formatMultiple(peerData.sector_median.pe_ratio)}
                    </td>
                    <td className="py-3 px-3 text-right text-cyan-300 font-mono">
                      {formatPercent(peerData.sector_median.opm_pct)}
                    </td>
                    <td className="py-3 px-3 text-right text-cyan-300 font-mono">
                      {formatPercent(peerData.sector_median.net_margin_pct)}
                    </td>
                    <td className="py-3 px-3 text-right text-cyan-300 font-mono">
                      {formatPercent(peerData.sector_median.roe_pct)}
                    </td>
                    <td className="py-3 px-3 text-right text-cyan-300 font-mono">
                      {formatPercent(peerData.sector_median.revenue_growth_pct)}
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* 3c. LIVE COMPANY MARKET NEWS FEED */}
      <div className="bg-navy-900/90 border border-navy-800 rounded-2xl p-5 sm:p-6 shadow-xl space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-navy-800 pb-3">
          <div className="flex items-center gap-2">
            <span className="h-5 px-2 rounded bg-gold-500/10 text-gold-400 border border-gold-500/30 text-[10px] font-bold uppercase tracking-wider flex items-center gap-1">
              <Newspaper className="h-3 w-3" />
              Live News Feed
            </span>
            <h2 className="text-base font-bold text-white flex items-center gap-2">
              <span>Latest Market News & Intelligence</span>
              {loadingNews && <RefreshCw className="h-3.5 w-3.5 animate-spin text-gold-400" />}
            </h2>
          </div>

          <div className="flex items-center gap-2 text-[11px] text-slate-400">
            <span className="text-emerald-400 font-mono text-[10px] flex items-center gap-1">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse" />
              30-MIN CACHED FEED
            </span>
            <span>•</span>
            <span className="font-mono text-slate-400">{symbol}</span>
          </div>
        </div>

        {loadingNews && newsItems.length === 0 ? (
          <div className="py-8 flex flex-col items-center justify-center text-center text-xs text-slate-400">
            <RefreshCw className="h-5 w-5 animate-spin text-gold-400 mb-2" />
            <span>Scanning real-time institutional financial news wire...</span>
          </div>
        ) : newsItems.length === 0 ? (
          <div className="py-6 text-center text-xs text-slate-400">
            No recent news stories found for {symbol}. Check back during active market hours.
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {newsItems.map((item) => (
              <a
                key={item.id}
                href={item.link}
                target="_blank"
                rel="noopener noreferrer"
                className="bg-navy-950/70 hover:bg-navy-850/80 border border-navy-800 hover:border-gold-500/40 rounded-xl p-4 flex flex-col justify-between transition-all group shadow-sm hover:shadow-md"
              >
                <div>
                  <div className="flex items-center justify-between gap-2 mb-2">
                    <span className="text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded bg-navy-900 border border-navy-750 text-gold-400 truncate max-w-[140px]">
                      {item.publisher}
                    </span>
                    <span className="text-[10px] text-slate-500 font-mono flex items-center gap-1 flex-shrink-0">
                      <Clock className="h-2.5 w-2.5" />
                      {new Date(item.published_at).toLocaleDateString(undefined, {
                        month: 'short',
                        day: 'numeric',
                        year: 'numeric',
                      })}
                    </span>
                  </div>

                  <h3 className="text-xs font-semibold text-slate-200 group-hover:text-gold-300 leading-snug transition-colors line-clamp-2">
                    {item.title}
                  </h3>

                  {item.summary && (
                    <p className="text-[11px] text-slate-400 mt-1.5 line-clamp-2 leading-relaxed">
                      {item.summary}
                    </p>
                  )}
                </div>

                <div className="mt-3 pt-2 border-t border-navy-800/60 flex items-center justify-between text-[10px] text-slate-400 group-hover:text-gold-400">
                  <span className="font-medium">Read Full Article</span>
                  <ExternalLink className="h-3 w-3 text-slate-500 group-hover:text-gold-400 transition-colors" />
                </div>
              </a>
            ))}
          </div>
        )}
      </div>

      {/* 4. MAIN FINANCIAL STATEMENTS & TRENDS TABS */}
      <div className="bg-navy-900 border border-navy-800 rounded-2xl shadow-xl overflow-hidden">
        {/* Navigation Tab Bar */}
        <div className="flex items-center gap-1 border-b border-navy-800 px-4 py-2.5 overflow-x-auto bg-navy-950/50">
          <button
            onClick={() => setActiveTab('income')}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
              activeTab === 'income' ? 'bg-gold-500/20 text-gold-300 border border-gold-500/40' : 'text-slate-400 hover:text-white'
            }`}
          >
            Income Statement
          </button>
          <button
            onClick={() => setActiveTab('balance')}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
              activeTab === 'balance' ? 'bg-gold-500/20 text-gold-300 border border-gold-500/40' : 'text-slate-400 hover:text-white'
            }`}
          >
            Balance Sheet
          </button>
          <button
            onClick={() => setActiveTab('cashflow')}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
              activeTab === 'cashflow' ? 'bg-gold-500/20 text-gold-300 border border-gold-500/40' : 'text-slate-400 hover:text-white'
            }`}
          >
            Cash Flow
          </button>
          {trends && (
            <button
              onClick={() => setActiveTab('trends')}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                activeTab === 'trends' ? 'bg-gold-500/20 text-gold-300 border border-gold-500/40' : 'text-slate-400 hover:text-white'
              }`}
            >
              Multi-Year Trends Matrix
            </button>
          )}
        </div>

        {/* Tab Content Tables */}
        <div className="p-4 sm:p-5 overflow-x-auto">
          {activeTab === 'income' && (
            <table className="w-full text-xs text-left">
              <thead>
                <tr className="border-b border-navy-800 text-slate-400 text-[11px] font-mono uppercase">
                  <th className="py-2.5 pr-4 font-semibold">Metric ({getUnitLabel(currency)})</th>
                  {displayPeriods.map((p: any, idx: number) => (
                    <th key={idx} className="py-2.5 px-3 text-right font-semibold">
                      {p.fiscal_period || `FY${p.fiscal_year}`}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-navy-800/40 font-mono">
                <tr>
                  <td className="py-2.5 pr-4 text-white font-sans font-semibold">Sales / Revenue</td>
                  {displayPeriods.map((p: any, idx: number) => (
                    <td key={idx} className="py-2.5 px-3 text-right text-slate-200">
                      {formatFinancialValue(p.revenue, currency)}
                    </td>
                  ))}
                </tr>
                <tr>
                  <td className="py-2.5 pr-4 text-slate-300 font-sans">Operating Expenses</td>
                  {displayPeriods.map((p: any, idx: number) => (
                    <td key={idx} className="py-2.5 px-3 text-right text-slate-400">
                      {formatFinancialValue(p.operating_expenses, currency)}
                    </td>
                  ))}
                </tr>
                <tr className="bg-navy-950/30">
                  <td className="py-2.5 pr-4 text-emerald-400 font-sans font-semibold">Operating Profit</td>
                  {displayPeriods.map((p: any, idx: number) => (
                    <td key={idx} className="py-2.5 px-3 text-right text-emerald-300 font-bold">
                      {formatFinancialValue(p.operating_income, currency)}
                    </td>
                  ))}
                </tr>
                <tr>
                  <td className="py-2.5 pr-4 text-slate-300 font-sans">OPM %</td>
                  {displayPeriods.map((p: any, idx: number) => (
                    <td key={idx} className="py-2.5 px-3 text-right text-gold-400">
                      {p.opm_pct !== null && p.opm_pct !== undefined ? formatPercent(p.opm_pct) : '—'}
                    </td>
                  ))}
                </tr>
                <tr>
                  <td className="py-2.5 pr-4 text-slate-300 font-sans">Other Income</td>
                  {displayPeriods.map((p: any, idx: number) => (
                    <td key={idx} className="py-2.5 px-3 text-right text-slate-400">
                      {formatFinancialValue(p.other_income, currency)}
                    </td>
                  ))}
                </tr>
                <tr>
                  <td className="py-2.5 pr-4 text-slate-300 font-sans">Depreciation</td>
                  {displayPeriods.map((p: any, idx: number) => (
                    <td key={idx} className="py-2.5 px-3 text-right text-slate-400">
                      {formatFinancialValue(p.depreciation_amortization, currency)}
                    </td>
                  ))}
                </tr>
                <tr>
                  <td className="py-2.5 pr-4 text-slate-300 font-sans">Interest Expense</td>
                  {displayPeriods.map((p: any, idx: number) => (
                    <td key={idx} className="py-2.5 px-3 text-right text-slate-400">
                      {formatFinancialValue(p.interest_expense, currency)}
                    </td>
                  ))}
                </tr>
                <tr className="bg-navy-950/40">
                  <td className="py-2.5 pr-4 text-white font-sans font-semibold">Net Profit</td>
                  {displayPeriods.map((p: any, idx: number) => (
                    <td key={idx} className="py-2.5 px-3 text-right text-white font-bold">
                      {formatFinancialValue(p.net_income, currency)}
                    </td>
                  ))}
                </tr>
                <tr>
                  <td className="py-2.5 pr-4 text-slate-300 font-sans">EPS</td>
                  {displayPeriods.map((p: any, idx: number) => (
                    <td key={idx} className="py-2.5 px-3 text-right text-slate-300">
                      {formatPerShare(p.eps, currency)}
                    </td>
                  ))}
                </tr>
                <tr>
                  <td className="py-2.5 pr-4 text-slate-300 font-sans">Price to Earning (P/E)</td>
                  {displayPeriods.map((p: any, idx: number) => (
                    <td key={idx} className="py-2.5 px-3 text-right text-slate-400">
                      {formatMultiple(p.pe_ratio)}
                    </td>
                  ))}
                </tr>
              </tbody>
            </table>
          )}

          {activeTab === 'balance' && (
            <table className="w-full text-xs text-left">
              <thead>
                <tr className="border-b border-navy-800 text-slate-400 text-[11px] font-mono uppercase">
                  <th className="py-2.5 pr-4 font-semibold">Balance Sheet Items ({getUnitLabel(currency)})</th>
                  {displayPeriods.map((p: any, idx: number) => (
                    <th key={idx} className="py-2.5 px-3 text-right font-semibold">
                      {p.fiscal_period || `FY${p.fiscal_year}`}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-navy-800/40 font-mono">
                <tr>
                  <td className="py-2.5 pr-4 text-white font-sans font-semibold">Total Assets</td>
                  {displayPeriods.map((p: any, idx: number) => (
                    <td key={idx} className="py-2.5 px-3 text-right text-slate-200">
                      {formatFinancialValue(p.total_assets, currency)}
                    </td>
                  ))}
                </tr>
                <tr>
                  <td className="py-2.5 pr-4 text-slate-300 font-sans">Current Assets</td>
                  {displayPeriods.map((p: any, idx: number) => (
                    <td key={idx} className="py-2.5 px-3 text-right text-slate-400">
                      {formatFinancialValue(p.current_assets, currency)}
                    </td>
                  ))}
                </tr>
                <tr>
                  <td className="py-2.5 pr-4 text-slate-300 font-sans">Total Liabilities</td>
                  {displayPeriods.map((p: any, idx: number) => (
                    <td key={idx} className="py-2.5 px-3 text-right text-slate-400">
                      {formatFinancialValue(p.total_liabilities, currency)}
                    </td>
                  ))}
                </tr>
                <tr className="bg-navy-950/30">
                  <td className="py-2.5 pr-4 text-emerald-400 font-sans font-semibold">Stockholders Equity / Net Worth</td>
                  {displayPeriods.map((p: any, idx: number) => (
                    <td key={idx} className="py-2.5 px-3 text-right text-emerald-300 font-bold">
                      {formatFinancialValue(p.total_equity, currency)}
                    </td>
                  ))}
                </tr>
                <tr>
                  <td className="py-2.5 pr-4 text-slate-300 font-sans">Total Debt</td>
                  {displayPeriods.map((p: any, idx: number) => (
                    <td key={idx} className="py-2.5 px-3 text-right text-slate-400">
                      {formatFinancialValue(p.total_debt, currency)}
                    </td>
                  ))}
                </tr>
              </tbody>
            </table>
          )}

          {activeTab === 'cashflow' && (
            <table className="w-full text-xs text-left">
              <thead>
                <tr className="border-b border-navy-800 text-slate-400 text-[11px] font-mono uppercase">
                  <th className="py-2.5 pr-4 font-semibold">Cash Flow Statement ({getUnitLabel(currency)})</th>
                  {displayPeriods.map((p: any, idx: number) => (
                    <th key={idx} className="py-2.5 px-3 text-right font-semibold">
                      {p.fiscal_period || `FY${p.fiscal_year}`}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-navy-800/40 font-mono">
                <tr>
                  <td className="py-2.5 pr-4 text-white font-sans font-semibold">Operating Cash Flow (CFO)</td>
                  {displayPeriods.map((p: any, idx: number) => (
                    <td key={idx} className="py-2.5 px-3 text-right text-slate-200">
                      {formatFinancialValue(p.operating_cash_flow, currency)}
                    </td>
                  ))}
                </tr>
                <tr>
                  <td className="py-2.5 pr-4 text-slate-300 font-sans">Capital Expenditure (CapEx)</td>
                  {displayPeriods.map((p: any, idx: number) => (
                    <td key={idx} className="py-2.5 px-3 text-right text-slate-400">
                      {formatFinancialValue(p.capital_expenditure, currency)}
                    </td>
                  ))}
                </tr>
                <tr className="bg-navy-950/30">
                  <td className="py-2.5 pr-4 text-emerald-400 font-sans font-semibold">Free Cash Flow (FCF)</td>
                  {displayPeriods.map((p: any, idx: number) => (
                    <td key={idx} className="py-2.5 px-3 text-right text-emerald-300 font-bold">
                      {formatFinancialValue(p.free_cash_flow, currency)}
                    </td>
                  ))}
                </tr>
              </tbody>
            </table>
          )}

          {activeTab === 'trends' && trends && (
            <div className="space-y-4">
              <div className="text-[11px] text-slate-400 font-mono uppercase tracking-wider mb-2">
                Compounded Growth & Margin Matrix Across Horizons
              </div>
              <table className="w-full text-xs text-left">
                <thead>
                  <tr className="border-b border-navy-800 text-slate-400 text-[11px] font-mono uppercase">
                    <th className="py-2.5 pr-4 font-semibold">Metric</th>
                    {(trends.headers || []).map((h: string, idx: number) => (
                      <th key={idx} className="py-2.5 px-3 text-right font-semibold">
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-navy-800/40 font-mono">
                  {Object.entries(trends.metrics || {}).map(([metricName, spanMap]: [string, any], mIdx: number) => (
                    <tr key={mIdx}>
                      <td className="py-2.5 pr-4 text-white font-sans font-semibold capitalize">
                        {metricName.replace('_', ' ')}
                      </td>
                      {(trends.headers || []).map((h: string, hIdx: number) => {
                        const val = spanMap[h];
                        return (
                          <td key={hIdx} className="py-2.5 px-3 text-right text-slate-200">
                            {val !== undefined && val !== null ? `${val}%` : '—'}
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>

      {/* 5. AI RESEARCH ANALYST PANEL (GEMINI 3.8 FLASH RAG) */}
      <div className="bg-navy-900 border border-navy-800 rounded-2xl p-5 shadow-xl">
        <div className="flex items-center justify-between mb-3 border-b border-navy-800 pb-3">
          <div className="flex items-center gap-2">
            <Sparkles className="h-4 w-4 text-gold-400" />
            <h3 className="text-sm font-bold text-white tracking-wide uppercase">
              AI Research Analyst Desk (Gemini 3.8 Flash RAG)
            </h3>
          </div>
          <span className="text-[10px] text-emerald-400 font-mono flex items-center gap-1">
            <Database className="h-2.5 w-2.5" /> GROUNDED ON VERIFIED CANONICAL DB
          </span>
        </div>

        {/* Starter Prompts */}
        <div className="flex items-center gap-2 flex-wrap mb-4">
          <span className="text-[11px] text-slate-400 font-medium">Quick Prompts:</span>
          {[
            'Analyze margin & growth trends',
            'Explain Best vs. Worst case valuation',
            'Summarize revenue trajectory and operating profit'
          ].map((promptText, i) => (
            <button
              key={i}
              onClick={() => handleAsk(promptText)}
              disabled={asking}
              className="text-[11px] px-2.5 py-1 rounded-full bg-navy-800 hover:bg-navy-750 text-slate-300 hover:text-white border border-navy-700 hover:border-gold-500/40 transition-all"
            >
              {promptText}
            </button>
          ))}
        </div>

        {/* Chat History Messages */}
        <div className="space-y-3 max-h-96 overflow-y-auto pr-1 mb-4">
          {chatHistory.map((msg, idx) => (
            <div
              key={idx}
              className={`p-3.5 rounded-xl text-xs ${
                msg.role === 'user'
                  ? 'bg-navy-800 text-white ml-8 border border-navy-700'
                  : 'bg-navy-950/80 text-slate-200 mr-4 border border-navy-800'
              }`}
            >
              <div className="font-semibold text-[10px] uppercase text-gold-400 mb-1">
                {msg.role === 'user' ? 'Analyst Inquiry' : 'Institutional Synthesis'}
              </div>
              <div className="whitespace-pre-line leading-relaxed">{msg.content}</div>

              {/* Grounded Citation Chips */}
              {msg.citations && msg.citations.length > 0 && (
                <div className="mt-2.5 pt-2 border-t border-navy-800/80 flex items-center gap-1.5 flex-wrap">
                  <span className="text-[10px] text-slate-400 font-medium">Sources:</span>
                  {msg.citations.map((cite, cIdx) => (
                    <span
                      key={cIdx}
                      className="px-2 py-0.5 text-[10px] font-mono bg-navy-900 border border-navy-700 text-slate-300 rounded hover:border-gold-500/50 transition-colors"
                      title={cite.snippet}
                    >
                      {cite.source_ref}
                    </span>
                  ))}
                </div>
              )}
            </div>
          ))}

          {asking && (
            <div className="p-3.5 rounded-xl text-xs bg-navy-950/80 text-slate-400 mr-4 border border-navy-800 flex items-center gap-2">
              <RefreshCw className="h-3.5 w-3.5 text-gold-400 animate-spin" />
              <span>Querying pgvector cosine indexes and synthesizing research answer...</span>
            </div>
          )}
        </div>

        {/* Question Input Box */}
        <form
          onSubmit={(e) => {
            e.preventDefault();
            handleAsk();
          }}
          className="flex items-center gap-2"
        >
          <input
            type="text"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            disabled={asking}
            placeholder={`Ask research question about ${company_name} (e.g. What drove the OPM expansion in FY24?)...`}
            className="flex-1 bg-navy-950 border border-navy-700 rounded-xl px-4 py-2.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-gold-500/50 focus:ring-1 focus:ring-gold-500/30 transition-all"
          />
          <button
            type="submit"
            disabled={asking || !question.trim()}
            className="px-4 py-2.5 rounded-xl bg-gold-500 hover:bg-gold-450 disabled:bg-slate-750 text-navy-950 disabled:text-slate-500 font-bold text-xs flex items-center gap-1.5 transition-all shadow-md"
          >
            <Send className="h-3.5 w-3.5" />
            <span>Ask</span>
          </button>
        </form>
      </div>
    </div>
  );
};
