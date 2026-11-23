'use client';

import React, { useState, useEffect } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import ReactMarkdown from 'react-markdown';
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
  Clock,
  RotateCcw
} from 'lucide-react';
import { ChartRevenue } from '@/components/ChartRevenue';
import { ChartProfitability } from '@/components/ChartProfitability';
import { API_BASE } from '@/lib/api';
import {
  formatFinancialValue,
  formatAccountingValue,
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
  ai_mode?: 'live' | 'fallback';
  model?: string;
}

interface CompanyDashboardViewProps {
  symbolOrId: string;
  initialData?: any;
  onRefresh?: () => void;
  onSelectTicker?: (ticker: string) => void;
  currentTab?: string;
}

export const CompanyDashboardView: React.FC<CompanyDashboardViewProps> = ({
  symbolOrId,
  initialData,
  onRefresh,
  onSelectTicker,
  currentTab,
}) => {
  const router = useRouter();
  const searchParams = useSearchParams();
  const activeSection = currentTab || searchParams?.get('tab') || 'overview';
  const [data, setData] = useState<any>(initialData || null);
  const [loading, setLoading] = useState<boolean>(!initialData);
  const [isSlowLoading, setIsSlowLoading] = useState<boolean>(false);
  const [refreshing, setRefreshing] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'income' | 'balance' | 'cashflow' | 'trends' | 'scenarios'>('income');
  const [marginPeriodFilter, setMarginPeriodFilter] = useState<'annual' | 'quarterly'>('annual');

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
          citations: resJson.citations,
          ai_mode: resJson.ai_mode,
          model: resJson.model
        }
      ]);
    } catch (e: any) {
      setChatHistory((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: 'Unable to complete AI inquiry. Please ensure your backend is running and GEMINI_API_KEY is configured.',
          ai_mode: 'fallback'
        }
      ]);
    } finally {
      setAsking(false);
    }
  };

  const renderFormattedMessage = (content: string, isUser: boolean) => {
    if (isUser) {
      return <div className="whitespace-pre-line text-xs">{content}</div>;
    }
    return (
      <div className="text-slate-200 text-xs leading-relaxed space-y-1.5 overflow-hidden">
        <ReactMarkdown
          components={{
            h1: ({ node, ...props }) => <h1 className="text-sm font-bold text-gold-400 mt-2 mb-1 border-b border-navy-750 pb-0.5" {...props} />,
            h2: ({ node, ...props }) => <h2 className="text-xs font-bold text-gold-300 mt-2 mb-1 uppercase tracking-wider" {...props} />,
            h3: ({ node, ...props }) => <h3 className="text-xs font-bold text-white mt-1.5 mb-0.5" {...props} />,
            h4: ({ node, ...props }) => <h4 className="text-xs font-semibold text-slate-200 mt-1 mb-0.5" {...props} />,
            p: ({ node, ...props }) => <p className="mb-1.5 last:mb-0" {...props} />,
            strong: ({ node, ...props }) => <strong className="font-semibold text-white" {...props} />,
            ul: ({ node, ...props }) => <ul className="list-disc pl-4 space-y-1 my-1 text-slate-300" {...props} />,
            ol: ({ node, ...props }) => <ol className="list-decimal pl-4 space-y-1 my-1 text-slate-300" {...props} />,
            li: ({ node, ...props }) => <li className="pl-0.5" {...props} />,
            code: ({ node, ...props }) => <code className="bg-navy-950 px-1 py-0.5 rounded text-gold-300 font-mono text-[11px]" {...props} />,
          }}
        >
          {content}
        </ReactMarkdown>
      </div>
    );
  };

  if (loading) {
    return (
      <div className="space-y-6">
        {/* Shimmer Skeleton: Company Hero Strip */}
        <div className="bg-[#11141B] border border-white/[0.07] rounded-xl p-5 shadow-[0_1px_0_0_rgba(255,255,255,0.04)_inset] animate-pulse">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div className="space-y-2.5">
              <div className="flex items-center gap-3">
                <div className="h-7 w-48 bg-white/[0.06] rounded-md" />
                <div className="h-5 w-20 bg-white/[0.04] rounded-md" />
                <div className="h-5 w-14 bg-white/[0.04] rounded-md" />
              </div>
              <div className="h-4 w-64 bg-white/[0.03] rounded" />
            </div>
            <div className="flex items-center gap-3">
              <div className="text-right space-y-1">
                <div className="h-3 w-16 bg-white/[0.04] rounded ml-auto" />
                <div className="h-7 w-28 bg-white/[0.06] rounded-md ml-auto" />
              </div>
              <div className="h-9 w-9 bg-white/[0.04] rounded-lg" />
            </div>
          </div>
        </div>

        {/* Cold-start notification banner if server is waking up */}
        {isSlowLoading && (
          <div className="px-4 py-3 rounded-xl bg-sky-500/10 border border-sky-500/30 text-sky-300 text-xs flex items-center gap-2 animate-pulse shadow-lg">
            <RefreshCw className="h-4 w-4 animate-spin flex-shrink-0" />
            <span>Waking up live market server on Render (first load may take ~20–30s)...</span>
          </div>
        )}

        {/* Shimmer Skeleton: 5 KPI Tiles */}
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
          {[1, 2, 3, 4, 5].map((i) => (
            <div
              key={i}
              className="bg-[#11141B] border border-white/[0.07] rounded-xl p-3.5 space-y-2 animate-pulse"
            >
              <div className="h-3 w-20 bg-white/[0.04] rounded" />
              <div className="h-6 w-28 bg-white/[0.06] rounded" />
              <div className="h-3 w-16 bg-white/[0.03] rounded" />
            </div>
          ))}
        </div>

        {/* Shimmer Skeleton: Chart Container */}
        <div className="bg-[#11141B] border border-white/[0.07] rounded-xl p-5 space-y-4 animate-pulse">
          <div className="flex items-center justify-between">
            <div className="h-4 w-44 bg-white/[0.06] rounded" />
            <div className="h-5 w-32 bg-white/[0.04] rounded-lg" />
          </div>
          <div className="h-56 bg-white/[0.02] rounded-lg border border-white/[0.04] flex items-center justify-center">
            <div className="flex items-center gap-2 text-slate-500 text-xs font-mono">
              <RefreshCw className="h-4 w-4 animate-spin text-sky-400" />
              <span>Calibrating financial curves...</span>
            </div>
          </div>
        </div>

        {/* Shimmer Skeleton: Financial Table Lines */}
        <div className="bg-[#11141B] border border-white/[0.07] rounded-xl p-5 space-y-3 animate-pulse">
          <div className="h-4 w-36 bg-white/[0.06] rounded" />
          <div className="space-y-2 pt-2">
            {[1, 2, 3, 4].map((i) => (
              <div key={i} className="h-8 bg-white/[0.03] rounded flex items-center justify-between px-3">
                <div className="h-3 w-32 bg-white/[0.05] rounded" />
                <div className="flex gap-4">
                  <div className="h-3 w-16 bg-white/[0.04] rounded" />
                  <div className="h-3 w-16 bg-white/[0.04] rounded" />
                  <div className="h-3 w-16 bg-white/[0.04] rounded" />
                </div>
              </div>
            ))}
          </div>
        </div>
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
      <div className="flex flex-col items-center justify-center min-h-[400px] text-center p-8 bg-[#11141B] rounded-xl border border-white/[0.07] shadow-xl">
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
          className="mt-4 px-4 py-2 rounded-lg bg-white/[0.04] hover:bg-white/[0.08] text-xs font-medium text-sky-400 border border-sky-500/30 flex items-center gap-1.5 transition-all shadow-md"
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

  const annualPeriods = displayPeriods.filter(
    (p: any) => p.fiscal_year && p.statement_type !== 'quarterly' && (!p.fiscal_period || !p.fiscal_period.startsWith('Q'))
  );
  const quarterlyPeriods = displayPeriods
    .filter((p: any) => p.statement_type === 'quarterly' || (p.fiscal_period && p.fiscal_period.startsWith('Q')))
    .sort((a: any, b: any) => {
      const ya = a.fiscal_year || 0;
      const yb = b.fiscal_year || 0;
      if (ya !== yb) return ya - yb;
      return (a.fiscal_period || '').localeCompare(b.fiscal_period || '');
    });

  const latestPeriod = annualPeriods.length > 0 ? annualPeriods[annualPeriods.length - 1] : (displayPeriods[displayPeriods.length - 1] || {});
  const latestOpm = latestPeriod.opm_pct ?? (latestPeriod.operating_income && latestPeriod.revenue ? (latestPeriod.operating_income / latestPeriod.revenue) * 100 : null);
  const latestNetMargin = latestPeriod.net_margin_pct ?? (latestPeriod.net_income && latestPeriod.revenue ? (latestPeriod.net_income / latestPeriod.revenue) * 100 : null);
  const latestGrossMargin = latestPeriod.gross_margin_pct ?? (latestPeriod.gross_profit && latestPeriod.revenue ? (latestPeriod.gross_profit / latestPeriod.revenue) * 100 : null);
  const latestEbitda = latestPeriod.ebitda ?? (latestPeriod.operating_income != null ? latestPeriod.operating_income + Math.abs(latestPeriod.depreciation_amortization || 0) : null);
  const latestEbitdaMargin = latestPeriod.ebitda_margin_pct ?? (latestEbitda && latestPeriod.revenue ? (latestEbitda / latestPeriod.revenue) * 100 : null);
  const latestRoe = latestPeriod.roe_pct ?? (latestPeriod.net_income && latestPeriod.total_equity ? (latestPeriod.net_income / latestPeriod.total_equity) * 100 : null);
  const latestFcf = latestPeriod.free_cash_flow;
  const latestDebtToEquity = latestPeriod.debt_to_equity ?? (latestPeriod.total_debt && latestPeriod.total_equity ? latestPeriod.total_debt / latestPeriod.total_equity : null);

  // Sliced strictly by annual periods to prevent quarterly dip artifacts on multi-year trajectory
  const annualChartPeriods = annualPeriods.length > 0 ? annualPeriods : displayPeriods;
  const chartData = annualChartPeriods.map((p: any) => {
    const ebitdaVal = p.ebitda ?? (p.operating_income != null ? p.operating_income + Math.abs(p.depreciation_amortization || 0) : null);
    return {
      period: p.fiscal_period || (p.fiscal_year ? `FY${p.fiscal_year}` : 'FY'),
      revenue: p.revenue || 0,
      gross_profit: p.gross_profit || (p.revenue && p.cost_of_revenue ? p.revenue - p.cost_of_revenue : p.operating_income || 0),
      net_income: p.net_income || 0,
      ebitda: ebitdaVal || 0,
    };
  });

  // 1. INSTITUTIONAL COMPANY HEADER
  const renderHeader = () => {
    const marketPrice = quote?.current_price;
    const peRatio = quote?.trailing_pe;
    const mCap = quote?.market_cap;

    return (
      <div className="bg-[#11141B] border border-white/[0.07] rounded-xl p-5 shadow-[0_1px_0_0_rgba(255,255,255,0.04)_inset] relative overflow-hidden">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="space-y-1.5">
            <div className="flex items-center gap-2.5 flex-wrap">
              <h1 className="text-xl sm:text-2xl font-bold text-white tracking-tight">
                {company_name}
              </h1>
              <button
                type="button"
                onClick={toggleWatchlist}
                className={`p-1.5 rounded-lg border transition-all ${
                  isWatchlisted
                    ? 'bg-sky-500/10 border-sky-500/30 text-sky-400 shadow-sm'
                    : 'bg-white/[0.03] border-white/[0.08] text-slate-400 hover:text-white hover:border-white/[0.15]'
                }`}
                title={isWatchlisted ? 'Remove from Watchlist' : 'Add to Personal Watchlist'}
              >
                <Star className={`h-4 w-4 ${isWatchlisted ? 'fill-sky-400 text-sky-400' : 'text-slate-400'}`} />
              </button>
              <span className="px-2 py-0.5 text-xs font-mono font-bold bg-white/[0.04] text-sky-400 border border-white/[0.08] rounded">
                {symbol || 'EQUITY'}
              </span>
              <span className="px-2 py-0.5 text-xs font-semibold bg-white/[0.04] text-slate-300 border border-white/[0.08] rounded">
                {normExchange}
              </span>
              {quote?.sector && (
                <span className="px-2 py-0.5 text-xs font-medium bg-sky-500/10 text-sky-400 border border-sky-500/20 rounded">
                  {quote.sector}
                </span>
              )}
              {is_cached && (
                <span className="px-2 py-0.5 text-xs font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 rounded flex items-center gap-1 font-mono">
                  <Database className="h-2.5 w-2.5" /> Neon DB
                </span>
              )}
            </div>

            <p className="text-xs text-slate-400 flex items-center gap-3 font-mono">
              <span>Currency: <strong className="text-slate-200">{currency} ({curSymbol})</strong></span>
              {last_synced_at && (
                <span>• Synced: <strong className="text-slate-300 font-mono text-[11px]">{new Date(last_synced_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</strong></span>
              )}
            </p>
          </div>

          {/* Large Tabular Price, Inline P/E, Market Cap & Icon-Only Refresh */}
          <div className="flex items-center gap-3 self-start md:self-auto">
            {marketPrice != null && (
              <div className="text-left md:text-right pr-3 md:border-r md:border-white/[0.08]">
                <div className="text-[10px] uppercase font-mono font-medium text-slate-400 tracking-wider">Market Price</div>
                <div className="text-2xl font-bold font-mono text-white tabular-nums tracking-tight">
                  {formatPerShare(marketPrice, currency)}
                </div>
                <div className="flex items-center gap-2 text-[11px] font-mono text-slate-400 mt-0.5">
                  {peRatio != null && (
                    <span>P/E: <strong className="text-slate-200 tabular-nums">{formatMultiple(peRatio)}</strong></span>
                  )}
                  {mCap != null && (
                    <span>• MCap: <strong className="text-slate-200 tabular-nums">{formatFinancialValue(mCap, currency)}</strong></span>
                  )}
                </div>
              </div>
            )}

            {/* Clean icon-only refresh button */}
            <button
              onClick={() => fetchAnalysis(true)}
              disabled={refreshing}
              className="p-2.5 rounded-lg bg-white/[0.04] hover:bg-white/[0.08] text-slate-300 hover:text-white border border-white/[0.08] transition-all shadow-sm"
              title={refreshing ? 'Syncing...' : 'Refresh Live Data'}
            >
              <RefreshCw className={`h-4 w-4 text-sky-400 ${refreshing ? 'animate-spin' : ''}`} />
            </button>
          </div>
        </div>
      </div>
    );
  };

  // 2. SECTOR PEER COMPARISON TABLE (Shared)
  const renderComparisonCell = (
    val: number | null | undefined,
    median: number | null | undefined,
    formatted: string,
    lowerIsBetter: boolean = false,
    _higherIsBetter: boolean = true
  ) => {
    return renderMetricComparison(val, median, formatted.includes('%'), lowerIsBetter);
  };

  const renderPeerComparison = () => (
    <div className="bg-[#11141B] border border-white/[0.07] rounded-xl p-5 shadow-[0_1px_0_0_rgba(255,255,255,0.04)_inset] space-y-4">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-white/[0.06] pb-3">
        <div>
          <div className="flex items-center gap-2">
            <span className="h-5 px-2 rounded bg-sky-500/10 text-sky-400 border border-sky-500/20 text-[10px] font-bold uppercase tracking-wider flex items-center gap-1 font-mono">
              <Users className="h-3 w-3" />
              Institutional Peer Universe
            </span>
            <span className="text-xs text-slate-400 font-medium">
              {peerData?.sector || quote?.sector || 'Sector'} Benchmark ({peerData?.count || 6} Equities)
            </span>
          </div>
          <h2 className="text-base font-bold text-white mt-1 flex items-center gap-2">
            <span>Automatic Sector Peer Comparison</span>
            {loadingPeers && <RefreshCw className="h-3.5 w-3.5 animate-spin text-sky-400" />}
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
          <span>Querying Neon Postgres universe for {quote?.sector || 'sector'} peers...</span>
        </div>
      ) : !peerData ? (
        <div className="py-6 text-center text-xs text-slate-400">
          Sector peer data currently calibrating.
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-xs text-left">
            <thead>
              <tr className="border-b border-white/[0.06] text-slate-400 text-[11px] font-mono uppercase bg-[#0C0E14]">
                <th className="py-2.5 px-3 font-semibold min-w-[200px]">Company</th>
                <th className="py-2.5 px-3 text-right font-semibold">Price</th>
                <th className="py-2.5 px-3 text-right font-semibold">Market Cap</th>
                <th className="py-2.5 px-3 text-right font-semibold">P/E</th>
                <th className="py-2.5 px-3 text-right font-semibold">P/B</th>
                <th className="py-2.5 px-3 text-right font-semibold">EV/EBITDA</th>
                <th className="py-2.5 px-3 text-right font-semibold">EBITDA Margin %</th>
                <th className="py-2.5 px-3 text-right font-semibold">OPM %</th>
                <th className="py-2.5 px-3 text-right font-semibold">Net Margin %</th>
                <th className="py-2.5 px-3 text-right font-semibold">ROE %</th>
                <th className="py-2.5 px-3 text-right font-semibold">YoY Rev Growth</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/[0.04] font-mono tabular-nums">
              {/* Active Company Highlight Row */}
              {peerData.target && (
                <tr className="bg-sky-500/10 border-l-4 border-l-sky-400 hover:bg-sky-500/15 transition-colors">
                  <td className="py-3 px-3">
                    <div className="flex items-center gap-2">
                      <span className="px-1.5 py-0.5 rounded text-[9px] font-bold bg-sky-500 text-white uppercase tracking-wider font-mono">
                        Active
                      </span>
                      <div>
                        <div className="font-sans font-bold text-white text-xs">
                          {peerData.target.name}
                        </div>
                        <div className="text-[10px] text-sky-400 font-mono font-medium">
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
                    {renderComparisonCell(
                      peerData.target.pe_ratio,
                      peerData.sector_median?.pe_ratio,
                      peerData.target.pe_ratio != null ? `${Number(peerData.target.pe_ratio).toFixed(2)}x` : '—',
                      true,
                      false
                    )}
                  </td>
                  <td className="py-3 px-3 text-right">
                    {renderComparisonCell(
                      peerData.target.price_to_book,
                      peerData.sector_median?.price_to_book,
                      peerData.target.price_to_book != null ? `${Number(peerData.target.price_to_book).toFixed(2)}x` : '—',
                      true,
                      false
                    )}
                  </td>
                  <td className="py-3 px-3 text-right">
                    {renderComparisonCell(
                      peerData.target.ev_to_ebitda,
                      peerData.sector_median?.ev_to_ebitda,
                      peerData.target.ev_to_ebitda != null ? `${Number(peerData.target.ev_to_ebitda).toFixed(2)}x` : '—',
                      true,
                      false
                    )}
                  </td>
                  <td className="py-3 px-3 text-right">
                    {renderComparisonCell(
                      peerData.target.ebitda_margin_pct,
                      peerData.sector_median?.ebitda_margin_pct,
                      peerData.target.ebitda_margin_pct != null ? `${Number(peerData.target.ebitda_margin_pct).toFixed(2)}%` : '—',
                      false,
                      true
                    )}
                  </td>
                  <td className="py-3 px-3 text-right">
                    {renderComparisonCell(
                      peerData.target.opm_pct,
                      peerData.sector_median?.opm_pct,
                      peerData.target.opm_pct != null ? `${Number(peerData.target.opm_pct).toFixed(2)}%` : '—',
                      false,
                      true
                    )}
                  </td>
                  <td className="py-3 px-3 text-right">
                    {renderComparisonCell(
                      peerData.target.net_margin_pct,
                      peerData.sector_median?.net_margin_pct,
                      peerData.target.net_margin_pct != null ? `${Number(peerData.target.net_margin_pct).toFixed(2)}%` : '—',
                      false,
                      true
                    )}
                  </td>
                  <td className="py-3 px-3 text-right">
                    {renderComparisonCell(
                      peerData.target.roe_pct,
                      peerData.sector_median?.roe_pct,
                      peerData.target.roe_pct != null ? `${Number(peerData.target.roe_pct).toFixed(2)}%` : '—',
                      false,
                      true
                    )}
                  </td>
                  <td className="py-3 px-3 text-right">
                    {renderComparisonCell(
                      peerData.target.revenue_growth_pct,
                      peerData.sector_median?.revenue_growth_pct,
                      peerData.target.revenue_growth_pct != null ? `${Number(peerData.target.revenue_growth_pct).toFixed(2)}%` : '—',
                      false,
                      true
                    )}
                  </td>
                </tr>
              )}

              {/* Peer Companies Rows */}
              {(peerData.peers || []).map((peer: any) => (
                <tr
                  key={peer.symbol}
                  onClick={() => handleSelectPeer(peer.symbol)}
                  className="hover:bg-white/[0.03] cursor-pointer transition-colors group border-b border-white/[0.04]"
                >
                  <td className="py-3 px-3">
                    <div className="flex items-center gap-2">
                      <ChevronRight className="h-3 w-3 text-slate-500 group-hover:text-sky-400 group-hover:translate-x-0.5 transition-all" />
                      <div>
                        <div className="font-sans font-medium text-slate-200 group-hover:text-white text-xs transition-colors">
                          {peer.name}
                        </div>
                        <div className="text-[10px] text-slate-400 font-mono">
                          {peer.symbol}
                        </div>
                      </div>
                    </div>
                  </td>
                  <td className="py-3 px-3 text-right text-slate-200">
                    {formatPerShare(peer.price, peer.currency)}
                  </td>
                  <td className="py-3 px-3 text-right text-slate-300">
                    {formatFinancialValue(peer.market_cap, peer.currency)}
                  </td>
                  <td className="py-3 px-3 text-right text-slate-200">
                    {renderComparisonCell(
                      peer.pe_ratio,
                      peerData.sector_median?.pe_ratio,
                      peer.pe_ratio != null ? `${Number(peer.pe_ratio).toFixed(2)}x` : '—',
                      true,
                      false
                    )}
                  </td>
                  <td className="py-3 px-3 text-right text-slate-200">
                    {renderComparisonCell(
                      peer.price_to_book,
                      peerData.sector_median?.price_to_book,
                      peer.price_to_book != null ? `${Number(peer.price_to_book).toFixed(2)}x` : '—',
                      true,
                      false
                    )}
                  </td>
                  <td className="py-3 px-3 text-right text-slate-200">
                    {renderComparisonCell(
                      peer.ev_to_ebitda,
                      peerData.sector_median?.ev_to_ebitda,
                      peer.ev_to_ebitda != null ? `${Number(peer.ev_to_ebitda).toFixed(2)}x` : '—',
                      true,
                      false
                    )}
                  </td>
                  <td className="py-3 px-3 text-right text-slate-200">
                    {renderComparisonCell(
                      peer.ebitda_margin_pct,
                      peerData.sector_median?.ebitda_margin_pct,
                      peer.ebitda_margin_pct != null ? `${Number(peer.ebitda_margin_pct).toFixed(2)}%` : '—',
                      false,
                      true
                    )}
                  </td>
                  <td className="py-3 px-3 text-right text-slate-200">
                    {renderComparisonCell(
                      peer.opm_pct,
                      peerData.sector_median?.opm_pct,
                      peer.opm_pct != null ? `${Number(peer.opm_pct).toFixed(2)}%` : '—',
                      false,
                      true
                    )}
                  </td>
                  <td className="py-3 px-3 text-right text-slate-200">
                    {renderComparisonCell(
                      peer.net_margin_pct,
                      peerData.sector_median?.net_margin_pct,
                      peer.net_margin_pct != null ? `${Number(peer.net_margin_pct).toFixed(2)}%` : '—',
                      false,
                      true
                    )}
                  </td>
                  <td className="py-3 px-3 text-right text-slate-200">
                    {renderComparisonCell(
                      peer.roe_pct,
                      peerData.sector_median?.roe_pct,
                      peer.roe_pct != null ? `${Number(peer.roe_pct).toFixed(2)}%` : '—',
                      false,
                      true
                    )}
                  </td>
                  <td className="py-3 px-3 text-right text-slate-200">
                    {renderComparisonCell(
                      peer.revenue_growth_pct,
                      peerData.sector_median?.revenue_growth_pct,
                      peer.revenue_growth_pct != null ? `${Number(peer.revenue_growth_pct).toFixed(2)}%` : '—',
                      false,
                      true
                    )}
                  </td>
                </tr>
              ))}

              {/* Sector Median Benchmark Row */}
              {peerData.sector_median && (
                <tr className="bg-sky-500/[0.06] font-bold border-t-2 border-sky-500/30">
                  <td className="py-3 px-3">
                    <div className="flex items-center gap-2">
                      <span className="px-2 py-0.5 rounded text-[9px] font-bold bg-sky-500/10 text-sky-400 border border-sky-500/20 font-mono">
                        MEDIAN
                      </span>
                      <div className="font-sans text-xs text-white">
                        {peerData.sector_median.name}
                      </div>
                    </div>
                  </td>
                  <td className="py-3 px-3 text-right text-sky-300 font-mono tabular-nums">
                    {formatPerShare(peerData.sector_median.price, peerData.sector_median.currency)}
                  </td>
                  <td className="py-3 px-3 text-right text-sky-300 font-mono tabular-nums">
                    {formatFinancialValue(peerData.sector_median.market_cap, peerData.sector_median.currency)}
                  </td>
                  <td className="py-3 px-3 text-right text-sky-300 font-mono tabular-nums">
                    {formatMultiple(peerData.sector_median.pe_ratio)}
                  </td>
                  <td className="py-3 px-3 text-right text-sky-300 font-mono tabular-nums">
                    {formatMultiple(peerData.sector_median.price_to_book)}
                  </td>
                  <td className="py-3 px-3 text-right text-sky-300 font-mono tabular-nums">
                    {formatMultiple(peerData.sector_median.ev_to_ebitda)}
                  </td>
                  <td className="py-3 px-3 text-right text-sky-300 font-mono tabular-nums">
                    {formatPercent(peerData.sector_median.ebitda_margin_pct)}
                  </td>
                  <td className="py-3 px-3 text-right text-sky-300 font-mono tabular-nums">
                    {formatPercent(peerData.sector_median.opm_pct)}
                  </td>
                  <td className="py-3 px-3 text-right text-sky-300 font-mono tabular-nums">
                    {formatPercent(peerData.sector_median.net_margin_pct)}
                  </td>
                  <td className="py-3 px-3 text-right text-sky-300 font-mono tabular-nums">
                    {formatPercent(peerData.sector_median.roe_pct)}
                  </td>
                  <td className="py-3 px-3 text-right text-sky-300 font-mono tabular-nums">
                    {formatPercent(peerData.sector_median.revenue_growth_pct)}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );

  // 3. DEDICATED COMPANY ANALYSIS WORKSPACE (?tab=company-analysis)
  const renderCompanyAnalysisWorkspace = () => {
    const cagrHeaders = trends?.headers || ['3 YEARS', '5 YEARS'];
    const cagrMetrics = trends?.metrics || {};

    return (
      <div className="space-y-6">
        {/* Sector Peer Comparison Table */}
        {renderPeerComparison()}

        {/* Historical Multi-Year CAGRs Matrix */}
        <div className="bg-navy-900 border border-navy-800 rounded-2xl p-5 sm:p-6 shadow-xl space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-navy-800 pb-3">
            <div className="flex items-center gap-2">
              <span className="h-5 px-2 rounded bg-gold-500/10 text-gold-400 border border-gold-500/30 text-[10px] font-bold uppercase tracking-wider flex items-center gap-1">
                <TrendingUp className="h-3 w-3" />
                Growth Matrix
              </span>
              <h2 className="text-base font-bold text-white">
                Historical Multi-Year Compound Annual Growth Rates (CAGRs)
              </h2>
            </div>
            <span className="text-xs text-slate-400 font-mono">
              Audited Historical Financial Trajectory
            </span>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-xs text-left">
              <thead>
                <tr className="border-b border-white/[0.06] text-slate-400 text-[11px] font-mono uppercase bg-[#0C0E14]">
                  <th className="py-3 px-4 font-semibold min-w-[220px]">Metric</th>
                  {cagrHeaders.map((h: string, idx: number) => (
                    <th key={idx} className="py-3 px-4 text-right font-bold text-white min-w-[110px]">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-white/[0.04] font-mono tabular-nums">
                {[
                  { key: 'sales_growth', label: 'Sales / Revenue CAGR' },
                  { key: 'ebitda_growth', label: 'EBITDA CAGR' },
                  { key: 'ebit_growth', label: 'Operating Profit (EBIT) CAGR' },
                  { key: 'net_profit_growth', label: 'Net Profit CAGR' },
                  { key: 'eps_growth', label: 'Diluted EPS CAGR' },
                  { key: 'fcf_growth', label: 'Free Cash Flow (FCF) CAGR' },
                ].map((row, rIdx) => {
                  const metricMap = cagrMetrics[row.key] || {};
                  return (
                    <tr key={rIdx} className="hover:bg-navy-800/40 transition-colors">
                      <td className="py-3 px-4 font-sans font-semibold text-slate-200">
                        {row.label}
                      </td>
                      {cagrHeaders.map((h: string, hIdx: number) => {
                        const val = metricMap[h];
                        const isNM = val === 'N/M' || val === 'NM';
                        const isNum = typeof val === 'number' && !isNaN(val);
                        const isPos = isNum && val >= 0;
                        return (
                          <td key={hIdx} className="py-3 px-4 text-right">
                            {isNM ? (
                              <span className="text-slate-400 font-mono text-[11px] font-semibold">N/M</span>
                            ) : isNum ? (
                              <span className={`font-bold ${isPos ? 'text-emerald-400' : 'text-rose-400'}`}>
                                {isPos ? '+' : ''}{Number(val).toFixed(2)}%
                              </span>
                            ) : (
                              <span className="text-slate-500">—</span>
                            )}
                          </td>
                        );
                      })}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>

        {/* Margin & Growth Trend Charts */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="bg-navy-900 border border-navy-800 rounded-2xl p-5 shadow-xl">
            <div className="flex items-center justify-between mb-4 border-b border-navy-800 pb-3">
              <div className="flex items-center gap-2">
                <BarChart3 className="h-4 w-4 text-gold-400" />
                <h3 className="text-sm font-bold text-white uppercase tracking-wider">
                  Revenue & Net Profit Trajectory
                </h3>
              </div>
              <span className="text-[10px] font-mono text-slate-400">Multi-Period Horizon</span>
            </div>
            <ChartRevenue data={chartData} ticker={symbol} />
          </div>

          <ChartProfitability
            grossMargin={latestGrossMargin}
            ebitdaMargin={latestEbitdaMargin}
            operatingMargin={latestOpm}
            netMargin={latestNetMargin}
          />
        </div>

        {/* Multi-Period Margin Trends Breakdown */}
        <div className="bg-navy-900 border border-navy-800 rounded-2xl p-5 shadow-xl space-y-3">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-navy-800 pb-2.5">
            <div>
              <h3 className="text-sm font-bold text-white uppercase tracking-wider">
                Historical Margin Evolution
              </h3>
              <span className="text-xs text-slate-400 font-mono">
                {marginPeriodFilter === 'annual' ? 'Annual (FY) Reporting Periods' : 'Quarterly Financial Trajectory'}
              </span>
            </div>
            {/* Annual | Quarterly Toggle Pill */}
            <div className="flex items-center gap-1 bg-[#090B0F] p-0.5 rounded-lg border border-white/[0.08]">
              <button
                onClick={() => setMarginPeriodFilter('annual')}
                className={`px-2.5 py-1 text-[11px] font-mono rounded transition-all ${
                  marginPeriodFilter === 'annual' ? 'bg-sky-500 text-white font-bold shadow-sm' : 'text-slate-400 hover:text-white'
                }`}
              >
                Annual {annualPeriods.length > 0 && `(${annualPeriods.length}Y)`}
              </button>
              <button
                onClick={() => setMarginPeriodFilter('quarterly')}
                className={`px-2.5 py-1 text-[11px] font-mono rounded transition-all ${
                  marginPeriodFilter === 'quarterly' ? 'bg-sky-500 text-white font-bold shadow-sm' : 'text-slate-400 hover:text-white'
                }`}
              >
                Quarterly {quarterlyPeriods.length > 0 && `(${quarterlyPeriods.length}Q)`}
              </button>
            </div>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-xs text-left">
              <thead>
                <tr className="border-b border-white/[0.06] text-slate-400 text-[11px] font-mono uppercase bg-[#0C0E14]">
                  <th className="py-2.5 px-3 font-semibold min-w-[200px]">Margin Ratio</th>
                  {(marginPeriodFilter === 'annual' ? (annualPeriods.length > 0 ? annualPeriods : displayPeriods) : (quarterlyPeriods.length > 0 ? quarterlyPeriods : displayPeriods)).map((p: any, idx: number) => (
                    <th key={idx} className="py-2.5 px-3 text-right font-mono font-bold text-white">
                      {p.fiscal_period || (p.fiscal_year ? `FY${p.fiscal_year}` : 'FY')}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-white/[0.04] font-mono tabular-nums">
                <tr>
                  <td className="py-2.5 px-3 font-sans font-medium text-slate-300">Gross Margin %</td>
                  {(marginPeriodFilter === 'annual' ? (annualPeriods.length > 0 ? annualPeriods : displayPeriods) : (quarterlyPeriods.length > 0 ? quarterlyPeriods : displayPeriods)).map((p: any, idx: number) => {
                    const gm = p.gross_margin_pct ?? (p.gross_profit && p.revenue ? (p.gross_profit / p.revenue) * 100 : null);
                    return (
                      <td key={idx} className="py-2.5 px-3 text-right text-slate-200">
                        {formatPercent(gm)}
                      </td>
                    );
                  })}
                </tr>
                <tr>
                  <td className="py-2.5 px-3 font-sans font-medium text-slate-300">EBITDA Margin %</td>
                  {(marginPeriodFilter === 'annual' ? (annualPeriods.length > 0 ? annualPeriods : displayPeriods) : (quarterlyPeriods.length > 0 ? quarterlyPeriods : displayPeriods)).map((p: any, idx: number) => {
                    const ebitdaVal = p.ebitda ?? (p.operating_income != null ? p.operating_income + Math.abs(p.depreciation_amortization || 0) : null);
                    const em = p.ebitda_margin_pct ?? (ebitdaVal != null && p.revenue ? (ebitdaVal / p.revenue) * 100 : null);
                    return (
                      <td key={idx} className="py-2.5 px-3 text-right text-indigo-400 font-semibold">
                        {formatPercent(em)}
                      </td>
                    );
                  })}
                </tr>
                <tr>
                  <td className="py-2.5 px-3 font-sans font-medium text-slate-300">Operating Margin (OPM) %</td>
                  {(marginPeriodFilter === 'annual' ? (annualPeriods.length > 0 ? annualPeriods : displayPeriods) : (quarterlyPeriods.length > 0 ? quarterlyPeriods : displayPeriods)).map((p: any, idx: number) => {
                    const op = p.opm_pct ?? (p.operating_income && p.revenue ? (p.operating_income / p.revenue) * 100 : null);
                    return (
                      <td key={idx} className="py-2.5 px-3 text-right text-gold-300 font-semibold">
                        {formatPercent(op)}
                      </td>
                    );
                  })}
                </tr>
                <tr>
                  <td className="py-2.5 px-3 font-sans font-medium text-slate-300">Net Profit Margin %</td>
                  {(marginPeriodFilter === 'annual' ? (annualPeriods.length > 0 ? annualPeriods : displayPeriods) : (quarterlyPeriods.length > 0 ? quarterlyPeriods : displayPeriods)).map((p: any, idx: number) => {
                    const nm = p.net_margin_pct ?? (p.net_income && p.revenue ? (p.net_income / p.revenue) * 100 : null);
                    return (
                      <td key={idx} className="py-2.5 px-3 text-right text-emerald-400 font-semibold">
                        {formatPercent(nm)}
                      </td>
                    );
                  })}
                </tr>
                <tr>
                  <td className="py-2.5 px-3 font-sans font-medium text-slate-300">FCF Margin %</td>
                  {(marginPeriodFilter === 'annual' ? (annualPeriods.length > 0 ? annualPeriods : displayPeriods) : (quarterlyPeriods.length > 0 ? quarterlyPeriods : displayPeriods)).map((p: any, idx: number) => {
                    const fcfm = p.fcf_margin_pct ?? (p.free_cash_flow && p.revenue ? (p.free_cash_flow / p.revenue) * 100 : null);
                    return (
                      <td key={idx} className="py-2.5 px-3 text-right text-slate-200">
                        {formatPercent(fcfm)}
                      </td>
                    );
                  })}
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    );
  };

  // 4. DEDICATED FULL-HEIGHT AI RESEARCH ASSISTANT WORKSPACE (?tab=ai-research)
  const renderAiResearchWorkspace = () => {
    return (
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 items-start">
        {/* Left/Main Conversation Workspace */}
        <div className="lg:col-span-2 bg-navy-900 border border-navy-800 rounded-2xl p-5 sm:p-6 shadow-xl flex flex-col space-y-4">
          <div className="flex items-center justify-between border-b border-navy-800 pb-3">
            <div className="flex items-center gap-2.5">
              <Sparkles className="h-5 w-5 text-gold-400" />
              <div>
                <h2 className="text-sm font-bold text-white uppercase tracking-wider">
                  Dedicated AI Analyst Research Workspace
                </h2>
                <div className="text-[10px] text-slate-400 font-mono">
                  Gemini Flash RAG • Cosine Similarity over Verified Neon Postgres Vectors
                </div>
              </div>
            </div>
            <button
              onClick={() => setChatHistory([])}
              className="text-[10px] text-slate-400 hover:text-white px-2.5 py-1 rounded-lg bg-navy-800 hover:bg-navy-750 border border-navy-700 transition-colors flex items-center gap-1"
            >
              <RotateCcw className="h-3 w-3" />
              <span>Clear Chat</span>
            </button>
          </div>

          {/* Clickable Starter Prompt Chips */}
          <div className="flex items-center gap-2 overflow-x-auto pb-1 scrollbar-thin">
            <span className="text-[10px] text-slate-400 uppercase font-semibold whitespace-nowrap flex items-center gap-1">
              <Sparkles className="h-3 w-3 text-gold-400" /> Starters:
            </span>
            {[
              "Is cash generation healthy?",
              "Summarize key financial risks",
              "Explain valuation vs peers",
              "What drove the OPM expansion or contraction?",
              "Analyze balance sheet solvency & debt burden"
            ].map((pText, i) => (
              <button
                key={i}
                onClick={() => handleAsk(pText)}
                disabled={asking}
                className="text-xs px-3 py-1.5 rounded-full bg-navy-800 hover:bg-navy-750 text-slate-300 hover:text-gold-300 border border-navy-700 hover:border-gold-500/40 whitespace-nowrap transition-all flex-shrink-0 disabled:opacity-50"
              >
                {pText}
              </button>
            ))}
          </div>

          {/* Scrollable Conversation History */}
          <div className="min-h-[440px] max-h-[580px] overflow-y-auto pr-2 space-y-4 bg-navy-950/70 rounded-xl p-4 border border-navy-800/80">
            {chatHistory.map((msg, idx) => (
              <div
                key={idx}
                className={`p-4 rounded-xl text-xs leading-relaxed ${
                  msg.role === 'user'
                    ? 'bg-navy-800 text-white ml-8 border border-navy-700 shadow-sm'
                    : 'bg-navy-900 text-slate-200 mr-2 border border-navy-750 shadow-md'
                }`}
              >
                <div className="flex items-center justify-between mb-1.5">
                  <span className="font-bold text-[10px] uppercase font-mono tracking-wider text-gold-400">
                    {msg.role === 'user' ? 'Analyst Inquiry' : 'Institutional Synthesis'}
                  </span>
                  <span className="text-[9px] text-slate-500 font-mono">
                    {msg.role === 'user' ? 'Prompt' : (msg.ai_mode === 'live' ? `${msg.model || 'Gemini Flash'} · Live AI` : 'Deterministic Synthesis')}
                  </span>
                </div>
                {renderFormattedMessage(msg.content, msg.role === 'user')}

                {msg.citations && msg.citations.length > 0 && (
                  <div className="mt-3 pt-2.5 border-t border-navy-800 flex items-center gap-1.5 flex-wrap">
                    <span className="text-[10px] text-slate-400 font-medium">Grounded Sources:</span>
                    {msg.citations.map((cite, cIdx) => (
                      <span
                        key={cIdx}
                        className="px-2 py-0.5 text-[9px] font-mono bg-navy-950 border border-navy-750 text-gold-300 rounded"
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
              <div className="p-4 rounded-xl text-xs bg-navy-900 border border-navy-750 text-slate-300 flex items-center gap-3">
                <RefreshCw className="h-4 w-4 text-gold-400 animate-spin flex-shrink-0" />
                <span>Synthesizing research answer from financial statements and pgvector embeddings...</span>
              </div>
            )}
          </div>

          {/* Interactive Question Input Form */}
          <form
            onSubmit={(e) => {
              e.preventDefault();
              handleAsk();
            }}
            className="flex items-center gap-2 pt-1"
          >
            <input
              type="text"
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              disabled={asking}
              placeholder={`Ask institutional research question about ${company_name} (e.g. Is cash generation healthy?)...`}
              className="flex-1 bg-navy-950 border border-navy-700 focus:border-gold-500/50 rounded-xl px-4 py-3 text-xs text-white placeholder-slate-500 focus:outline-none transition-all"
            />
            <button
              type="submit"
              disabled={asking || !question.trim()}
              className="px-5 py-3 rounded-xl bg-gold-500 hover:bg-gold-450 disabled:bg-slate-800 text-navy-950 disabled:text-slate-500 font-bold text-xs flex items-center gap-1.5 transition-all shadow-md"
            >
              <Send className="h-3.5 w-3.5" />
              <span>Ask AI</span>
            </button>
          </form>
        </div>

        {/* Right Panel: Key Metrics + Citations Grounding Reference */}
        <div className="space-y-4">
          {/* Key Metrics Summary Card */}
          <div className="bg-navy-900 border border-navy-800 rounded-2xl p-5 shadow-xl space-y-3">
            <div className="flex items-center justify-between border-b border-navy-800 pb-2.5">
              <h3 className="text-xs font-bold uppercase tracking-wider text-white">
                Active Key Metrics
              </h3>
              <span className="text-[10px] font-mono text-gold-400 font-bold">{symbol}</span>
            </div>
            <div className="space-y-2.5 text-xs font-mono">
              <div className="flex justify-between items-center py-1 border-b border-navy-800/40">
                <span className="text-slate-400 font-sans">Market Price</span>
                <span className="text-white font-bold">{formatPerShare(quote?.current_price, currency)}</span>
              </div>
              <div className="flex justify-between items-center py-1 border-b border-navy-800/40">
                <span className="text-slate-400 font-sans">Trailing P/E</span>
                <span className="text-gold-300 font-bold">{formatMultiple(quote?.trailing_pe)}</span>
              </div>
              <div className="flex justify-between items-center py-1 border-b border-navy-800/40">
                <span className="text-slate-400 font-sans">Market Cap</span>
                <span className="text-slate-200">{formatFinancialValue(quote?.market_cap, currency)}</span>
              </div>
              <div className="flex justify-between items-center py-1 border-b border-navy-800/40">
                <span className="text-slate-400 font-sans">Operating Margin (OPM)</span>
                <span className="text-emerald-400 font-bold">{formatPercent(latestOpm)}</span>
              </div>
              <div className="flex justify-between items-center py-1 border-b border-navy-800/40">
                <span className="text-slate-400 font-sans">Net Margin</span>
                <span className="text-emerald-400 font-bold">{formatPercent(latestNetMargin)}</span>
              </div>
              <div className="flex justify-between items-center py-1 border-b border-navy-800/40">
                <span className="text-slate-400 font-sans">Return on Equity (ROE)</span>
                <span className="text-gold-300 font-bold">{formatPercent(latestRoe)}</span>
              </div>
              <div className="flex justify-between items-center py-1 border-b border-navy-800/40">
                <span className="text-slate-400 font-sans">Free Cash Flow</span>
                <span className="text-emerald-300 font-bold">{formatFinancialValue(latestFcf, currency)}</span>
              </div>
              <div className="flex justify-between items-center py-1">
                <span className="text-slate-400 font-sans">Debt-to-Equity</span>
                <span className="text-slate-200">{formatMultiple(latestDebtToEquity)}</span>
              </div>
            </div>
          </div>

          {/* Grounding Sources Card */}
          <div className="bg-navy-900 border border-navy-800 rounded-2xl p-5 shadow-xl space-y-3">
            <div className="flex items-center gap-2 border-b border-navy-800 pb-2.5">
              <Database className="h-3.5 w-3.5 text-cyan-400" />
              <h3 className="text-xs font-bold uppercase tracking-wider text-white">
                Grounded Knowledge Sources
              </h3>
            </div>
            <p className="text-[11px] text-slate-400 leading-relaxed">
              Synthesis answers are grounded directly in deterministic income statements, balance sheets, cash flows, and risk intelligence in Neon PostgreSQL.
            </p>
            <div className="space-y-1.5 pt-1">
              <div className="text-[10px] font-mono px-2.5 py-1.5 rounded bg-navy-950 border border-navy-800 text-slate-300 flex items-center justify-between">
                <span>Income Statements</span>
                <span className="text-emerald-400">Audited FY</span>
              </div>
              <div className="text-[10px] font-mono px-2.5 py-1.5 rounded bg-navy-950 border border-navy-800 text-slate-300 flex items-center justify-between">
                <span>Balance Sheets</span>
                <span className="text-emerald-400">Verified</span>
              </div>
              <div className="text-[10px] font-mono px-2.5 py-1.5 rounded bg-navy-950 border border-navy-800 text-slate-300 flex items-center justify-between">
                <span>Cash Flow Statements</span>
                <span className="text-emerald-400">Grounded</span>
              </div>
              <div className="text-[10px] font-mono px-2.5 py-1.5 rounded bg-navy-950 border border-navy-800 text-slate-300 flex items-center justify-between">
                <span>Risk Scorecard</span>
                <span className="text-cyan-400">4-Pillar Score</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  };

  // 5. STANDARD EXECUTIVE OVERVIEW WORKSPACE (?tab=overview)
  const renderOverviewWorkspace = () => (
    <div className="space-y-6">
      {/* 2. INSTITUTIONAL KPI SUMMARY STRIP (5-Tile Ribbon) */}
      {kpis.length > 0 && (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
          {kpis.slice(0, 5).map((kpi: any, i: number) => {
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
                className="bg-[#11141B] border border-white/[0.07] rounded-xl p-3.5 flex flex-col justify-between hover:border-white/[0.14] transition-all shadow-[0_1px_0_0_rgba(255,255,255,0.04)_inset]"
              >
                <div className="text-[10px] font-mono font-medium text-slate-400 uppercase tracking-wider truncate">{kpi.label}</div>
                <div className="text-base sm:text-lg font-bold font-mono text-white tabular-nums mt-1">
                  {displayVal}
                </div>
                {kpi.change && (
                  <div
                    className={`inline-flex items-center gap-1 mt-1 text-[10px] font-mono font-semibold px-1.5 py-0.2 rounded w-fit tabular-nums ${
                      kpi.is_positive
                        ? 'text-emerald-400 bg-emerald-500/10 border border-emerald-500/20'
                        : 'text-rose-400 bg-rose-500/10 border border-rose-500/20'
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

      {/* 2b. INTERACTIVE GRADIENT REVENUE & PROFITABILITY TRAJECTORY CHART */}
      {chartData && chartData.length > 0 && (
        <ChartRevenue data={chartData} ticker={symbol} currency={currency} />
      )}

      {/* 3. DETERMINISTIC SCENARIO CARDS (Trailing vs Base Case vs Best Case vs Worst Case) */}
      {scenarios && (
        <div className="bg-[#11141B] border border-white/[0.07] rounded-xl p-5 shadow-[0_1px_0_0_rgba(255,255,255,0.04)_inset]">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <ShieldCheck className="h-4 w-4 text-sky-400" />
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
            <div className="bg-[#0C0E14] border border-white/[0.08] rounded-xl p-4">
              <div className="text-[10px] uppercase font-bold text-slate-400 tracking-wider">Trailing Price</div>
              <div className="text-xl font-bold font-mono text-white mt-1 tabular-nums">
                {formatPerShare(scenarios.trailing_price, currency)}
              </div>
              <div className="text-[10px] text-slate-400 mt-1 font-mono">
                Multiple: <strong className="text-slate-200">{(quote?.trailing_pe ?? scenarios.trailing_pe) ? formatMultiple(quote?.trailing_pe ?? scenarios.trailing_pe) : 'N/A'}</strong>
              </div>
            </div>

            {/* Base Case */}
            {scenarios.base_case_price && (
              <div className="bg-[#0C0E14] border border-sky-500/20 rounded-xl p-4">
                <div className="text-[10px] uppercase font-bold text-sky-400 tracking-wider">Base Case Target</div>
                <div className="text-xl font-bold font-mono text-sky-300 mt-1 tabular-nums">
                  {formatPerShare(scenarios.base_case_price, currency)}
                </div>
                <div className="text-[10px] text-slate-400 mt-1 font-mono">
                  Median Growth & Valuation Multiple
                </div>
              </div>
            )}

            {/* Best Case */}
            <div className="bg-[#0C0E14] border border-emerald-500/30 rounded-xl p-4 relative overflow-hidden">
              <div className="flex items-center justify-between">
                <span className="text-[10px] uppercase font-bold text-emerald-400 tracking-wider">Best Case Target</span>
                {scenarios.upside_best_pct !== undefined && scenarios.upside_best_pct !== null && (
                  <span className="text-[10px] font-bold px-1.5 py-0.2 rounded bg-emerald-500/20 text-emerald-300 font-mono tabular-nums">
                    {scenarios.upside_best_pct > 0 ? `+${Number(scenarios.upside_best_pct).toFixed(2)}%` : `${Number(scenarios.upside_best_pct).toFixed(2)}%`}
                  </span>
                )}
              </div>
              <div className="text-xl font-bold font-mono text-emerald-300 mt-1 tabular-nums">
                {formatPerShare(scenarios.best_case_price, currency)}
              </div>
              <div className="text-[10px] text-slate-400 mt-1 font-mono">
                Optimistic multiple expansion & sales growth
              </div>
            </div>

            {/* Worst Case */}
            <div className="bg-[#0C0E14] border border-rose-500/30 rounded-xl p-4 relative overflow-hidden">
              <div className="flex items-center justify-between">
                <span className="text-[10px] uppercase font-bold text-rose-400 tracking-wider">Worst Case Floor</span>
                {scenarios.downside_worst_pct !== undefined && scenarios.downside_worst_pct !== null && (
                  <span className="text-[10px] font-bold px-1.5 py-0.2 rounded bg-rose-500/20 text-rose-300 font-mono tabular-nums">
                    {Number(scenarios.downside_worst_pct).toFixed(2)}%
                  </span>
                )}
              </div>
              <div className="text-xl font-bold font-mono text-rose-300 mt-1 tabular-nums">
                {formatPerShare(scenarios.worst_case_price, currency)}
              </div>
              <div className="text-[10px] text-slate-400 mt-1 font-mono">
                Margin compression & conservative multiple
              </div>
            </div>
          </div>
        </div>
      )}

      {/* 3b. AUTOMATIC SECTOR PEER COMPARISON TABLE */}
      {renderPeerComparison()}

      {/* 3c. LIVE COMPANY MARKET NEWS FEED */}
      <div className="bg-[#11141B] border border-white/[0.07] rounded-xl p-5 shadow-[0_1px_0_0_rgba(255,255,255,0.04)_inset] space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-white/[0.06] pb-3">
          <div className="flex items-center gap-2">
            <span className="h-5 px-2 rounded bg-sky-500/10 text-sky-400 border border-sky-500/20 text-[10px] font-bold uppercase tracking-wider flex items-center gap-1 font-mono">
              <Newspaper className="h-3 w-3" />
              Live News Feed
            </span>
            <h2 className="text-base font-bold text-white flex items-center gap-2">
              <span>Latest Market News & Intelligence</span>
              {loadingNews && <RefreshCw className="h-3.5 w-3.5 animate-spin text-sky-400" />}
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
            <RefreshCw className="h-5 w-5 animate-spin text-sky-400 mb-2" />
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
                className="bg-[#0C0E14] hover:bg-white/[0.03] border border-white/[0.06] hover:border-white/[0.14] rounded-xl p-4 flex flex-col justify-between transition-all group shadow-sm"
              >
                <div>
                  <div className="flex items-center justify-between gap-2 mb-2">
                    <span className="text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded bg-white/[0.04] border border-white/[0.08] text-sky-400 truncate max-w-[140px] font-mono">
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

                  <h3 className="text-xs font-semibold text-slate-200 group-hover:text-white leading-snug transition-colors line-clamp-2">
                    {item.title}
                  </h3>

                  {item.summary && (
                    <p className="text-[11px] text-slate-400 mt-1.5 line-clamp-2 leading-relaxed">
                      {item.summary}
                    </p>
                  )}
                </div>

                <div className="mt-3 pt-2 border-t border-white/[0.06] flex items-center justify-between text-[10px] text-slate-400 group-hover:text-sky-400">
                  <span className="font-medium">Read Full Article</span>
                  <ExternalLink className="h-3 w-3 text-slate-500 group-hover:text-sky-400 transition-colors" />
                </div>
              </a>
            ))}
          </div>
        )}
      </div>

      {/* 4. MAIN HIGH-DENSITY FINANCIAL STATEMENTS & TRENDS TABS */}
      <div className="bg-[#11141B] border border-white/[0.07] rounded-xl shadow-[0_1px_0_0_rgba(255,255,255,0.04)_inset] overflow-hidden">
        {/* Navigation Tab Bar */}
        <div className="flex items-center gap-1 border-b border-white/[0.06] px-4 py-2.5 overflow-x-auto bg-[#0C0E14]">
          <button
            onClick={() => setActiveTab('income')}
            className={`px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-all ${
              activeTab === 'income' ? 'bg-sky-500/10 text-sky-300 border border-sky-500/20' : 'text-slate-400 hover:text-white'
            }`}
          >
            Income Statement
          </button>
          <button
            onClick={() => setActiveTab('balance')}
            className={`px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-all ${
              activeTab === 'balance' ? 'bg-sky-500/10 text-sky-300 border border-sky-500/20' : 'text-slate-400 hover:text-white'
            }`}
          >
            Balance Sheet
          </button>
          <button
            onClick={() => setActiveTab('cashflow')}
            className={`px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-all ${
              activeTab === 'cashflow' ? 'bg-sky-500/10 text-sky-300 border border-sky-500/20' : 'text-slate-400 hover:text-white'
            }`}
          >
            Cash Flow
          </button>
          {trends && (
            <button
              onClick={() => setActiveTab('trends')}
              className={`px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                activeTab === 'trends' ? 'bg-sky-500/10 text-sky-300 border border-sky-500/20' : 'text-slate-400 hover:text-white'
              }`}
            >
              Trends & Horizons
            </button>
          )}
        </div>

        {/* High-Density Tab Content Tables with Sticky Metric Column & Tabular Nums */}
        <div className="overflow-x-auto">
          {activeTab === 'income' && (
            <table className="w-full text-xs text-left">
              <thead>
                <tr className="border-b border-white/[0.06] bg-[#0C0E14] text-slate-400 text-[11px] font-mono uppercase">
                  <th className="py-2.5 px-4 font-semibold sticky left-0 bg-[#0C0E14] z-20 border-r border-white/[0.06] min-w-[220px]">Line Item</th>
                  {displayPeriods.map((p: any, idx: number) => (
                    <th key={idx} className="py-2.5 px-4 text-right font-semibold min-w-[110px]">
                      {p.fiscal_period || (p.fiscal_year ? `FY${p.fiscal_year}` : 'FY')}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-white/[0.04] font-mono tabular-nums">
                <tr className="hover:bg-white/[0.03] transition-colors">
                  <td className="py-2.5 px-4 text-white font-sans font-semibold sticky left-0 bg-[#11141B] z-10 border-r border-white/[0.06]">Total Revenue</td>
                  {displayPeriods.map((p: any, idx: number) => (
                    <td key={idx} className="py-2.5 px-4 text-right text-slate-200">
                      {formatFinancialValue(p.revenue, currency)}
                    </td>
                  ))}
                </tr>
                <tr className="hover:bg-white/[0.03] transition-colors">
                  <td className="py-2.5 px-4 text-slate-300 font-sans sticky left-0 bg-[#11141B] z-10 border-r border-white/[0.06] pl-8">(-) Cost of Goods Sold</td>
                  {displayPeriods.map((p: any, idx: number) => {
                    const cogs = p.cost_of_revenue ?? (p.revenue != null && p.gross_profit != null ? p.revenue - p.gross_profit : null);
                    return (
                      <td key={idx} className="py-2.5 px-4 text-right text-rose-300/85">
                        {formatAccountingValue(cogs, currency, true)}
                      </td>
                    );
                  })}
                </tr>
                <tr className="bg-cyan-500/[0.03] hover:bg-cyan-500/[0.06] transition-colors">
                  <td className="py-2.5 px-4 text-cyan-200 font-sans font-semibold sticky left-0 bg-[#131b20] z-10 border-r border-white/[0.06]">= Gross Profit</td>
                  {displayPeriods.map((p: any, idx: number) => {
                    const gp = p.gross_profit ?? (p.revenue != null && p.cost_of_revenue != null ? p.revenue - p.cost_of_revenue : null);
                    return (
                      <td key={idx} className="py-2.5 px-4 text-right text-cyan-200 font-semibold">
                        {formatFinancialValue(gp, currency)}
                      </td>
                    );
                  })}
                </tr>
                <tr className="hover:bg-white/[0.03] transition-colors">
                  <td className="py-2.5 px-4 text-slate-300 font-sans sticky left-0 bg-[#11141B] z-10 border-r border-white/[0.06] pl-8">(-) Operating Expenses (excl. D&A)</td>
                  {displayPeriods.map((p: any, idx: number) => {
                    const rev = p.revenue;
                    const gp = p.gross_profit ?? (rev != null && p.cost_of_revenue != null ? rev - p.cost_of_revenue : null);
                    const da = Math.abs(p.depreciation_amortization || 0);
                    const eb = p.ebitda ?? (p.operating_income != null ? p.operating_income + da : null);
                    const opex = gp != null && eb != null ? gp - eb : (p.operating_expenses != null ? Math.max(0, p.operating_expenses - da) : null);
                    return (
                      <td key={idx} className="py-2.5 px-4 text-right text-rose-300/85">
                        {formatAccountingValue(opex, currency, true)}
                      </td>
                    );
                  })}
                </tr>
                <tr className="bg-sky-500/[0.03] hover:bg-sky-500/[0.06] transition-colors">
                  <td className="py-2.5 px-4 text-sky-200 font-sans font-bold sticky left-0 bg-[#141822] z-10 border-r border-white/[0.06]">= EBITDA</td>
                  {displayPeriods.map((p: any, idx: number) => {
                    const ebitdaVal = p.ebitda ?? (p.operating_income != null ? p.operating_income + Math.abs(p.depreciation_amortization || 0) : null);
                    return (
                      <td key={idx} className="py-2.5 px-4 text-right text-sky-200 font-bold">
                        {formatFinancialValue(ebitdaVal, currency)}
                      </td>
                    );
                  })}
                </tr>
                <tr className="hover:bg-white/[0.03] transition-colors">
                  <td className="py-2.5 px-4 text-slate-300 font-sans italic text-xs sticky left-0 bg-[#11141B] z-10 border-r border-white/[0.06] pl-8">EBITDA Margin %</td>
                  {displayPeriods.map((p: any, idx: number) => {
                    const ebitdaVal = p.ebitda ?? (p.operating_income != null ? p.operating_income + Math.abs(p.depreciation_amortization || 0) : null);
                    const em = p.ebitda_margin_pct ?? (ebitdaVal != null && p.revenue ? (ebitdaVal / p.revenue) * 100 : null);
                    return (
                      <td key={idx} className="py-2.5 px-4 text-right text-indigo-400 font-semibold">
                        {formatPercent(em)}
                      </td>
                    );
                  })}
                </tr>
                <tr className="hover:bg-white/[0.03] transition-colors">
                  <td className="py-2.5 px-4 text-slate-300 font-sans sticky left-0 bg-[#11141B] z-10 border-r border-white/[0.06] pl-8">(-) Depreciation & Amortization</td>
                  {displayPeriods.map((p: any, idx: number) => {
                    const da = p.depreciation_amortization != null ? Math.abs(p.depreciation_amortization) : null;
                    return (
                      <td key={idx} className="py-2.5 px-4 text-right text-rose-300/85">
                        {formatAccountingValue(da, currency, true)}
                      </td>
                    );
                  })}
                </tr>
                <tr className="bg-sky-500/[0.04] border-b border-white/[0.06] hover:bg-sky-500/[0.07] transition-colors">
                  <td className="py-2.5 px-4 text-sky-300 font-sans font-bold sticky left-0 bg-[#141822] z-10 border-r border-white/[0.06]">= Operating Income (EBIT)</td>
                  {displayPeriods.map((p: any, idx: number) => (
                    <td key={idx} className="py-2.5 px-4 text-right text-sky-200 font-bold">
                      {formatFinancialValue(p.operating_income, currency)}
                    </td>
                  ))}
                </tr>
                <tr className="hover:bg-white/[0.03] transition-colors">
                  <td className="py-2.5 px-4 text-slate-300 font-sans italic text-xs sticky left-0 bg-[#11141B] z-10 border-r border-white/[0.06] pl-8">Operating Margin (OPM %)</td>
                  {displayPeriods.map((p: any, idx: number) => {
                    const opmVal = p.opm_pct ?? (p.operating_income && p.revenue ? (p.operating_income / p.revenue) * 100 : null);
                    return (
                      <td key={idx} className="py-2.5 px-4 text-right text-sky-400 font-semibold">
                        {formatPercent(opmVal)}
                      </td>
                    );
                  })}
                </tr>
                <tr className="bg-emerald-500/[0.05] border-b border-white/[0.08] hover:bg-emerald-500/[0.08] transition-colors">
                  <td className="py-2.5 px-4 text-emerald-400 font-sans font-bold sticky left-0 bg-[#121c1a] z-10 border-r border-white/[0.06]">= Net Income</td>
                  {displayPeriods.map((p: any, idx: number) => (
                    <td key={idx} className="py-2.5 px-4 text-right text-emerald-300 font-bold">
                      {formatFinancialValue(p.net_income, currency)}
                    </td>
                  ))}
                </tr>
                <tr className="hover:bg-white/[0.03] transition-colors">
                  <td className="py-2.5 px-4 text-slate-300 font-sans sticky left-0 bg-[#11141B] z-10 border-r border-white/[0.06] pl-8">Diluted EPS</td>
                  {displayPeriods.map((p: any, idx: number) => (
                    <td key={idx} className="py-2.5 px-4 text-right text-slate-200">
                      {formatPerShare(p.eps, currency)}
                    </td>
                  ))}
                </tr>
              </tbody>
            </table>
          )}

          {activeTab === 'balance' && (
            <table className="w-full text-xs text-left">
              <thead>
                <tr className="border-b border-white/[0.06] bg-[#0C0E14] text-slate-400 text-[11px] font-mono uppercase">
                  <th className="py-2.5 px-4 font-semibold sticky left-0 bg-[#0C0E14] z-20 border-r border-white/[0.06] min-w-[220px]">Line Item</th>
                  {displayPeriods.map((p: any, idx: number) => (
                    <th key={idx} className="py-2.5 px-4 text-right font-semibold min-w-[110px]">
                      {p.fiscal_period || (p.fiscal_year ? `FY${p.fiscal_year}` : 'FY')}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-white/[0.04] font-mono tabular-nums">
                <tr className="hover:bg-white/[0.03] transition-colors">
                  <td className="py-2.5 px-4 text-slate-300 font-sans sticky left-0 bg-[#11141B] z-10 border-r border-white/[0.06] pl-8">Cash & Cash Equivalents</td>
                  {displayPeriods.map((p: any, idx: number) => (
                    <td key={idx} className="py-2.5 px-4 text-right text-slate-200">
                      {formatFinancialValue(p.cash_and_equivalents, currency)}
                    </td>
                  ))}
                </tr>
                <tr className="hover:bg-white/[0.03] transition-colors">
                  <td className="py-2.5 px-4 text-slate-300 font-sans sticky left-0 bg-[#11141B] z-10 border-r border-white/[0.06] pl-8">Current Assets</td>
                  {displayPeriods.map((p: any, idx: number) => (
                    <td key={idx} className="py-2.5 px-4 text-right text-slate-200">
                      {formatFinancialValue(p.current_assets, currency)}
                    </td>
                  ))}
                </tr>
                <tr className="hover:bg-white/[0.03] transition-colors">
                  <td className="py-2.5 px-4 text-slate-300 font-sans sticky left-0 bg-[#11141B] z-10 border-r border-white/[0.06] pl-8">Property, Plant & Equipment (Net)</td>
                  {displayPeriods.map((p: any, idx: number) => (
                    <td key={idx} className="py-2.5 px-4 text-right text-slate-200">
                      {formatFinancialValue(p.net_ppe, currency)}
                    </td>
                  ))}
                </tr>
                <tr className="bg-cyan-500/[0.03] hover:bg-cyan-500/[0.06] transition-colors">
                  <td className="py-2.5 px-4 text-cyan-200 font-sans font-bold sticky left-0 bg-[#131b20] z-10 border-r border-white/[0.06]">= Total Assets</td>
                  {displayPeriods.map((p: any, idx: number) => (
                    <td key={idx} className="py-2.5 px-4 text-right text-cyan-200 font-bold">
                      {formatFinancialValue(p.total_assets, currency)}
                    </td>
                  ))}
                </tr>
                <tr className="hover:bg-white/[0.03] transition-colors">
                  <td className="py-2.5 px-4 text-slate-300 font-sans sticky left-0 bg-[#11141B] z-10 border-r border-white/[0.06] pl-8">Current Liabilities</td>
                  {displayPeriods.map((p: any, idx: number) => (
                    <td key={idx} className="py-2.5 px-4 text-right text-slate-200">
                      {formatFinancialValue(p.current_liabilities, currency)}
                    </td>
                  ))}
                </tr>
                <tr className="hover:bg-white/[0.03] transition-colors">
                  <td className="py-2.5 px-4 text-slate-300 font-sans sticky left-0 bg-[#11141B] z-10 border-r border-white/[0.06] pl-8">Total Debt (Short + Long Term)</td>
                  {displayPeriods.map((p: any, idx: number) => (
                    <td key={idx} className="py-2.5 px-4 text-right text-slate-200">
                      {formatFinancialValue(p.total_debt, currency)}
                    </td>
                  ))}
                </tr>
                <tr className="hover:bg-white/[0.03] transition-colors">
                  <td className="py-2.5 px-4 text-slate-200 font-sans font-semibold sticky left-0 bg-[#11141B] z-10 border-r border-white/[0.06]">= Total Liabilities</td>
                  {displayPeriods.map((p: any, idx: number) => (
                    <td key={idx} className="py-2.5 px-4 text-right text-slate-200 font-semibold">
                      {formatFinancialValue(p.total_liabilities, currency)}
                    </td>
                  ))}
                </tr>
                <tr className="bg-sky-500/[0.04] border-b border-white/[0.08] hover:bg-sky-500/[0.07] transition-colors">
                  <td className="py-2.5 px-4 text-sky-300 font-sans font-bold sticky left-0 bg-[#141822] z-10 border-r border-white/[0.06]">= Total Stockholders' Equity</td>
                  {displayPeriods.map((p: any, idx: number) => (
                    <td key={idx} className="py-2.5 px-4 text-right text-sky-200 font-bold">
                      {formatFinancialValue(p.total_equity, currency)}
                    </td>
                  ))}
                </tr>
              </tbody>
            </table>
          )}

          {activeTab === 'cashflow' && (
            <table className="w-full text-xs text-left">
              <thead>
                <tr className="border-b border-white/[0.06] bg-[#0C0E14] text-slate-400 text-[11px] font-mono uppercase">
                  <th className="py-2.5 px-4 font-semibold sticky left-0 bg-[#0C0E14] z-20 border-r border-white/[0.06] min-w-[220px]">Line Item</th>
                  {displayPeriods.map((p: any, idx: number) => (
                    <th key={idx} className="py-2.5 px-4 text-right font-semibold min-w-[110px]">
                      {p.fiscal_period || (p.fiscal_year ? `FY${p.fiscal_year}` : 'FY')}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-white/[0.04] font-mono tabular-nums">
                <tr className="hover:bg-white/[0.03] transition-colors">
                  <td className="py-2.5 px-4 text-emerald-400 font-sans font-bold sticky left-0 bg-[#121c1a] z-10 border-r border-white/[0.06]">Cash Flow from Operations (OCF)</td>
                  {displayPeriods.map((p: any, idx: number) => (
                    <td key={idx} className="py-2.5 px-4 text-right text-emerald-300 font-bold">
                      {formatFinancialValue(p.operating_cash_flow, currency)}
                    </td>
                  ))}
                </tr>
                <tr className="hover:bg-white/[0.03] transition-colors">
                  <td className="py-2.5 px-4 text-slate-300 font-sans sticky left-0 bg-[#11141B] z-10 border-r border-white/[0.06] pl-8">Investing Cash Flow (CFI)</td>
                  {displayPeriods.map((p: any, idx: number) => (
                    <td key={idx} className="py-2.5 px-4 text-right text-slate-200">
                      {formatAccountingValue(p.investing_cash_flow, currency, false)}
                    </td>
                  ))}
                </tr>
                <tr className="hover:bg-white/[0.03] transition-colors">
                  <td className="py-2.5 px-4 text-slate-300 font-sans sticky left-0 bg-[#11141B] z-10 border-r border-white/[0.06] pl-8">(-) Capital Expenditures (CapEx)</td>
                  {displayPeriods.map((p: any, idx: number) => {
                    const capex = p.capital_expenditure != null ? Math.abs(p.capital_expenditure) : null;
                    return (
                      <td key={idx} className="py-2.5 px-4 text-right text-rose-300/85">
                        {formatAccountingValue(capex, currency, true)}
                      </td>
                    );
                  })}
                </tr>
                <tr className="hover:bg-white/[0.03] transition-colors">
                  <td className="py-2.5 px-4 text-slate-300 font-sans sticky left-0 bg-[#11141B] z-10 border-r border-white/[0.06] pl-8">Financing Cash Flow (CFF)</td>
                  {displayPeriods.map((p: any, idx: number) => (
                    <td key={idx} className="py-2.5 px-4 text-right text-slate-200">
                      {formatAccountingValue(p.financing_cash_flow, currency, false)}
                    </td>
                  ))}
                </tr>
                <tr className="bg-emerald-500/[0.05] border-b border-white/[0.08] hover:bg-emerald-500/[0.08] transition-colors">
                  <td className="py-2.5 px-4 text-emerald-400 font-sans font-bold sticky left-0 bg-[#121c1a] z-10 border-r border-white/[0.06]">= Free Cash Flow (FCF)</td>
                  {displayPeriods.map((p: any, idx: number) => (
                    <td key={idx} className="py-2.5 px-4 text-right text-emerald-300 font-bold">
                      {formatFinancialValue(p.free_cash_flow, currency)}
                    </td>
                  ))}
                </tr>
              </tbody>
            </table>
          )}

          {activeTab === 'trends' && trends && (
            <div className="p-4 sm:p-5 space-y-4">
              <div className="text-[11px] text-slate-400 font-mono uppercase tracking-wider mb-2">
                Compounded Growth & Margin Matrix Across Horizons
              </div>
              <table className="w-full text-xs text-left">
                <thead>
                  <tr className="border-b border-white/[0.06] bg-[#0C0E14] text-slate-400 text-[11px] font-mono uppercase">
                    <th className="py-2.5 px-4 font-semibold sticky left-0 bg-[#0C0E14] z-20 border-r border-white/[0.06] min-w-[220px]">Metric</th>
                    {(trends.headers || []).map((h: string, idx: number) => (
                      <th key={idx} className="py-2.5 px-4 text-right font-semibold min-w-[110px]">
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/[0.04] font-mono tabular-nums">
                  {Object.entries(trends.metrics || {}).map(([metricName, spanMap]: [string, any], mIdx: number) => (
                    <tr key={mIdx} className="hover:bg-white/[0.03] transition-colors">
                      <td className="py-2.5 px-4 text-white font-sans font-semibold capitalize sticky left-0 bg-[#11141B] z-10 border-r border-white/[0.06]">
                        {metricName.replace('_', ' ')}
                      </td>
                      {(trends.headers || []).map((h: string, hIdx: number) => {
                        const val = spanMap[h];
                        const isNM = val === 'N/M' || val === 'NM';
                        return (
                          <td key={hIdx} className="py-2.5 px-4 text-right text-slate-200">
                            {val !== undefined && val !== null ? (isNM ? 'N/M' : `${val}%`) : '—'}
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

      {/* 5. AI RESEARCH ANALYST DESK PREVIEW */}
      <div className="bg-[#11141B] border border-white/[0.07] rounded-xl p-5 shadow-[0_1px_0_0_rgba(255,255,255,0.04)_inset]">
        <div className="flex items-center justify-between mb-3 border-b border-white/[0.06] pb-3">
          <div className="flex items-center gap-2">
            <Sparkles className="h-4 w-4 text-sky-400" />
            <h3 className="text-sm font-bold text-white tracking-wide uppercase">
              AI Research Analyst Desk (Gemini Flash RAG)
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
              className="text-[11px] px-2.5 py-1 rounded-full bg-white/[0.04] hover:bg-white/[0.08] text-slate-300 hover:text-white border border-white/[0.08] transition-all font-sans"
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
                  ? 'bg-white/[0.06] text-white ml-8 border border-white/[0.08]'
                  : 'bg-[#0C0E14] text-slate-200 mr-4 border border-white/[0.06]'
              }`}
            >
              <div className="flex items-center justify-between mb-1">
                <span className="font-semibold text-[10px] uppercase text-sky-400 font-mono">
                  {msg.role === 'user' ? 'Analyst Inquiry' : 'Institutional Synthesis'}
                </span>
                <span className="text-[9px] text-slate-500 font-mono">
                  {msg.role === 'user' ? 'Prompt' : (msg.ai_mode === 'live' ? `${msg.model || 'Gemini Flash'} · Live AI` : 'Deterministic Synthesis')}
                </span>
              </div>
              {renderFormattedMessage(msg.content, msg.role === 'user')}

              {/* Grounded Citation Chips */}
              {msg.citations && msg.citations.length > 0 && (
                <div className="mt-2.5 pt-2 border-t border-white/[0.06] flex items-center gap-1.5 flex-wrap">
                  <span className="text-[10px] text-slate-400 font-medium">Sources:</span>
                  {msg.citations.map((cite, cIdx) => (
                    <span
                      key={cIdx}
                      className="px-2 py-0.5 text-[10px] font-mono bg-white/[0.04] border border-white/[0.08] text-slate-300 rounded hover:border-sky-500/40 transition-colors"
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
            <div className="p-3.5 rounded-xl text-xs bg-[#0C0E14] text-slate-400 mr-4 border border-white/[0.06] flex items-center gap-2">
              <RefreshCw className="h-3.5 w-3.5 text-sky-400 animate-spin" />
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
            className="flex-1 bg-[#0C0E14] border border-white/[0.08] rounded-xl px-4 py-2.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-sky-500/50 focus:ring-1 focus:ring-sky-500/30 transition-all font-sans"
          />
          <button
            type="submit"
            disabled={asking || !question.trim()}
            className="px-4 py-2.5 rounded-xl bg-sky-500 hover:bg-sky-400 disabled:bg-slate-800 text-white disabled:text-slate-500 font-bold text-xs flex items-center gap-1.5 transition-all shadow-md"
          >
            <Send className="h-3.5 w-3.5" />
            <span>Ask</span>
          </button>
        </form>
      </div>
    </div>
  );

  if (activeSection === 'ai-research') {
    return (
      <div className="space-y-6">
        {renderHeader()}
        {renderAiResearchWorkspace()}
      </div>
    );
  }

  if (activeSection === 'company-analysis') {
    return (
      <div className="space-y-6">
        {renderHeader()}
        {renderCompanyAnalysisWorkspace()}
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {renderHeader()}
      {renderOverviewWorkspace()}
    </div>
  );
};
