'use client';

import React from 'react';
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
}

export const Sidebar: React.FC<SidebarProps> = ({
  activeSection,
  onSelectSection,
  currentTicker,
  isOpenOnMobile = false,
  onCloseMobile,
}) => {
  return (
    <>
      {/* Mobile Backdrop */}
      {isOpenOnMobile && (
        <div
          className="fixed inset-0 bg-black/60 backdrop-blur-sm z-30 md:hidden"
          onClick={onCloseMobile}
        />
      )}

      <aside
        className={`fixed md:static inset-y-0 left-0 z-40 w-64 bg-navy-900 border-r border-navy-800 flex flex-col flex-shrink-0 min-h-screen transition-transform duration-300 ease-in-out ${
          isOpenOnMobile ? 'translate-x-0' : '-translate-x-full md:translate-x-0'
        }`}
      >
        {/* Brand Header */}
        <div className="p-5 border-b border-navy-800 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="h-9 w-9 rounded-lg bg-gradient-to-br from-gold-500/20 to-gold-accent/10 border border-gold-500/30 flex items-center justify-center text-gold-accent shadow-sm">
              <TrendingUp className="h-5 w-5 text-gold-accent" />
            </div>
            <div>
              <div className="flex items-center gap-1.5">
                <span className="font-bold text-lg tracking-tight text-white">FinSight</span>
                <span className="font-semibold text-xs px-1.5 py-0.5 rounded bg-gold-500/10 text-gold-400 border border-gold-500/30">AI</span>
              </div>
              <p className="text-[10px] text-slate-400 tracking-tight leading-tight mt-0.5">
                Equity Research & Intelligence
              </p>
            </div>
          </div>

          {/* Close button on mobile */}
          {onCloseMobile && (
            <button
              onClick={onCloseMobile}
              className="md:hidden p-1 text-slate-400 hover:text-white"
            >
              <X className="h-5 w-5" />
            </button>
          )}
        </div>

        {/* Navigation List */}
        <nav className="flex-1 p-3 space-y-1 overflow-y-auto">
          <div className="px-3 py-2 text-[11px] font-semibold tracking-wider text-slate-400 uppercase">
            Institutional Cockpit
          </div>
          {NAV_ITEMS.map((item) => {
            const Icon = item.icon;
            const isActive =
              activeSection === item.id ||
              (item.id === 'dcf' && activeSection === 'dcf-valuation') ||
              (item.id === 'risk' && activeSection === 'risk-intelligence') ||
              (item.id === 'reports' && activeSection === 'research-reports');
            return (
              <button
                key={item.id}
                onClick={() => {
                  onSelectSection(item.id);
                  if (onCloseMobile) onCloseMobile();
                }}
                className={`w-full flex items-center justify-between px-3 py-2.5 rounded-lg text-xs font-medium transition-all group ${
                  isActive
                    ? 'bg-navy-800 text-gold-400 border border-gold-500/30 shadow-sm shadow-gold-glow'
                    : 'text-slate-300 hover:bg-navy-850 hover:text-white border border-transparent'
                }`}
              >
                <div className="flex items-center gap-3">
                  <Icon
                    className={`h-4 w-4 transition-colors ${
                      isActive ? 'text-gold-accent' : 'text-slate-400 group-hover:text-slate-200'
                    }`}
                  />
                  <span className="truncate">{item.name}</span>
                </div>
                {item.isReady ? (
                  <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 shadow-sm shadow-emerald-400/50"></span>
                ) : (
                  <span className="text-[9px] uppercase px-1.5 py-0.5 rounded bg-navy-800 text-slate-400 border border-navy-700">
                    Phase 5
                  </span>
                )}
              </button>
            );
          })}
        </nav>

        {/* System Status Footer */}
        <div className="p-4 border-t border-navy-800 bg-navy-950/40">
          <div className="flex items-center justify-between text-[11px] text-slate-400 mb-2">
            <span>Engine Status</span>
            <span className="flex items-center gap-1.5 text-emerald-400 font-medium">
              <span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse"></span>
              Online
            </span>
          </div>
          <div className="text-[10px] text-slate-500 flex items-center justify-between">
            <span>Architecture: v4.0.0</span>
            <span className="text-gold-400 font-semibold">Phase 4</span>
          </div>
        </div>
      </aside>
    </>
  );
};
