'use client';

import React, { useState, useEffect, useRef, useMemo } from 'react';
import { Search, X, Loader2, Building2, Check } from 'lucide-react';
import { API_BASE } from '@/lib/api';
import { normalizeExchange, formatFinancialValue } from '@/lib/formatters';

export interface CompanyAutocompleteItem {
  symbol: string;
  name: string;
  exchange?: string;
  sector?: string;
  currency?: string;
  price?: number | null;
  change_percent?: number | null;
  market_cap?: number | null;
  is_cached?: boolean;
}

// Module-level global index cache so both inputs share preloaded data
let globalCompanyCache: CompanyAutocompleteItem[] | null = null;
let globalPreloadPromise: Promise<CompanyAutocompleteItem[]> | null = null;

async function preloadCompanyIndex(): Promise<CompanyAutocompleteItem[]> {
  if (globalCompanyCache && globalCompanyCache.length > 0) {
    return globalCompanyCache;
  }
  if (globalPreloadPromise) {
    return globalPreloadPromise;
  }

  globalPreloadPromise = (async () => {
    try {
      // Fetch both featured/search and company listing in parallel
      const [searchRes, listRes] = await Promise.allSettled([
        fetch(`${API_BASE}/companies/search?limit=15`),
        fetch(`${API_BASE}/companies?limit=100`),
      ]);

      const mergedMap = new Map<string, CompanyAutocompleteItem>();

      if (searchRes.status === 'fulfilled' && searchRes.value.ok) {
        const data = await searchRes.value.json();
        if (Array.isArray(data)) {
          data.forEach((c: any) => {
            const sym = (c.symbol || c.ticker || '').trim().toUpperCase();
            if (sym) {
              mergedMap.set(sym, {
                symbol: sym,
                name: c.name || c.company_name || sym,
                exchange: normalizeExchange(c.exchange, sym),
                sector: c.sector || 'NSE Equities',
                currency: c.currency || 'INR',
                price: c.price,
                change_percent: c.change_percent,
                market_cap: c.market_cap,
                is_cached: true,
              });
            }
          });
        }
      }

      if (listRes.status === 'fulfilled' && listRes.value.ok) {
        const data = await listRes.value.json();
        if (Array.isArray(data)) {
          data.forEach((c: any) => {
            const sym = (c.symbol || c.ticker || '').trim().toUpperCase();
            if (sym && !mergedMap.has(sym)) {
              mergedMap.set(sym, {
                symbol: sym,
                name: c.company_name || c.name || sym,
                exchange: normalizeExchange(c.exchange, sym),
                sector: c.sector || 'NSE Equities',
                currency: c.currency || 'INR',
                price: c.price,
                change_percent: c.change_percent,
                market_cap: c.market_cap,
                is_cached: true,
              });
            }
          });
        }
      }

      globalCompanyCache = Array.from(mergedMap.values());
      return globalCompanyCache;
    } catch (err) {
      console.debug('Failed to preload company index:', err);
      return [];
    } finally {
      globalPreloadPromise = null;
    }
  })();

  return globalPreloadPromise;
}

interface TickerAutocompleteProps {
  label: string;
  sublabel?: string;
  selectedTicker: string;
  selectedName?: string;
  placeholder?: string;
  onSelect: (company: CompanyAutocompleteItem) => void;
  disabled?: boolean;
}

