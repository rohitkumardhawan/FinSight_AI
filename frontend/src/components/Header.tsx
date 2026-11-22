'use client';

import React, { useState, useEffect, useRef } from 'react';
import { useRouter } from 'next/navigation';
import { Search, AlertCircle, Menu, X, Loader2, Upload, Database, Globe } from 'lucide-react';
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
  const searchContainerRef = useRef<HTMLDivElement>(null);

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
          change_percent: c.change_percent
        }));
        setRecentCompanies(mapped);
        if (!searchTerm.trim()) {
          setResults(mapped);
        }
      }
    } catch (err) {
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
    // Navigate cleanly
    try {
      router.push(`/company/${encodeURIComponent(sym)}`);
    } catch {
      // Stay on page
    }
  };

  return (
    <header className="h-16 bg-navy-900 border-b border-navy-800 px-4 sm:px-6 flex items-center justify-between sticky top-0 z-30">
      {/* Mobile Menu Toggle & Search Bar */}
      <div className="flex items-center gap-3" ref={searchContainerRef}>
        {onToggleMobileMenu && (
          <button
            onClick={onToggleMobileMenu}
            aria-label="Toggle Navigation Menu"
            className="md:hidden p-1.5 rounded-lg bg-navy-800 text-slate-300 hover:text-white border border-navy-700"
          >
            {isMobileMenuOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
          </button>
        )}

        <div className="relative w-64 sm:w-96">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
            <input
              type="text"
              value={searchTerm}
              onFocus={() => {
                setSearchOpen(true);
                if (recentCompanies.length === 0) {
                  loadRecentCompanies();
                }
              }}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder={`Search Indian (NSE/BSE) or Global company/ticker...`}
              className="w-full bg-navy-950 border border-navy-700 rounded-lg pl-9 pr-8 py-2 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-gold-500/50 focus:ring-1 focus:ring-gold-500/30 transition-all"
            />
            {isSearching && (
              <Loader2 className="absolute right-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-gold-400 animate-spin" />
            )}
          </div>

          {/* Dropdown Results */}
          {searchOpen && (
            <>
              <div
                className="fixed inset-0 z-40"
                onClick={() => setSearchOpen(false)}
              />
              <div className="absolute left-0 mt-1.5 w-full sm:w-[420px] bg-navy-900 border border-navy-700 rounded-xl shadow-2xl z-50 overflow-hidden py-1 max-h-80 overflow-y-auto">
                <div className="px-3.5 py-2 text-[10px] uppercase tracking-wider text-slate-400 font-semibold border-b border-navy-800 flex justify-between items-center bg-navy-950/70">
                  <span>{searchTerm.trim().length >= 2 ? 'Global & Indian Equities' : 'Recent & Cached Companies'}</span>
                  <span className="text-emerald-400 font-mono text-[9px] flex items-center gap-1">
                    <Globe className="h-2.5 w-2.5" /> LIVE SEARCH
                  </span>
                </div>

                {results.length > 0 ? (
                  results.map((item) => {
                    const isSelected = currentTicker.toUpperCase() === item.symbol.toUpperCase();
                    const exch = normalizeExchange(item.exchange, item.symbol);
                    const isIndian = exch === 'NSE' || exch === 'BSE';
                    
                    return (
                      <button
                        key={`${item.symbol}-${item.exchange}`}
                        onClick={() => handleSelect(item)}
                        className={`w-full px-3.5 py-2.5 flex items-center justify-between text-left text-xs transition-colors hover:bg-navy-800/90 border-b border-navy-800/40 last:border-0 ${
                          isSelected ? 'bg-navy-850/80 text-gold-400' : 'text-slate-300'
                        }`}
                      >
                        <div className="pr-2 min-w-0 flex-1">
                          <div className="flex items-center gap-2 mb-0.5">
                            <span className="font-semibold text-white truncate max-w-[220px]">
                              {item.name}
                            </span>
                            {item.is_cached && (
                              <span className="px-1.5 py-0.5 text-[9px] font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 rounded flex items-center gap-1">
                                <Database className="h-2 w-2" /> Neon DB
                              </span>
                            )}
                          </div>
                          <div className="flex items-center gap-2 text-[10px] text-slate-400 font-mono">
                            <span className="font-bold text-gold-400/90">{item.symbol}</span>
                            <span>•</span>
                            <span className="truncate max-w-[120px]">{item.sector || 'General'}</span>
                            {item.price !== undefined && item.price !== null && (
                              <>
                                <span>•</span>
                                <span className="text-white font-semibold">{formatPerShare(item.price, item.currency)}</span>
                                {item.change_percent !== undefined && item.change_percent !== null && (
                                  <span className={item.change_percent >= 0 ? 'text-emerald-400' : 'text-rose-400'}>
                                    ({item.change_percent >= 0 ? '+' : ''}{Number(item.change_percent).toFixed(2)}%)
                                  </span>
                                )}
                              </>
                            )}
                          </div>
                        </div>

                        {/* Exchange Badge */}
                        <div className="flex-shrink-0">
                          <span
                            className={`px-2 py-0.5 text-[10px] font-bold rounded tracking-wider ${
                              isIndian
                                ? 'bg-orange-500/15 text-orange-400 border border-orange-500/30'
                                : exch === 'NASDAQ'
                                ? 'bg-cyan-500/15 text-cyan-400 border border-cyan-500/30'
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
                      <div className="flex items-center justify-center gap-2 text-gold-400">
                        <Loader2 className="h-4 w-4 animate-spin" />
                        <span>Searching global financial markets...</span>
                      </div>
                    ) : (
                      <span>No matching companies found. Try typing a ticker (e.g. ASIANPAINT.NS, TCS.NS, AAPL).</span>
                    )}
                  </div>
                )}
              </div>
            </>
          )}
        </div>

        {/* Optional Import CSV Button */}
        {onOpenImportCsv && (
          <button
            onClick={onOpenImportCsv}
            className="hidden sm:flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-navy-800 hover:bg-navy-750 text-slate-200 border border-navy-700 hover:border-gold-500/40 text-xs font-medium transition-all shadow-sm"
            title="Import Screener.in or FinSight CSV statement"
          >
            <Upload className="h-3.5 w-3.5 text-gold-400" />
            <span>Import CSV</span>
          </button>
        )}
      </div>

      {/* Center Market Pulse (Hidden on mobile/tablet) */}
      <div className="hidden xl:flex items-center gap-6 text-xs text-slate-400">
        <div className="flex items-center gap-2">
          <span className="text-slate-400 font-medium">NIFTY 50</span>
          <span className="text-emerald-400 font-semibold">24,180.80 (+0.55%)</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-slate-400 font-medium">S&P 500</span>
          <span className="text-emerald-400 font-semibold">5,983.25 (+0.42%)</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-slate-400 font-medium">NASDAQ</span>
          <span className="text-emerald-400 font-semibold">19,081.40 (+0.68%)</span>
        </div>
      </div>

      {/* Right Actions & Status Badges */}
      <div className="flex items-center gap-3">
        {/* Live Neon & FastAPI Engine Indicator */}
        <div className="flex items-center gap-1.5 px-2.5 sm:px-3 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/30 text-emerald-300 text-[10px] sm:text-[11px] font-semibold tracking-wide">
          <div className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse" />
          <span>NEON PGVECTOR LIVE</span>
        </div>

        {/* User Pill */}
        <div className="flex items-center gap-2 pl-3 border-l border-navy-800">
          <div className="h-8 w-8 rounded-full bg-gradient-to-tr from-navy-700 to-navy-600 border border-navy-600 flex items-center justify-center text-gold-accent font-semibold text-xs shadow-inner">
            FS
          </div>
          <div className="hidden sm:block text-left">
            <div className="text-xs font-semibold text-white leading-tight">Analyst Desk</div>
            <div className="text-[10px] text-slate-400">Phase 4 Active</div>
          </div>
        </div>
      </div>
    </header>
  );
};
