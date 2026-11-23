'use client';

import React, { useState, useEffect, useRef } from 'react';
import { useRouter } from 'next/navigation';
import { Search, Menu, X, Loader2, Upload, Database, Globe, Scale } from 'lucide-react';
import { API_BASE } from '@/lib/api';
import { normalizeExchange, formatPerShare } from '@/lib/formatters';

export interface CompanySearchResult {
  symbol: string;
  name: string;
  exchange: string;
  sector?: string;
  currency?: string;
  quote_type?: string;
  is_cached?: boolean;
  data_source?: string;
  price?: number | null;
  change_percent?: number | null;
}

export interface MarketIndexQuote {
  symbol: string;
  name: string;
  price: number;
  change: number;
  change_pct: number;
  currency: string;
}

const DEFAULT_INDICES: MarketIndexQuote[] = [
  { symbol: '^NSEI', name: 'NIFTY 50', price: 24180.80, change: 132.50, change_pct: 0.55, currency: 'INR' },
  { symbol: '^BSESN', name: 'BSE SENSEX', price: 79800.00, change: 245.30, change_pct: 0.31, currency: 'INR' },
  { symbol: '^NSEBANK', name: 'NIFTY BANK', price: 51200.00, change: 180.20, change_pct: 0.35, currency: 'INR' },
];

interface HeaderProps {
  currentTicker: string;
  onSelectTicker: (ticker: string) => void;
  onToggleMobileMenu?: () => void;
  isMobileMenuOpen?: boolean;
  onOpenImportCsv?: () => void;
}

