'use client';

import React, { useState, useEffect } from 'react';
import { 
  Calculator, 
  RotateCcw, 
  TrendingUp, 
  TrendingDown, 
  Layers, 
  Sliders, 
  AlertTriangle, 
  Info,
  CheckCircle2,
  RefreshCw,
  Building2
} from 'lucide-react';
import { API_BASE } from '@/lib/api';
import { 
  formatFinancialValue, 
  formatPerShare, 
  formatPercent, 
  normalizeExchange 
} from '@/lib/formatters';

interface ProjectedPeriod {
  year: number;
  fiscal_year_label: string;
  projected_fcf: number;
  discount_factor: number;
  pv_fcf: number;
}

interface SensitivityMatrix {
  wacc_rates: number[];
  terminal_growth_rates: number[];
  matrix: (number | null)[][];
}

interface DCFData {
  symbol: string;
  company_name: string;
  currency: string;
  current_price: number;
  intrinsic_value: number;
  upside_downside_pct: number;
  enterprise_value: number;
  equity_value: number;
  pv_cash_flows: number;
  pv_terminal_value: number;
  terminal_value: number;
  net_debt: number;
  shares_outstanding: number;
  fcf_base: number;
  fcf_estimated: boolean;
  growth_rate: number;
  historical_cagr: number;
  wacc: number;
  terminal_growth_rate: number;
  projection_years: number;
  projected_periods: ProjectedPeriod[];
  sensitivity_matrix: SensitivityMatrix;
}

interface DcfValuationViewProps {
  ticker: string;
  onSelectTicker?: (ticker: string) => void;
}

