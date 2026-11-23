'use client';

import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import {
  LayoutDashboard,
  Building2,
  FileSpreadsheet,
  Percent,
  Calculator,
  BrainCircuit,
  ShieldAlert,
  FileText,
  TrendingUp,
  Scale,
  Star,
  X
} from 'lucide-react';

export interface NavItem {
  id: string;
  name: string;
  icon: React.ComponentType<{ className?: string }>;
  isReady: boolean;
}

export const NAV_ITEMS: NavItem[] = [
  { id: 'overview', name: 'Overview', icon: LayoutDashboard, isReady: true },
  { id: 'company-analysis', name: 'Company Analysis', icon: Building2, isReady: true },
  { id: 'compare', name: 'Compare Equities', icon: Scale, isReady: true },
  { id: 'financial-statements', name: 'Financial Statements', icon: FileSpreadsheet, isReady: true },
  { id: 'financial-ratios', name: 'Financial Ratios', icon: Percent, isReady: true },
  { id: 'dcf', name: 'DCF Valuation', icon: Calculator, isReady: true },
  { id: 'ai-research', name: 'AI Research Assistant', icon: BrainCircuit, isReady: true },
  { id: 'risk', name: 'Risk Intelligence', icon: ShieldAlert, isReady: true },
  { id: 'reports', name: 'Research Reports', icon: FileText, isReady: true },
];

interface SidebarProps {
  activeSection: string;
  onSelectSection: (id: string) => void;
  currentTicker?: string;
  isOpenOnMobile?: boolean;
  onCloseMobile?: () => void;
  onSelectTicker?: (ticker: string) => void;
}

