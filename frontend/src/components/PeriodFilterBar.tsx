'use client';

import React from 'react';
import { Calendar, Layers, Clock, Sparkles, Filter, Check, RotateCcw } from 'lucide-react';

export const ALL_YEARS: number[] = [2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025, 2026];

/**
 * Safely parses the 4-digit integer year (e.g., 2026) from a period object or value.
 * Handles p.fiscal_year (2026 or "2026"), p.year, or embedded in p.label / p.period / p.fiscal_period ("FY2026", "Q3 2026").
 */
export const extractYear = (p: any): number | null => {
  if (p === null || p === undefined) return null;
  if (typeof p === 'number' && p >= 1900 && p <= 2100) return p;

  if (typeof p === 'object') {
    if (p.fiscal_year !== null && p.fiscal_year !== undefined) {
      const parsed = parseInt(String(p.fiscal_year), 10);
      if (!isNaN(parsed) && parsed >= 1900 && parsed <= 2100) return parsed;
    }
    if (p.year !== null && p.year !== undefined) {
      const parsed = parseInt(String(p.year), 10);
      if (!isNaN(parsed) && parsed >= 1900 && parsed <= 2100) return parsed;
    }
  }

  // Look inside string representations (fiscal_period, period, label, date, or primitive string)
  const candidate = typeof p === 'object'
    ? String(p.fiscal_period || p.period || p.label || p.date || '')
    : String(p);

  const match = candidate.match(/\b(20\d{2})\b/);
  if (match) {
    const parsed = parseInt(match[1], 10);
    if (!isNaN(parsed)) return parsed;
  }

  const fy2DigitMatch = candidate.match(/FY(\d{2})\b/i);
  if (fy2DigitMatch) {
    const parsed = 2000 + parseInt(fy2DigitMatch[1], 10);
    if (!isNaN(parsed)) return parsed;
  }

  return null;
};

/**
 * Checks whether a period record represents an annual FY period.
 * Checks fiscal_period === "FY" (or starts with "FY") OR statement_type === "annual" OR !label.startsWith("Q").
 */
export const isAnnualPeriod = (p: any): boolean => {
  if (!p) return false;
  if (p.statement_type === 'quarterly') return false;
  if (p.statement_type === 'annual' || p.statement_type === 'annual_combined') return true;

  const periodStr = String(p.fiscal_period || p.period || p.label || '').trim().toUpperCase();
  if (periodStr.startsWith('Q') || /\bQ[1-4]\b/.test(periodStr)) return false;
  if (periodStr === 'FY' || periodStr.startsWith('FY')) return true;
  return true;
};

export interface PeriodFilterBarProps {
  mode: 'annual' | 'quarterly';
  onModeChange: (mode: 'annual' | 'quarterly') => void;
  selectedYears: number[];
  onSelectedYearsChange: (years: number[]) => void;
  availableYears: number[];
  annualCount?: number;
  quarterlyCount?: number;
  className?: string;
  showSectionSwitcherOnly?: boolean;
}