export const TickerAutocomplete: React.FC<TickerAutocompleteProps> = ({
  label,
  sublabel,
  selectedTicker,
  selectedName,
  placeholder = 'Search by company name or ticker (e.g. HDFC, AXI, TATAMOTORS)...',
  onSelect,
  disabled = false,
}) => {
  const [query, setQuery] = useState<string>('');
  const [isOpen, setIsOpen] = useState<boolean>(false);
  const [isLoadingServer, setIsLoadingServer] = useState<boolean>(false);
  const [highlightedIndex, setHighlightedIndex] = useState<number>(0);
  const [serverResults, setServerResults] = useState<CompanyAutocompleteItem[]>([]);
  const [cachedCompanies, setCachedCompanies] = useState<CompanyAutocompleteItem[]>([]);

  const containerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const debounceTimerRef = useRef<NodeJS.Timeout | null>(null);

  // Preload company index on mount
  useEffect(() => {
    let active = true;
    preloadCompanyIndex().then((list) => {
      if (active && list.length > 0) {
        setCachedCompanies(list);
      }
    });
    return () => {
      active = false;
    };
  }, []);

  // Close dropdown on outside click
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Instant fuzzy filter across client-cached companies (<10ms)
  const localMatches = useMemo(() => {
    const cleanQ = query.trim().toLowerCase();
    if (!cleanQ) {
      return cachedCompanies.slice(0, 8);
    }

    const qNoNS = cleanQ.endsWith('.ns') ? cleanQ.slice(0, -3) : cleanQ;

    const scored = cachedCompanies
      .map((c) => {
        const sym = c.symbol.toLowerCase();
        const symNoNS = sym.endsWith('.ns') ? sym.slice(0, -3) : sym;
        const name = c.name.toLowerCase();
        const sector = (c.sector || '').toLowerCase();

        let score = 999;
        if (sym === cleanQ || symNoNS === cleanQ) score = 0;
        else if (sym.startsWith(cleanQ) || symNoNS.startsWith(cleanQ)) score = 1;
        else if (name.startsWith(cleanQ)) score = 2;
        else if (sym.includes(cleanQ) || symNoNS.includes(qNoNS)) score = 3;
        else if (name.includes(cleanQ)) score = 4;
        else if (sector.includes(cleanQ)) score = 5;

        return { company: c, score };
      })
      .filter((item) => item.score < 999)
      .sort((a, b) => a.score - b.score);

    return scored.slice(0, 8).map((item) => item.company);
  }, [query, cachedCompanies]);

  // Debounced (200ms) server fallback
  useEffect(() => {
    const cleanQ = query.trim();
    if (!cleanQ || cleanQ.length < 2) {
      setServerResults([]);
      setIsLoadingServer(false);
      return;
    }

    if (debounceTimerRef.current) {
      clearTimeout(debounceTimerRef.current);
    }

    debounceTimerRef.current = setTimeout(async () => {
      setIsLoadingServer(true);
      try {
        const res = await fetch(`${API_BASE}/companies/search?q=${encodeURIComponent(cleanQ)}&limit=8`);
        if (res.ok) {
          const data = await res.json();
          if (Array.isArray(data)) {
            const mapped: CompanyAutocompleteItem[] = data.map((c: any) => ({
              symbol: (c.symbol || c.ticker || '').trim().toUpperCase(),
              name: c.name || c.company_name || c.symbol,
              exchange: normalizeExchange(c.exchange, c.symbol),
              sector: c.sector || 'NSE Equities',
              currency: c.currency || 'INR',
              price: c.price,
              change_percent: c.change_percent,
              market_cap: c.market_cap,
              is_cached: c.is_cached ?? true,
            }));
            setServerResults(mapped);

            // Merge new companies into module cache
            if (globalCompanyCache) {
              const symSet = new Set(globalCompanyCache.map((x) => x.symbol));
              mapped.forEach((m) => {
                if (!symSet.has(m.symbol)) {
                  globalCompanyCache?.push(m);
                  symSet.add(m.symbol);
                }
              });
            }
          }
        }
      } catch (err) {
        console.debug('Autocomplete server search error:', err);
      } finally {
        setIsLoadingServer(false);
      }
    }, 200);

    return () => {
      if (debounceTimerRef.current) {
        clearTimeout(debounceTimerRef.current);
      }
    };
  }, [query]);

  // Combined suggestions (Local immediate matches + Server results)
  const suggestions = useMemo(() => {
    const map = new Map<string, CompanyAutocompleteItem>();
    localMatches.forEach((c) => map.set(c.symbol, c));
    serverResults.forEach((c) => {
      if (!map.has(c.symbol)) {
        map.set(c.symbol, c);
      }
    });
    return Array.from(map.values()).slice(0, 8);
  }, [localMatches, serverResults]);

  // Reset highlighted index when suggestions change
  useEffect(() => {
    setHighlightedIndex(0);
  }, [suggestions]);

  const handleSelectCompany = (comp: CompanyAutocompleteItem) => {
    onSelect(comp);
    setQuery('');
    setIsOpen(false);
    inputRef.current?.blur();
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (!isOpen && (e.key === 'ArrowDown' || e.key === 'Enter')) {
      setIsOpen(true);
      return;
    }

    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setHighlightedIndex((prev) => (prev + 1) % Math.max(1, suggestions.length));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setHighlightedIndex((prev) => (prev - 1 + suggestions.length) % Math.max(1, suggestions.length));
    } else if (e.key === 'Enter') {
      e.preventDefault();
      if (suggestions.length > 0 && suggestions[highlightedIndex]) {
        handleSelectCompany(suggestions[highlightedIndex]);
      } else if (query.trim()) {
        const rawSym = query.trim().toUpperCase();
        const sym = rawSym.endsWith('.NS') || rawSym.endsWith('.BO') ? rawSym : `${rawSym}.NS`;
        handleSelectCompany({
          symbol: sym,
          name: sym,
          exchange: 'NSE',
          currency: 'INR',
        });
      }
    } else if (e.key === 'Escape') {
      e.preventDefault();
      setIsOpen(false);
    }
  };

  return (
    <div ref={containerRef} className="relative w-full">
      <div className="flex items-center justify-between mb-1.5">
        <label className="text-[11px] font-semibold text-slate-300 uppercase tracking-wider flex items-center gap-1.5">
          <Building2 className="h-3.5 w-3.5 text-gold-400" />
          <span>{label}</span>
        </label>
        {sublabel && <span className="text-[10px] text-slate-500 font-medium">{sublabel}</span>}
      </div>

      {/* Input container */}
      <div className="relative flex items-center">
        <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400 pointer-events-none" />
        <input
          ref={inputRef}
          type="text"
          value={query}
          disabled={disabled}
          onChange={(e) => {
            setQuery(e.target.value);
            if (!isOpen) setIsOpen(true);
          }}
          onFocus={() => setIsOpen(true)}
          onKeyDown={handleKeyDown}
          placeholder={selectedTicker ? `${selectedTicker} — ${selectedName || 'Selected'}` : placeholder}
          className="w-full bg-[#0B0E14] border border-white/[0.08] focus:border-gold-500/60 rounded-xl pl-10 pr-20 py-2.5 text-xs text-white placeholder-slate-400 focus:outline-none focus:ring-1 focus:ring-gold-500/30 transition-all font-medium"
        />

        <div className="absolute right-3 top-1/2 -translate-y-1/2 flex items-center gap-1.5">
          {isLoadingServer && <Loader2 className="h-3.5 w-3.5 animate-spin text-gold-400" />}
          {query ? (
            <button
              type="button"
              onClick={() => {
                setQuery('');
                inputRef.current?.focus();
              }}
              className="p-1 rounded-md text-slate-400 hover:text-white hover:bg-white/[0.06] transition-colors"
            >
              <X className="h-3 w-3" />
            </button>
          ) : (
            selectedTicker && (
              <span className="font-mono text-[10px] font-bold text-gold-400 bg-gold-500/10 border border-gold-500/25 px-1.5 py-0.5 rounded">
                {selectedTicker}
              </span>
            )
          )}
        </div>
      </div>

      {/* Dropdown Menu (Dark Obsidian z-50) */}
      {isOpen && (
        <div className="absolute left-0 right-0 top-full mt-2 bg-[#0B0E14] border border-white/[0.12] rounded-xl shadow-2xl z-50 overflow-hidden divide-y divide-white/[0.04] backdrop-blur-md">
          {suggestions.length === 0 ? (
            <div className="px-4 py-3 text-center text-xs text-slate-500">
              {isLoadingServer ? 'Searching companies...' : `No matching companies found for "${query}"`}
            </div>
          ) : (
            suggestions.map((item, idx) => {
              const isSelected = item.symbol === selectedTicker;
              const isHighlighted = idx === highlightedIndex;

              return (
                <div
                  key={item.symbol}
                  onMouseDown={(e) => {
                    // Prevent blur so selection always executes
                    e.preventDefault();
                    handleSelectCompany(item);
                  }}
                  onMouseEnter={() => setHighlightedIndex(idx)}
                  className={`px-3.5 py-2.5 flex items-center justify-between cursor-pointer transition-colors ${
                    isHighlighted ? 'bg-white/[0.08]' : 'hover:bg-white/[0.04]'
                  } ${isSelected ? 'bg-gold-500/5' : ''}`}
                >
                  <div className="flex items-center gap-2.5 min-w-0 pr-3">
                    <span className="shrink-0 font-mono text-[11px] font-bold px-2 py-0.5 rounded bg-gold-500/10 border border-gold-500/30 text-gold-400">
                      {item.symbol}
                    </span>
                    <div className="min-w-0">
                      <div className="text-xs font-semibold text-white truncate flex items-center gap-1.5">
                        <span>{item.name}</span>
                        {isSelected && <Check className="h-3 w-3 text-gold-400 shrink-0" />}
                      </div>
                      <div className="text-[10px] text-slate-400 truncate">
                        {item.sector || 'NSE Equities'}
                      </div>
                    </div>
                  </div>

                  <div className="shrink-0 text-right">
                    {item.market_cap && item.market_cap > 0 ? (
                      <div className="font-mono text-[10px] font-semibold text-emerald-400">
                        {formatFinancialValue(item.market_cap, 'INR')}
                      </div>
                    ) : item.price && item.price > 0 ? (
                      <div className="font-mono text-[10px] text-slate-300">
                        ₹{item.price.toLocaleString('en-IN', { maximumFractionDigits: 2 })}
                      </div>
                    ) : (
                      <span className="text-[9px] px-1.5 py-0.5 rounded bg-white/[0.06] text-slate-400 uppercase font-mono">
                        {item.exchange || 'NSE'}
                      </span>
                    )}
                  </div>
                </div>
              );
            })
          )}
        </div>
      )}
    </div>
  );
};