export const Sidebar: React.FC<SidebarProps> = ({
  activeSection,
  onSelectSection,
  currentTicker,
  isOpenOnMobile = false,
  onCloseMobile,
  onSelectTicker,
}) => {
  const router = useRouter();
  const [watchlist, setWatchlist] = useState<string[]>([]);

  // 1. Sync Watchlist from localStorage
  useEffect(() => {
    const loadWatchlist = () => {
      try {
        const raw = localStorage.getItem('finsight_watchlist');
        if (raw) {
          const parsed = JSON.parse(raw);
          if (Array.isArray(parsed)) {
            setWatchlist(parsed.map((x: any) => (typeof x === 'string' ? x : x.symbol)));
            return;
          }
        }
        // Seed default institutional universe if clean state
        const defaults = ['ASIANPAINT.NS', 'RELIANCE.NS', 'TCS.NS', 'INFY.NS'];
        setWatchlist(defaults);
        localStorage.setItem('finsight_watchlist', JSON.stringify(defaults));
      } catch {
        setWatchlist(['ASIANPAINT.NS', 'RELIANCE.NS', 'TCS.NS', 'INFY.NS']);
      }
    };

    loadWatchlist();
    window.addEventListener('watchlistUpdated', loadWatchlist);
    window.addEventListener('storage', loadWatchlist);
    return () => {
      window.removeEventListener('watchlistUpdated', loadWatchlist);
      window.removeEventListener('storage', loadWatchlist);
    };
  }, []);

  const handleRemoveFromWatchlist = (e: React.MouseEvent, tickerToRemove: string) => {
    e.stopPropagation();
    const updated = watchlist.filter((s) => s.toUpperCase() !== tickerToRemove.toUpperCase());
    setWatchlist(updated);
    try {
      localStorage.setItem('finsight_watchlist', JSON.stringify(updated));
      window.dispatchEvent(new Event('watchlistUpdated'));
    } catch {}
  };

  const handleSwitchTicker = (ticker: string) => {
    if (onSelectTicker) {
      onSelectTicker(ticker);
    } else {
      try {
        localStorage.setItem('finsight_last_company', ticker);
      } catch {}
      router.push(`/company/${encodeURIComponent(ticker)}?tab=${activeSection}`);
    }
    if (onCloseMobile) onCloseMobile();
  };

  return (
    <>
      {/* Mobile & Tablet Backdrop (< 1024px) */}
      {isOpenOnMobile && (
        <div
          className="fixed inset-0 bg-black/70 backdrop-blur-sm z-30 lg:hidden"
          onClick={onCloseMobile}
        />
      )}

      <aside
        className={`fixed lg:static inset-y-0 left-0 z-40 w-60 bg-[#0B0E14] border-r border-white/[0.06] flex flex-col flex-shrink-0 min-h-screen transition-transform duration-300 ease-in-out ${
          isOpenOnMobile ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'
        }`}
      >
        {/* Brand Header */}
        <div className="h-14 px-4 border-b border-white/[0.06] flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="h-7 w-7 rounded-md bg-sky-500/10 border border-sky-500/20 flex items-center justify-center text-sky-400">
              <TrendingUp className="h-4 w-4" />
            </div>
            <div className="flex items-center gap-1.5">
              <span className="font-bold text-sm tracking-tight text-white">FinSight</span>
              <span className="text-[10px] font-mono font-semibold px-1.5 py-0.2 rounded bg-sky-500/10 text-sky-400 border border-sky-500/20">
                AI
              </span>
            </div>
          </div>

          {/* Close button on mobile/tablet */}
          {onCloseMobile && (
            <button
              onClick={onCloseMobile}
              className="lg:hidden p-1 rounded text-slate-400 hover:text-white hover:bg-white/[0.05]"
            >
              <X className="h-4 w-4" />
            </button>
          )}
        </div>

        {/* Navigation List */}
        <nav className="flex-1 p-2 space-y-0.5 overflow-y-auto">
          <div className="px-2.5 py-2 text-[10px] font-mono font-semibold tracking-wider text-slate-400 uppercase">
            Terminal Views
          </div>
          {NAV_ITEMS.map((item) => {
            const Icon = item.icon;
            const isActive =
              activeSection === item.id ||
              (item.id === 'dcf' && activeSection === 'dcf-valuation') ||
              (item.id === 'risk' && activeSection === 'risk-intelligence') ||
              (item.id === 'reports' && activeSection === 'research-reports') ||
              (item.id === 'compare' && activeSection === 'compare');

            return (
              <button
                key={item.id}
                onClick={() => {
                  onSelectSection(item.id);
                  if (onCloseMobile) onCloseMobile();
                }}
                className={`w-full flex items-center justify-between px-2.5 py-2 text-xs font-medium transition-all group ${
                  isActive
                    ? 'border-l-2 border-sky-400 bg-white/[0.04] text-white rounded-r-lg font-semibold'
                    : 'border-l-2 border-transparent text-slate-400 hover:text-slate-200 hover:bg-white/[0.02] rounded-lg'
                }`}
              >
                <div className="flex items-center gap-2.5 min-w-0">
                  <Icon
                    className={`h-4 w-4 flex-shrink-0 transition-colors ${
                      isActive ? 'text-sky-400' : 'text-slate-500 group-hover:text-slate-300'
                    }`}
                  />
                  <span className="truncate">{item.name}</span>
                </div>
                {item.isReady && (
                  <span
                    className={`h-1.5 w-1.5 rounded-full ${
                      isActive ? 'bg-sky-400' : 'bg-emerald-400/80'
                    }`}
                  />
                )}
              </button>
            );
          })}
        </nav>

        {/* Personal Watchlist Section */}
        <div className="p-3 border-t border-white/[0.06] bg-[#080A0F]">
          <div className="flex items-center justify-between px-1 mb-2">
            <div className="flex items-center gap-1.5 text-[10px] font-mono font-semibold tracking-wider text-slate-400 uppercase">
              <Star className="h-3 w-3 text-sky-400 fill-sky-400" />
              <span>Watchlist</span>
            </div>
            <span className="text-[10px] font-mono text-slate-400 bg-white/[0.04] border border-white/[0.08] px-1.5 py-0.2 rounded">
              {watchlist.length}
            </span>
          </div>

          <div className="space-y-1 max-h-36 overflow-y-auto pr-1">
            {watchlist.length === 0 ? (
              <div className="px-1 py-1.5 text-[11px] text-slate-500 italic">
                No starred tickers. Click ★ to add.
              </div>
            ) : (
              watchlist.map((itemTicker) => {
                const isCurrent = currentTicker?.toUpperCase() === itemTicker.toUpperCase();
                return (
                  <div
                    key={itemTicker}
                    className={`group flex items-center justify-between px-2 py-1.5 rounded-md text-xs transition-colors cursor-pointer ${
                      isCurrent
                        ? 'bg-white/[0.05] text-sky-400 font-semibold border border-white/[0.08]'
                        : 'text-slate-400 hover:bg-white/[0.02] hover:text-slate-200'
                    }`}
                  >
                    <button
                      type="button"
                      onClick={() => handleSwitchTicker(itemTicker)}
                      className="flex-1 text-left truncate font-mono text-[11px] tabular-nums"
                      title={`Switch to ${itemTicker}`}
                    >
                      {itemTicker}
                    </button>
                    <button
                      type="button"
                      onClick={(e) => handleRemoveFromWatchlist(e, itemTicker)}
                      className="opacity-0 group-hover:opacity-100 p-0.5 text-slate-500 hover:text-rose-400 transition-opacity ml-1"
                      title="Remove from watchlist"
                    >
                      <X className="h-3 w-3" />
                    </button>
                  </div>
                );
              })
            )}
          </div>
        </div>

        {/* Minimal Footer */}
        <div className="p-3.5 border-t border-white/[0.06] bg-[#07090D] flex items-center justify-between text-xs">
          <div className="flex items-center gap-2">
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse" />
            <span className="text-[11px] font-medium text-slate-300">FinSight AI</span>
          </div>
          <span className="text-[10px] font-mono text-slate-400">Live</span>
        </div>
      </aside>
    </>
  );
};