export const PeriodFilterBar: React.FC<PeriodFilterBarProps> = ({
  mode,
  onModeChange,
  selectedYears,
  onSelectedYearsChange,
  availableYears,
  annualCount,
  quarterlyCount,
  className = '',
  showSectionSwitcherOnly = false,
}) => {
  // Normalize selected and available years to strict 4-digit numbers
  const safeSelected = (selectedYears || []).map(extractYear).filter((y: any): y is number => y !== null);
  const safeAvailable = (availableYears || []).map(extractYear).filter((y: any): y is number => y !== null);
  const sortedAvailable = Array.from(new Set<number>(safeAvailable)).sort((a: number, b: number) => a - b);

  // Toggle year selection (enforcing at least 1 year remains selected)
  const handleToggleYear = (year: number) => {
    if (safeSelected.includes(year)) {
      if (safeSelected.length > 1) {
        onSelectedYearsChange(safeSelected.filter((y) => y !== year).sort((a, b) => a - b));
      }
    } else {
      onSelectedYearsChange([...safeSelected, year].sort((a, b) => a - b));
    }
  };

  // Quick Preset Handlers
  const handlePreset3Y = () => {
    if (sortedAvailable.length >= 3) {
      onSelectedYearsChange(sortedAvailable.slice(-3));
    } else {
      onSelectedYearsChange([2024, 2025, 2026]);
    }
  };

  const handlePreset5Y = () => {
    if (sortedAvailable.length >= 5) {
      onSelectedYearsChange(sortedAvailable.slice(-5));
    } else {
      onSelectedYearsChange([2022, 2023, 2024, 2025, 2026]);
    }
  };

  const handlePreset10Y = () => {
    onSelectedYearsChange([...ALL_YEARS]);
  };

  const handleSelectAllAvailable = () => {
    if (sortedAvailable.length > 0) {
      onSelectedYearsChange([...sortedAvailable]);
    } else {
      onSelectedYearsChange([2023, 2024, 2025, 2026]);
    }
  };

  // Range Dropdown Handlers
  const minSelected = safeSelected.length > 0 ? Math.min(...safeSelected) : 2023;
  const maxSelected = safeSelected.length > 0 ? Math.max(...safeSelected) : 2026;

  const handleFromChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const fromY = parseInt(e.target.value, 10);
    const toY = Math.max(fromY, maxSelected);
    const newRange = ALL_YEARS.filter((y) => y >= fromY && y <= toY);
    onSelectedYearsChange(newRange);
  };

  const handleToChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const toY = parseInt(e.target.value, 10);
    const fromY = Math.min(toY, minSelected);
    const newRange = ALL_YEARS.filter((y) => y >= fromY && y <= toY);
    onSelectedYearsChange(newRange);
  };

  return (
    <div
      className={`bg-[#11141B] border border-white/[0.08] rounded-2xl p-3.5 space-y-3.5 shadow-xl ${className}`}
    >
      {/* 1. Top Bar: Section Switcher (Annual vs. Quarterly) + Presets */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 border-b border-white/[0.06] pb-3">
        {/* Section Switcher Tabs */}
        <div className="flex items-center gap-1.5 bg-[#090B0F] p-1 rounded-xl border border-white/[0.08] shadow-inner self-start">
          <button
            type="button"
            onClick={() => onModeChange('annual')}
            className={`px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-all flex items-center gap-2 ${
              mode === 'annual'
                ? 'bg-sky-500 text-white shadow-md font-bold'
                : 'text-slate-400 hover:text-white hover:bg-white/[0.04]'
            }`}
          >
            <Calendar className="h-3.5 w-3.5" />
            <span>Annual (Year-Wise)</span>
            {annualCount !== undefined && annualCount > 0 && (
              <span
                className={`text-[10px] px-1.5 py-0.2 rounded-full font-mono ${
                  mode === 'annual'
                    ? 'bg-white/20 text-white font-bold'
                    : 'bg-navy-800 text-slate-400 border border-white/[0.05]'
                }`}
              >
                {annualCount}Y
              </span>
            )}
          </button>

          <button
            type="button"
            onClick={() => onModeChange('quarterly')}
            className={`px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-all flex items-center gap-2 ${
              mode === 'quarterly'
                ? 'bg-sky-500 text-white shadow-md font-bold'
                : 'text-slate-400 hover:text-white hover:bg-white/[0.04]'
            }`}
          >
            <Layers className="h-3.5 w-3.5" />
            <span>Quarterly Results</span>
            {quarterlyCount !== undefined && quarterlyCount > 0 && (
              <span
                className={`text-[10px] px-1.5 py-0.2 rounded-full font-mono ${
                  mode === 'quarterly'
                    ? 'bg-white/20 text-white font-bold'
                    : 'bg-navy-800 text-slate-400 border border-white/[0.05]'
                }`}
              >
                {quarterlyCount}Q
              </span>
            )}
          </button>
        </div>

        {/* Quick Presets & Range Dropdowns (Rendered when in Annual mode) */}
        {mode === 'annual' && !showSectionSwitcherOnly && (
          <div className="flex items-center gap-2 flex-wrap text-xs">
            <span className="text-[11px] text-slate-400 font-medium flex items-center gap-1">
              <Filter className="h-3 w-3 text-sky-400" />
              Presets:
            </span>

            {/* Quick Buttons */}
            <div className="flex items-center gap-1 bg-[#090B0F] p-0.5 rounded-lg border border-white/[0.08]">
              <button
                type="button"
                onClick={handlePreset3Y}
                className="px-2.5 py-1 rounded text-[11px] font-mono font-medium text-slate-300 hover:text-white hover:bg-white/[0.06] transition-colors"
                title="Select last 3 fiscal years"
              >
                3Y
              </button>
              <button
                type="button"
                onClick={handlePreset5Y}
                className="px-2.5 py-1 rounded text-[11px] font-mono font-medium text-slate-300 hover:text-white hover:bg-white/[0.06] transition-colors"
                title="Select last 5 fiscal years"
              >
                5Y
              </button>
              <button
                type="button"
                onClick={handlePreset10Y}
                className="px-2.5 py-1 rounded text-[11px] font-mono font-medium text-slate-300 hover:text-white hover:bg-white/[0.06] transition-colors"
                title="Select full 10-year span (2017–2026)"
              >
                10Y (2017–26)
              </button>
              <button
                type="button"
                onClick={handleSelectAllAvailable}
                className="px-2.5 py-1 rounded text-[11px] font-mono font-medium text-cyan-400 hover:text-cyan-300 hover:bg-cyan-500/10 transition-colors"
                title="Select all years with verified records in active dataset"
              >
                Available ({sortedAvailable.length}Y)
              </button>
            </div>

            {/* Range Dropdowns: From ... To ... */}
            <div className="flex items-center gap-1.5 ml-1 text-slate-300">
              <span className="text-[10px] text-slate-500 font-mono">FROM</span>
              <select
                value={minSelected}
                onChange={handleFromChange}
                className="bg-[#090B0F] text-slate-200 border border-white/[0.12] rounded px-2 py-0.5 text-xs font-mono focus:outline-none focus:border-sky-500"
              >
                {ALL_YEARS.map((y) => (
                  <option key={y} value={y}>
                    FY{y}
                  </option>
                ))}
              </select>

              <span className="text-[10px] text-slate-500 font-mono">TO</span>
              <select
                value={maxSelected}
                onChange={handleToChange}
                className="bg-[#090B0F] text-slate-200 border border-white/[0.12] rounded px-2 py-0.5 text-xs font-mono focus:outline-none focus:border-sky-500"
              >
                {ALL_YEARS.map((y) => (
                  <option key={y} value={y}>
                    FY{y}
                  </option>
                ))}
              </select>
            </div>
          </div>
        )}
      </div>

      {/* 2. Interactive 2017–2026 Year Selector Pills (Annual Mode) */}
      {mode === 'annual' && !showSectionSwitcherOnly && (
        <div className="space-y-1.5">
          <div className="flex items-center justify-between text-[11px] text-slate-400">
            <span className="flex items-center gap-1.5">
              <Calendar className="h-3.5 w-3.5 text-cyan-400" />
              <span className="font-semibold text-slate-300">Custom 2017–2026 Year Selector:</span>
              <span className="text-slate-500">
                Click any year to toggle • ({safeSelected.length} of 10 selected)
              </span>
            </span>
            <span className="text-[10px] text-slate-500 hidden sm:inline">
              Green dot = Live data available in dataset
            </span>
          </div>

          <div className="flex items-center gap-1.5 flex-wrap">
            {ALL_YEARS.map((year) => {
              const isSelected = safeSelected.includes(year);
              const hasData = sortedAvailable.includes(year);

              let pillClass = '';
              if (isSelected) {
                pillClass =
                  'bg-sky-500 text-white font-bold shadow-md shadow-sky-500/20 border border-sky-400';
              } else if (hasData) {
                pillClass =
                  'bg-[#090B0F] text-slate-200 hover:text-white hover:bg-white/[0.08] border border-white/[0.12] opacity-100';
              } else {
                pillClass =
                  'bg-[#090B0F]/60 text-slate-500 hover:text-slate-300 hover:opacity-80 border border-white/[0.04] opacity-45';
              }

              const tooltip = hasData
                ? `FY${year}: Live verified data available in active dataset`
                : `FY${year}: No data fetched for this year — upload a 10Y Screener CSV or view available years`;

              return (
                <button
                  key={year}
                  type="button"
                  onClick={() => handleToggleYear(year)}
                  title={tooltip}
                  className={`px-3 py-1.5 rounded-lg text-xs font-mono font-medium transition-all flex items-center gap-1.5 ${pillClass}`}
                >
                  <span>FY{year}</span>
                  {hasData && (
                    <span
                      className={`w-1.5 h-1.5 rounded-full ${
                        isSelected ? 'bg-white' : 'bg-emerald-400'
                      }`}
                      title="Data verified"
                    />
                  )}
                </button>
              );
            })}
          </div>
        </div>
      )}

      {/* 3. Quarterly Results Info Strip */}
      {mode === 'quarterly' && (
        <div className="flex items-center justify-between text-xs text-slate-400 bg-[#090B0F] p-2.5 rounded-xl border border-white/[0.05]">
          <div className="flex items-center gap-2">
            <span className="h-2 w-2 rounded-full bg-cyan-400 animate-pulse" />
            <span className="text-slate-300 font-medium">
              Audited Quarterly Disclosure Section
            </span>
            <span className="text-slate-500 text-[11px]">
              • Trailing sequential quarters sorted chronologically
            </span>
          </div>
          {quarterlyCount !== undefined && (
            <span className="text-cyan-400 font-mono text-[11px]">
              {quarterlyCount} Consecutive Quarters Disclosed
            </span>
          )}
        </div>
      )}
    </div>
  );
};