export const Header: React.FC<HeaderProps> = ({
  currentTicker,
  onSelectTicker,
  onToggleMobileMenu,
  isMobileMenuOpen = false,
  onOpenImportCsv,
}) => {
  const router = useRouter();
  const [searchOpen, setSearchOpen] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [results, setResults] = useState<CompanySearchResult[]>([]);
  const [recentCompanies, setRecentCompanies] = useState<CompanySearchResult[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [selectedIndex, setSelectedIndex] = useState<number>(0);
  const [marketIndices, setMarketIndices] = useState<MarketIndexQuote[]>(DEFAULT_INDICES);
  const searchContainerRef = useRef<HTMLDivElement>(null);
  const searchInputRef = useRef<HTMLInputElement>(null);

  // Reset selectedIndex to 0 when results update
  useEffect(() => {
    setSelectedIndex(0);
  }, [results]);

  // Keyboard shortcut: Pressing '/' or 'Cmd+K' / 'Ctrl+K' focuses search
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      const activeTag = document.activeElement?.tagName;
      const isInputActive = activeTag === 'INPUT' || activeTag === 'TEXTAREA';

      if (e.key === '/' && !isInputActive) {
        e.preventDefault();
        searchInputRef.current?.focus();
        setSearchOpen(true);
        if (recentCompanies.length === 0) {
          loadRecentCompanies();
        }
      } else if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        searchInputRef.current?.focus();
        setSearchOpen(true);
        if (recentCompanies.length === 0) {
          loadRecentCompanies();
        }
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [recentCompanies]);

  // Close search dropdown on click outside
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (searchContainerRef.current && !searchContainerRef.current.contains(e.target as Node)) {
        setSearchOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // 0. Live Market Indices Polling (NIFTY 50, S&P 500, NASDAQ)
  useEffect(() => {
    let isMounted = true;
    const fetchIndices = async () => {
      try {
        const res = await fetch(`${API_BASE}/market/indices`);
        if (res.ok) {
          const json = await res.json();
          if (isMounted && Array.isArray(json.indices) && json.indices.length > 0) {
            setMarketIndices(json.indices);
          }
        }
      } catch {
        // Graceful silent fallback to default benchmarks
      }
    };

    fetchIndices();
    const interval = setInterval(fetchIndices, 60000); // 1-minute live poll
    return () => {
      isMounted = false;
      clearInterval(interval);
    };
  }, []);

  // 1. Fetch featured top NSE companies when search box opens with empty query
  const loadRecentCompanies = async () => {
    try {
      const res = await fetch(`${API_BASE}/companies/search`);
      if (res.ok) {
        const data = await res.json();
        const mapped: CompanySearchResult[] = (data || []).map((c: any) => ({
          symbol: c.symbol || c.ticker,
          name: c.name || c.company_name,
          exchange: normalizeExchange(c.exchange, c.symbol),
          sector: c.sector || 'Nifty 50',
          currency: c.currency || 'INR',
          is_cached: true,
          data_source: c.data_source || 'neon_db',
          price: c.price,
          change_percent: c.change_percent,
        }));
        setRecentCompanies(mapped);
        if (!searchTerm.trim()) {
          setResults(mapped);
        }
      }
    } catch {
      // Gracefully silent if backend starting up
    }
  };

  // 2. Debounced (250ms) Live Search across Indian (NSE/BSE) and Global markets
  useEffect(() => {
    const trimmed = searchTerm.trim();

    if (trimmed.length < 2) {
      if (recentCompanies.length > 0) {
        setResults(recentCompanies);
      }
      setIsSearching(false);
      return;
    }

    setIsSearching(true);
    let isCancelled = false;

    const timer = setTimeout(async () => {
      try {
        const query = encodeURIComponent(trimmed);
        const res = await fetch(`${API_BASE}/companies/search?q=${query}&limit=15`);
        if (res.ok) {
          const data = await res.json();
          if (!isCancelled && Array.isArray(data)) {
            setResults(data);
          }
        }
      } catch (err) {
        console.warn('Live ticker search error:', err);
      } finally {
        if (!isCancelled) {
          setIsSearching(false);
        }
      }
    }, 250);

    return () => {
      isCancelled = true;
      clearTimeout(timer);
    };
  }, [searchTerm, recentCompanies]);

  const handleSelect = (item: CompanySearchResult) => {
    const sym = item.symbol;
    if (typeof window !== 'undefined') {
      try {
        localStorage.setItem('finsight_last_company', sym);
      } catch {}
    }
    onSelectTicker(sym);
    setSearchOpen(false);
    setSearchTerm('');
    try {
      router.push(`/company/${encodeURIComponent(sym)}`);
    } catch {}
  };

  return (
    <div className="sticky top-0 z-30 flex flex-col w-full">
      {/* TIER 1: Slim Institutional Market Tape (h-8, bg-[#06080B], border-b border-white/[0.06]) */}
      <div className="h-8 bg-[#06080B] border-b border-white/[0.06] px-4 sm:px-6 flex items-center justify-between text-xs select-none">
        <div className="flex items-center gap-4 sm:gap-6 overflow-x-auto no-scrollbar py-0.5">
          {marketIndices.map((idx) => {
            const isPos = idx.change_pct >= 0;
            return (
              <div key={idx.symbol} className="flex items-center gap-2 whitespace-nowrap text-[11px]">
                <span className="text-slate-400 font-medium tracking-tight">{idx.name}</span>
                <span className="font-mono text-slate-200 tabular-nums">
                  {idx.price.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                </span>
                <span
                  className={`inline-flex items-center px-1.5 py-0.2 rounded text-[10px] font-mono font-medium tabular-nums ${
                    isPos
                      ? 'text-emerald-400 bg-emerald-500/10 border border-emerald-500/20'
                      : 'text-rose-400 bg-rose-500/10 border border-rose-500/20'
                  }`}
                >
                  {isPos ? '+' : ''}
                  {idx.change_pct.toFixed(2)}%
                </span>
              </div>
            );
          })}
        </div>

        {/* Live indicator on far right */}
        <div className="hidden sm:flex items-center gap-1.5 text-[10px] font-mono text-slate-400 pl-4 border-l border-white/[0.06] flex-shrink-0">
          <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse" />
          <span className="text-emerald-400 font-semibold uppercase tracking-wider">Live Markets</span>
        </div>
      </div>

      {/* TIER 2: Main Command Bar (h-14, bg-[#090B0F]/95 backdrop-blur-md) */}
      <header className="h-14 bg-[#090B0F]/95 backdrop-blur-md border-b border-white/[0.06] px-4 sm:px-6 flex items-center justify-between">
        {/* Left: Mobile Toggle & Wide Spotlight Search */}
        <div className="flex items-center gap-3 flex-1 min-w-0 pr-4" ref={searchContainerRef}>
          {onToggleMobileMenu && (
            <button
              onClick={onToggleMobileMenu}
              aria-label="Toggle Navigation Menu"
              className="lg:hidden p-1.5 rounded-md text-slate-400 hover:text-white hover:bg-white/[0.04] border border-white/[0.08] transition-colors"
            >
              {isMobileMenuOpen ? <X className="h-4 w-4" /> : <Menu className="h-4 w-4" />}
            </button>
          )}

          {/* Wide Spotlight Search Input */}
          <div className="relative w-full max-w-md sm:max-w-lg">
            <div className="relative flex items-center">
              <Search className="absolute left-3 h-3.5 w-3.5 text-slate-400 pointer-events-none" />
              <input
                ref={searchInputRef}
                type="text"
                value={searchTerm}
                onFocus={() => {
                  setSearchOpen(true);
                  if (recentCompanies.length === 0) {
                    loadRecentCompanies();
                  }
                }}
                onChange={(e) => setSearchTerm(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'ArrowDown') {
                    e.preventDefault();
                    if (!searchOpen) {
                      setSearchOpen(true);
                    } else if (results.length > 0) {
                      setSelectedIndex((prev) => (prev + 1) % results.length);
                    }
                  } else if (e.key === 'ArrowUp') {
                    e.preventDefault();
                    if (!searchOpen) {
                      setSearchOpen(true);
                    } else if (results.length > 0) {
                      setSelectedIndex((prev) => (prev - 1 + results.length) % results.length);
                    }
                  } else if (e.key === 'Enter') {
                    if (results.length > 0 && searchOpen) {
                      e.preventDefault();
                      const target = results[selectedIndex >= 0 && selectedIndex < results.length ? selectedIndex : 0];
                      if (target) handleSelect(target);
                    }
                  } else if (e.key === 'Escape') {
                    setSearchOpen(false);
                    searchInputRef.current?.blur();
                  }
                }}
                placeholder="Search any of 2,000+ Indian NSE companies (e.g., RELIANCE, TCS, ZOMATO, M&M)..."
                className="w-full bg-[#11141B] border border-white/[0.08] hover:border-white/[0.14] focus:border-sky-500/60 focus:ring-1 focus:ring-sky-500/30 rounded-lg pl-9 pr-14 py-2 text-xs text-white placeholder-slate-500 transition-all font-sans"
              />

              {/* Right Shortcut Badge / Loader */}
              <div className="absolute right-2.5 flex items-center gap-1 pointer-events-none">
                {isSearching ? (
                  <Loader2 className="h-3.5 w-3.5 text-sky-400 animate-spin" />
                ) : (
                  <kbd className="hidden sm:inline-flex items-center px-1.5 py-0.5 text-[10px] font-mono font-medium text-slate-400 bg-white/[0.04] border border-white/[0.08] rounded">
                    /
                  </kbd>
                )}
              </div>
            </div>

            {/* Dropdown Results */}
            {searchOpen && (
              <div className="absolute left-0 mt-2 w-full sm:w-[460px] bg-[#11141B] border border-white/[0.1] rounded-xl shadow-2xl z-50 overflow-hidden py-1 max-h-84 overflow-y-auto backdrop-blur-xl">
                <div className="px-3.5 py-2 text-[10px] uppercase tracking-wider text-slate-400 font-semibold border-b border-white/[0.06] flex justify-between items-center bg-[#0C0E14]">
                  <span>{searchTerm.trim().length >= 2 ? 'All-India NSE Equities' : 'Featured NSE Leaders'}</span>
                  <span className="text-sky-400 font-mono text-[9px] flex items-center gap-1">
                    <Globe className="h-2.5 w-2.5" /> NSE LIVE
                  </span>
                </div>

                {results.length > 0 ? (
                  results.map((item, idx) => {
                    const isSelected = currentTicker.toUpperCase() === item.symbol.toUpperCase();
                    const isHighlighted = idx === selectedIndex;
                    const exch = normalizeExchange(item.exchange, item.symbol);
                    const isIndian = exch === 'NSE' || exch === 'BSE';

                    return (
                      <button
                        key={`${item.symbol}-${item.exchange}`}
                        onClick={() => handleSelect(item)}
                        onMouseEnter={() => setSelectedIndex(idx)}
                        className={`w-full px-3.5 py-2.5 flex items-center justify-between text-left text-xs transition-colors border-b border-white/[0.03] last:border-0 ${
                          isHighlighted
                            ? 'bg-white/[0.06] text-white'
                            : isSelected
                            ? 'bg-sky-500/10 text-sky-300'
                            : 'text-slate-300 hover:bg-white/[0.03]'
                        }`}
                      >
                        <div className="pr-2 min-w-0 flex-1">
                          <div className="flex items-center gap-2 mb-0.5">
                            <span className="font-semibold text-white truncate max-w-[240px]">
                              {item.name}
                            </span>
                            {item.is_cached && (
                              <span className="px-1.5 py-0.5 text-[9px] font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 rounded flex items-center gap-1">
                                <Database className="h-2 w-2" /> Neon DB
                              </span>
                            )}
                          </div>
                          <div className="flex items-center gap-2 text-[10px] text-slate-400 font-mono">
                            <span className="font-bold text-sky-400">{item.symbol}</span>
                            <span>•</span>
                            <span className="truncate max-w-[130px]">{item.sector || 'General'}</span>
                            {item.price !== undefined && item.price !== null && (
                              <>
                                <span>•</span>
                                <span className="text-white font-semibold tabular-nums">
                                  {formatPerShare(item.price, item.currency)}
                                </span>
                                {item.change_percent !== undefined && item.change_percent !== null && (
                                  <span
                                    className={`tabular-nums ${
                                      item.change_percent >= 0 ? 'text-emerald-400' : 'text-rose-400'
                                    }`}
                                  >
                                    ({item.change_percent >= 0 ? '+' : ''}
                                    {Number(item.change_percent).toFixed(2)}%)
                                  </span>
                                )}
                              </>
                            )}
                          </div>
                        </div>

                        {/* Exchange Badge */}
                        <div className="flex-shrink-0">
                          <span
                            className={`px-2 py-0.5 text-[10px] font-mono font-bold rounded tracking-wider ${
                              isIndian
                                ? 'bg-orange-500/15 text-orange-400 border border-orange-500/30'
                                : exch === 'NASDAQ'
                                ? 'bg-sky-500/15 text-sky-400 border border-sky-500/30'
                                : exch === 'NYSE'
                                ? 'bg-blue-500/15 text-blue-400 border border-blue-500/30'
                                : 'bg-slate-700/40 text-slate-300 border border-slate-600/30'
                            }`}
                          >
                            {exch}
                          </span>
                        </div>
                      </button>
                    );
                  })
                ) : (
                  <div className="px-4 py-6 text-xs text-slate-400 text-center">
                    {isSearching ? (
                      <div className="flex items-center justify-center gap-2 text-sky-400">
                        <Loader2 className="h-4 w-4 animate-spin" />
                        <span>Searching 2,000+ Indian NSE equities...</span>
                      </div>
                    ) : (
                      <span>No matching companies found. Try typing an NSE ticker (e.g. RELIANCE.NS, TCS.NS, INFY.NS, M&amp;M.NS).</span>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>

        {/* Right Actions: Compare & Import CSV & Terminal Status */}
        <div className="flex items-center gap-2.5 sm:gap-3 flex-shrink-0">
          {/* Compare Equities Button */}
          <button
            onClick={() => {
              router.push(`/compare?a=${encodeURIComponent(currentTicker)}&b=BERGEPAINT.NS`);
            }}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white/[0.04] hover:bg-white/[0.08] text-slate-300 hover:text-white border border-white/[0.08] text-xs font-medium transition-all shadow-sm"
            title="Side-by-side equity comparison"
          >
            <Scale className="h-3.5 w-3.5 text-sky-400" />
            <span className="hidden sm:inline">Compare</span>
          </button>

          {/* Import CSV Button */}
          {onOpenImportCsv && (
            <button
              onClick={onOpenImportCsv}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white/[0.04] hover:bg-white/[0.08] text-slate-300 hover:text-white border border-white/[0.08] text-xs font-medium transition-all shadow-sm"
              title="Import Screener.in or FinSight CSV statement"
            >
              <Upload className="h-3.5 w-3.5 text-emerald-400" />
              <span className="hidden sm:inline">Import CSV</span>
            </button>
          )}

          {/* Clean Terminal Pill */}
          <div className="flex items-center gap-2 pl-2 sm:pl-3 border-l border-white/[0.06] flex-shrink-0">
            <div className="h-7 w-7 rounded-md bg-white/[0.04] border border-white/[0.08] flex items-center justify-center text-sky-400 font-mono font-bold text-xs shadow-inner">
              FS
            </div>
            <div className="hidden md:block text-left">
              <div className="text-xs font-medium text-slate-200 leading-tight">Terminal</div>
              <div className="text-[10px] text-slate-400 font-mono">Institutional</div>
            </div>
          </div>
        </div>
      </header>
    </div>
  );
};