export const DcfValuationView: React.FC<DcfValuationViewProps> = ({
  ticker,
  onSelectTicker,
}) => {
  const [data, setData] = useState<DCFData | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [calculating, setCalculating] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Sliders state (in percentage terms: e.g. 10.0 for 10%, 11.5 for 11.5%)
  const [fcfGrowthPct, setFcfGrowthPct] = useState<number>(10.0);
  const [waccPct, setWaccPct] = useState<number>(11.5);
  const [terminalGrowthPct, setTerminalGrowthPct] = useState<number>(4.0);
  const [projectionYears, setProjectionYears] = useState<number>(5);

  const sym = ticker || 'ASIANPAINT.NS';

  // 1. Initial Load of Auto-seeded Defaults
  const loadDcfData = async (customPayload?: Record<string, any>) => {
    if (customPayload) {
      setCalculating(true);
    } else {
      setLoading(true);
    }
    setError(null);

    try {
      const res = await fetch(`${API_BASE}/companies/${encodeURIComponent(sym)}/dcf`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(customPayload || {}),
      });

      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}));
        throw new Error(errJson.detail || `Server error: ${res.statusText}`);
      }

      const resData: DCFData = await res.json();
      setData(resData);

      // Sync slider states from response
      setFcfGrowthPct(Math.round(resData.growth_rate * 1000) / 10);
      setWaccPct(Math.round(resData.wacc * 1000) / 10);
      setTerminalGrowthPct(Math.round(resData.terminal_growth_rate * 1000) / 10);
      setProjectionYears(resData.projection_years || 5);
    } catch (err: any) {
      setError(err.message || 'Failed to calculate DCF model');
    } finally {
      setLoading(false);
      setCalculating(false);
    }
  };

  useEffect(() => {
    loadDcfData();
  }, [sym]);

  // Validation
  const spread = Math.round((waccPct - terminalGrowthPct) * 100) / 100;
  const isSpreadInvalid = spread <= 1.0;

  // Handle Recalculate with Slider Values
  const handleRecalculate = () => {
    if (isSpreadInvalid) return;
    loadDcfData({
      growth_rate: fcfGrowthPct / 100.0,
      wacc: waccPct / 100.0,
      terminal_growth_rate: terminalGrowthPct / 100.0,
      projection_years: projectionYears,
    });
  };

  // Reset Defaults
  const handleReset = () => {
    loadDcfData({});
  };

  if (loading && !data) {
    return (
      <div className="bg-navy-900 border border-navy-800 rounded-xl p-12 text-center text-slate-400">
        <RefreshCw className="h-8 w-8 text-gold-accent animate-spin mx-auto mb-3" />
        <p className="text-sm font-medium text-slate-200">Computing Multi-Year DCF Projections...</p>
        <p className="text-xs text-slate-500 mt-1">Seeding deterministic FCF, WACC, and Sensitivity Matrix for {sym}</p>
      </div>
    );
  }

  if (error && !data) {
    const isCold = error.toLowerCase().includes('failed to fetch') || error.toLowerCase().includes('network');
    return (
      <div className="bg-navy-900 border border-navy-800 rounded-xl p-8 text-center shadow-lg">
        <div className={`h-12 w-12 rounded-full ${isCold ? 'bg-amber-500/10 text-amber-400' : 'bg-rose-500/10 text-rose-400'} flex items-center justify-center mx-auto mb-3`}>
          {isCold ? <RefreshCw className="h-6 w-6 animate-spin" /> : <AlertTriangle className="h-6 w-6" />}
        </div>
        <h3 className="text-base font-semibold text-white">
          {isCold ? 'Connecting to Valuation Engine...' : 'DCF Calculation Unavailable'}
        </h3>
        <p className="text-xs text-slate-300 mt-1 max-w-md mx-auto leading-relaxed">
          {isCold ? 'The live market server on Render may be waking up from standby. Click retry to connect.' : error}
        </p>
        <button
          onClick={() => loadDcfData({})}
          className="mt-4 px-4 py-2 rounded-lg bg-navy-800 text-xs font-medium text-gold-400 hover:text-white border border-gold-500/30 shadow-md"
        >
          Retry Calculation
        </button>
      </div>
    );
  }

  if (!data) return null;

  const isUndervalued = data.upside_downside_pct >= 10.0;
  const isOvervalued = data.upside_downside_pct <= -10.0;
  const stanceLabel = isUndervalued ? 'UNDERVALUED' : isOvervalued ? 'OVERVALUED' : 'FAIRLY VALUED';
  const stanceBadgeClass = isUndervalued
    ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30'
    : isOvervalued
    ? 'bg-rose-500/10 text-rose-400 border-rose-500/30'
    : 'bg-amber-500/10 text-amber-400 border-amber-500/30';

  const maxFcf = Math.max(...data.projected_periods.map((p) => p.projected_fcf), 1);

  return (
    <div className="space-y-6">
      {/* 1. Header Banner */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-navy-900/90 border border-navy-800 rounded-xl p-5 shadow-sm">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-lg bg-gold-500/10 border border-gold-500/30 text-gold-accent">
            <Calculator className="h-6 w-6" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-xl font-bold text-white tracking-tight">
                {data.company_name}
              </h1>
              <span className="px-2 py-0.5 rounded text-[11px] font-semibold bg-navy-800 text-gold-400 border border-gold-500/20">
                {data.symbol}
              </span>
              <span className="px-2 py-0.5 rounded text-[11px] font-medium bg-navy-800 text-slate-400 border border-navy-700">
                {normalizeExchange('', data.symbol)}
              </span>
            </div>
            <p className="text-xs text-slate-400 mt-0.5">
              Deterministic Institutional Discounted Cash Flow (DCF) & Sensitivity Model
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2.5 self-start sm:self-auto">
          <button
            onClick={handleReset}
            disabled={calculating}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-navy-800 hover:bg-navy-750 text-slate-300 hover:text-white border border-navy-700 text-xs font-medium transition-colors"
          >
            <RotateCcw className="h-3.5 w-3.5" />
            <span>Reset Defaults</span>
          </button>
          <button
            onClick={handleRecalculate}
            disabled={calculating || isSpreadInvalid}
            className="flex items-center gap-1.5 px-4 py-1.5 rounded-lg bg-gradient-to-r from-gold-500 to-gold-accent text-navy-950 font-semibold text-xs shadow-sm hover:brightness-110 transition-all disabled:opacity-50"
          >
            {calculating ? (
              <RefreshCw className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <TrendingUp className="h-3.5 w-3.5" />
            )}
            <span>{calculating ? 'Calculating...' : 'Recalculate DCF'}</span>
          </button>
        </div>
      </div>

      {/* 2. Intrinsic Value vs Market Price Hero Card */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        <div className="lg:col-span-2 bg-gradient-to-br from-navy-900 to-navy-850 border border-navy-800 rounded-xl p-6 relative overflow-hidden shadow-md">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-5 border-b border-navy-800/80">
            <div>
              <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
                Model-Derived Intrinsic Value
              </span>
              <div className="flex items-baseline gap-3 mt-1">
                <span className="text-3xl sm:text-4xl font-extrabold text-white tracking-tight">
                  {formatPerShare(data.intrinsic_value, data.currency)}
                </span>
                <span className={`px-2.5 py-1 rounded-full text-xs font-bold border ${stanceBadgeClass}`}>
                  {stanceLabel}
                </span>
              </div>
            </div>

            <div className="sm:text-right">
              <span className="text-[11px] font-medium text-slate-400 uppercase tracking-wider">
                Current Market Price
              </span>
              <div className="text-2xl font-bold text-slate-200 mt-1">
                {formatPerShare(data.current_price, data.currency)}
              </div>
              <div className="flex sm:justify-end items-center gap-1 mt-0.5">
                {data.upside_downside_pct >= 0 ? (
                  <TrendingUp className="h-3.5 w-3.5 text-emerald-400" />
                ) : (
                  <TrendingDown className="h-3.5 w-3.5 text-rose-400" />
                )}
                <span
                  className={`text-xs font-semibold ${
                    data.upside_downside_pct >= 0 ? 'text-emerald-400' : 'text-rose-400'
                  }`}
                >
                  {data.upside_downside_pct >= 0 ? '+' : ''}
                  {data.upside_downside_pct.toFixed(2)}% implied {data.upside_downside_pct >= 0 ? 'upside' : 'downside'}
                </span>
              </div>
            </div>
          </div>

          {/* Quick Metrics Strip */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 pt-5">
            <div>
              <span className="text-[10px] uppercase font-semibold text-slate-400">Enterprise Value</span>
              <div className="text-sm font-bold text-slate-200 mt-0.5">
                {formatFinancialValue(data.enterprise_value, data.currency)}
              </div>
            </div>
            <div>
              <span className="text-[10px] uppercase font-semibold text-slate-400">Net Debt</span>
              <div className="text-sm font-bold text-slate-200 mt-0.5">
                {formatFinancialValue(data.net_debt, data.currency)}
              </div>
            </div>
            <div>
              <span className="text-[10px] uppercase font-semibold text-slate-400">Equity Value</span>
              <div className="text-sm font-bold text-slate-200 mt-0.5">
                {formatFinancialValue(data.equity_value, data.currency)}
              </div>
            </div>
            <div>
              <span className="text-[10px] uppercase font-semibold text-slate-400">Base FCF ({data.fcf_estimated ? 'Est.' : 'Actual'})</span>
              <div className="text-sm font-bold text-slate-200 mt-0.5">
                {formatFinancialValue(data.fcf_base, data.currency)}
              </div>
            </div>
          </div>
        </div>

        {/* 3. Valuation Parameter Sliders Card */}
        <div className="bg-navy-900 border border-navy-800 rounded-xl p-5 space-y-4 shadow-sm">
          <div className="flex items-center justify-between pb-2 border-b border-navy-800">
            <div className="flex items-center gap-2">
              <Sliders className="h-4 w-4 text-gold-accent" />
              <h3 className="text-xs font-bold text-white uppercase tracking-wider">Interactive DCF Controls</h3>
            </div>
            <span className="text-[10px] text-slate-400">Live Math</span>
          </div>

          {/* Slider 1: FCF Growth */}
          <div>
            <div className="flex justify-between text-xs mb-1">
              <span className="text-slate-300 font-medium">FCF Projected Growth:</span>
              <span className="text-gold-400 font-bold">{fcfGrowthPct.toFixed(1)}%</span>
            </div>
            <input
              type="range"
              min="0"
              max="25"
              step="0.5"
              value={fcfGrowthPct}
              onChange={(e) => setFcfGrowthPct(parseFloat(e.target.value))}
              className="w-full accent-gold-500 h-1.5 bg-navy-800 rounded-lg cursor-pointer"
            />
            <div className="flex justify-between text-[10px] text-slate-500 mt-0.5">
              <span>0%</span>
              <span>Hist: {(data.historical_cagr * 100).toFixed(1)}%</span>
              <span>25%</span>
            </div>
          </div>

          {/* Slider 2: WACC */}
          <div>
            <div className="flex justify-between text-xs mb-1">
              <span className="text-slate-300 font-medium">WACC (Discount Rate):</span>
              <span className="text-gold-400 font-bold">{waccPct.toFixed(2)}%</span>
            </div>
            <input
              type="range"
              min="6"
              max="20"
              step="0.25"
              value={waccPct}
              onChange={(e) => setWaccPct(parseFloat(e.target.value))}
              className="w-full accent-gold-500 h-1.5 bg-navy-800 rounded-lg cursor-pointer"
            />
            <div className="flex justify-between text-[10px] text-slate-500 mt-0.5">
              <span>6.0%</span>
              <span>Base: {(data.wacc * 100).toFixed(1)}%</span>
              <span>20.0%</span>
            </div>
          </div>

          {/* Slider 3: Terminal Growth */}
          <div>
            <div className="flex justify-between text-xs mb-1">
              <span className="text-slate-300 font-medium">Terminal Growth Rate:</span>
              <span className="text-gold-400 font-bold">{terminalGrowthPct.toFixed(2)}%</span>
            </div>
            <input
              type="range"
              min="1"
              max="6"
              step="0.25"
              value={terminalGrowthPct}
              onChange={(e) => setTerminalGrowthPct(parseFloat(e.target.value))}
              className="w-full accent-gold-500 h-1.5 bg-navy-800 rounded-lg cursor-pointer"
            />
            <div className="flex justify-between text-[10px] text-slate-500 mt-0.5">
              <span>1.0%</span>
              <span>Base: {(data.terminal_growth_rate * 100).toFixed(1)}%</span>
              <span>6.0%</span>
            </div>
          </div>

          {/* Projection Horizon Years */}
          <div>
            <div className="flex justify-between text-xs mb-1">
              <span className="text-slate-300 font-medium">Projection Horizon:</span>
              <span className="text-gold-400 font-bold">{projectionYears} Years</span>
            </div>
            <div className="grid grid-cols-6 gap-1 mt-1">
              {[5, 6, 7, 8, 9, 10].map((yr) => (
                <button
                  key={yr}
                  onClick={() => setProjectionYears(yr)}
                  className={`py-1 text-xs rounded font-medium transition-colors ${
                    projectionYears === yr
                      ? 'bg-gold-500 text-navy-950 font-bold'
                      : 'bg-navy-800 text-slate-400 hover:text-white'
                  }`}
                >
                  {yr}Y
                </button>
              ))}
            </div>
          </div>

          {/* Validation Alert */}
          {isSpreadInvalid && (
            <div className="p-2.5 rounded-lg bg-rose-500/10 border border-rose-500/30 text-rose-300 text-[11px] flex items-start gap-2">
              <AlertTriangle className="h-4 w-4 text-rose-400 flex-shrink-0 mt-0.5" />
              <span>WACC ({waccPct.toFixed(2)}%) must be at least 1.0% higher than Terminal Growth ({terminalGrowthPct.toFixed(2)}%). Current spread: {spread.toFixed(2)}%.</span>
            </div>
          )}
        </div>
      </div>

      {/* 4. Projected FCF Visual Bar Chart */}
      <div className="bg-navy-900 border border-navy-800 rounded-xl p-5 shadow-sm">
        <div className="flex items-center justify-between pb-3 border-b border-navy-800 mb-4">
          <div className="flex items-center gap-2">
            <Layers className="h-4 w-4 text-cyan-400" />
            <h3 className="text-xs font-bold text-white uppercase tracking-wider">
              Projected Free Cash Flows (5–10 Year Horizon)
            </h3>
          </div>
          <span className="text-[11px] text-slate-400">
            Discounted using {(data.wacc * 100).toFixed(2)}% WACC
          </span>
        </div>

        <div className="grid grid-cols-5 lg:grid-cols-10 gap-3 pt-2">
          {data.projected_periods.map((p) => {
            const heightPct = Math.min(100, Math.max(15, Math.round((p.projected_fcf / maxFcf) * 100)));
            return (
              <div key={p.year} className="flex flex-col items-center">
                <div className="text-[10px] text-slate-400 mb-1">
                  {formatFinancialValue(p.projected_fcf, data.currency)}
                </div>

                {/* Vertical Bar Container */}
                <div className="w-full bg-navy-800/80 rounded-t h-28 flex flex-col justify-end p-1 relative group">
                  <div
                    style={{ height: `${heightPct}%` }}
                    className="w-full bg-gradient-to-t from-gold-600 to-gold-accent rounded-t transition-all duration-300 group-hover:brightness-125"
                  />
                  {/* Tooltip on hover */}
                  <div className="absolute inset-0 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity bg-navy-950/90 rounded text-[9px] p-1 text-center font-mono">
                    <div>
                      <div>PV: {formatFinancialValue(p.pv_fcf, data.currency)}</div>
                      <div className="text-slate-400 text-[8px]">DF: {p.discount_factor.toFixed(3)}</div>
                    </div>
                  </div>
                </div>

                <div className="text-[11px] font-semibold text-slate-200 mt-2">
                  {p.fiscal_year_label}
                </div>
                <div className="text-[9px] text-slate-500">
                  Year {p.year}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* 5. Enterprise-to-Equity Value Bridge */}
      <div className="bg-navy-900 border border-navy-800 rounded-xl p-5 shadow-sm">
        <h3 className="text-xs font-bold text-white uppercase tracking-wider mb-4">
          Enterprise to Equity Value Bridge
        </h3>

        <div className="grid grid-cols-2 md:grid-cols-6 gap-3 text-center">
          <div className="p-3 rounded-lg bg-navy-850 border border-navy-800">
            <span className="text-[10px] uppercase font-semibold text-slate-400">PV of {data.projection_years}Y FCFs</span>
            <div className="text-sm font-bold text-slate-100 mt-1">
              {formatFinancialValue(data.pv_cash_flows, data.currency)}
            </div>
            <span className="text-[9px] text-slate-500">Cash Flow Horizon</span>
          </div>

          <div className="p-3 rounded-lg bg-navy-850 border border-navy-800">
            <span className="text-[10px] uppercase font-semibold text-slate-400">+ PV of Terminal Value</span>
            <div className="text-sm font-bold text-slate-100 mt-1">
              {formatFinancialValue(data.pv_terminal_value, data.currency)}
            </div>
            <span className="text-[9px] text-slate-500">Gordon Growth TV</span>
          </div>

          <div className="p-3 rounded-lg bg-navy-800/80 border border-navy-700">
            <span className="text-[10px] uppercase font-semibold text-gold-400">= Enterprise Value</span>
            <div className="text-sm font-bold text-gold-300 mt-1">
              {formatFinancialValue(data.enterprise_value, data.currency)}
            </div>
            <span className="text-[9px] text-slate-400">Firm Asset Value</span>
          </div>

          <div className="p-3 rounded-lg bg-navy-850 border border-navy-800">
            <span className="text-[10px] uppercase font-semibold text-slate-400">- Net Debt</span>
            <div className="text-sm font-bold text-slate-100 mt-1">
              {formatFinancialValue(data.net_debt, data.currency)}
            </div>
            <span className="text-[9px] text-slate-500">Debt less Cash</span>
          </div>

          <div className="p-3 rounded-lg bg-navy-800/80 border border-navy-700">
            <span className="text-[10px] uppercase font-semibold text-gold-400">= Equity Value</span>
            <div className="text-sm font-bold text-gold-300 mt-1">
              {formatFinancialValue(data.equity_value, data.currency)}
            </div>
            <span className="text-[9px] text-slate-400">Shareholder Equity</span>
          </div>

          <div className="p-3 rounded-lg bg-gradient-to-br from-gold-500/20 to-navy-900 border border-gold-500/40">
            <span className="text-[10px] uppercase font-bold text-gold-400">Intrinsic Target</span>
            <div className="text-sm font-extrabold text-white mt-1">
              {formatPerShare(data.intrinsic_value, data.currency)}
            </div>
            <span className="text-[9px] text-gold-300">Per Share Fair Value</span>
          </div>
        </div>
      </div>

      {/* 6. 5x5 Color-Coded Sensitivity Matrix */}
      <div className="bg-navy-900 border border-navy-800 rounded-xl p-5 shadow-sm overflow-x-auto">
        <div className="flex items-center justify-between pb-3 border-b border-navy-800 mb-4">
          <div className="flex items-center gap-2">
            <div className="h-2 w-2 rounded-full bg-gold-400" />
            <h3 className="text-xs font-bold text-white uppercase tracking-wider">
              5x5 Valuation Sensitivity Matrix (WACC vs. Terminal Growth Rate)
            </h3>
          </div>
          <div className="flex items-center gap-4 text-[10px]">
            <span className="flex items-center gap-1.5 text-emerald-400">
              <span className="h-2 w-2 rounded-full bg-emerald-400" />
              Above Market Price (Upside)
            </span>
            <span className="flex items-center gap-1.5 text-rose-400">
              <span className="h-2 w-2 rounded-full bg-rose-400" />
              Below Market Price (Downside)
            </span>
          </div>
        </div>

        <table className="w-full text-xs border-collapse">
          <thead>
            <tr>
              <th className="p-2.5 text-left text-[11px] font-bold text-slate-400 bg-navy-950 border border-navy-800">
                WACC \ Term. Growth
              </th>
              {data.sensitivity_matrix.terminal_growth_rates.map((tg) => (
                <th
                  key={tg}
                  className="p-2.5 text-center text-[11px] font-bold text-slate-300 bg-navy-950 border border-navy-800"
                >
                  {(tg * 100).toFixed(2)}%
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.sensitivity_matrix.wacc_rates.map((w, rowIdx) => (
              <tr key={w}>
                <td className="p-2.5 text-left font-bold text-slate-300 bg-navy-950/80 border border-navy-800">
                  {(w * 100).toFixed(2)}%
                </td>
                {data.sensitivity_matrix.matrix[rowIdx].map((cellPrice, colIdx) => {
                  if (cellPrice === null) {
                    return (
                      <td
                        key={colIdx}
                        className="p-2.5 text-center text-slate-600 bg-navy-950 border border-navy-800 font-mono"
                      >
                        N/A
                      </td>
                    );
                  }

                  const isAboveMarket = cellPrice >= data.current_price;
                  const isBaseCase = rowIdx === 2 && colIdx === 2; // Center cell of 5x5 is base

                  const cellClass = isAboveMarket
                    ? 'bg-emerald-950/30 text-emerald-300 border-emerald-500/20 hover:bg-emerald-900/40'
                    : 'bg-rose-950/30 text-rose-300 border-rose-500/20 hover:bg-rose-900/40';

                  return (
                    <td
                      key={colIdx}
                      className={`p-2.5 text-center font-semibold font-mono border transition-colors ${cellClass} ${
                        isBaseCase ? 'ring-2 ring-gold-400 ring-offset-1 ring-offset-navy-950 font-bold' : ''
                      }`}
                    >
                      {formatPerShare(cellPrice, data.currency)}
                      {isBaseCase && (
                        <div className="text-[9px] text-gold-400 font-sans tracking-tight">Base Case</div>
                      )}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};