export interface EmptyPeriodSelectionFallbackProps {
  selectedYears: number[];
  availableYears: number[];
  onSelectAllAvailable: () => void;
  title?: string;
  className?: string;
}

export const EmptyPeriodSelectionFallback: React.FC<EmptyPeriodSelectionFallbackProps> = ({
  selectedYears,
  availableYears,
  onSelectAllAvailable,
  title = 'No Data for Selected Fiscal Years',
  className = '',
}) => {
  const safeSelected = (selectedYears || []).map(extractYear).filter((y: any): y is number => y !== null);
  const safeAvailable = (availableYears || []).map(extractYear).filter((y: any): y is number => y !== null);
  const sortedAvailable = Array.from(new Set<number>(safeAvailable)).sort((a: number, b: number) => a - b);
  const availText =
    sortedAvailable.length > 0
      ? sortedAvailable.map((y) => `FY${y}`).join(', ')
      : 'FY2023–FY2026';

  return (
    <div
      className={`flex flex-col items-center justify-center text-center p-8 bg-[#11141B] rounded-2xl border border-white/[0.08] shadow-xl my-4 space-y-4 ${className}`}
    >
      <div className="h-12 w-12 rounded-full bg-amber-500/10 border border-amber-500/30 text-amber-400 flex items-center justify-center mx-auto">
        <Calendar className="h-6 w-6" />
      </div>
      <div className="space-y-1">
        <h3 className="text-base font-bold text-white">{title}</h3>
        <p className="text-xs text-slate-400 max-w-md mx-auto leading-relaxed">
          You selected {safeSelected.map((y) => `FY${y}`).join(', ')}. The active company dataset
          currently contains verified disclosures for{' '}
          <span className="text-cyan-400 font-mono font-semibold">{availText}</span>.
        </p>
        <p className="text-[11px] text-slate-500 max-w-md mx-auto pt-1">
          Upload a 10-Year Screener CSV to populate historical financials back to FY2017, or reset
          your view to available years below.
        </p>
      </div>
      <div className="flex items-center gap-3 pt-1">
        <button
          type="button"
          onClick={onSelectAllAvailable}
          className="px-4 py-2.5 bg-sky-500 hover:bg-sky-400 text-white rounded-xl text-xs font-bold transition-all shadow-lg shadow-sky-500/20 active:scale-95 flex items-center gap-2"
        >
          <RotateCcw className="h-3.5 w-3.5" />
          <span>Select All Available Years ({sortedAvailable.length}Y)</span>
        </button>
      </div>
    </div>
  );
};

