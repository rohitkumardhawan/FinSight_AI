'use client';

import React, { useState, useEffect } from 'react';
import { 
  ShieldAlert, 
  ShieldCheck, 
  AlertTriangle, 
  RefreshCw, 
  TrendingUp, 
  TrendingDown, 
  Scale, 
  Activity, 
  PieChart, 
  Sparkles,
  CheckCircle2,
  AlertCircle
} from 'lucide-react';
import { API_BASE } from '@/lib/api';
import { 
  formatFinancialValue, 
  formatPerShare, 
  formatMultiple, 
  formatPercent,
  normalizeExchange 
} from '@/lib/formatters';

interface LeverageLiquidityPillar {
  pillar_score: number;
  risk_level: string;
  debt_to_equity: number | null;
  interest_coverage: number | null;
  current_ratio: number | null;
  total_debt: number | null;
  cash_and_equivalents: number | null;
  net_debt: number | null;
  assessment: string;
}

interface ProfitabilityStabilityPillar {
  pillar_score: number;
  risk_level: string;
  opm_std_dev: number;
  historical_opms: number[];
  latest_revenue_growth_pct: number | null;
  revenue_contracting: boolean;
  latest_opm_change_pp: number | null;
  margin_contracting: boolean;
  assessment: string;
}

interface ValuationStretchPillar {
  pillar_score: number;
  risk_level: string;
  current_pe: number | null;
  historical_avg_pe: number | null;
  pe_stretch_multiple: number | null;
  dcf_intrinsic_value: number;
  dcf_downside_pct: number;
  assessment: string;
}

interface EarningsQualityPillar {
  pillar_score: number;
  risk_level: string;
  fcf_to_net_income: number | null;
  is_conversion_warning: boolean;
  free_cash_flow: number | null;
  net_income: number | null;
  assessment: string;
}

interface RiskWatchpoint {
  category: string;
  title: string;
  description: string;
  severity: string;
}

interface RiskData {
  symbol: string;
  company_name: string;
  currency: string;
  overall_score: number;
  risk_level: string;
  pillars: {
    leverage_liquidity: LeverageLiquidityPillar;
    profitability_stability: ProfitabilityStabilityPillar;
    valuation_stretch: ValuationStretchPillar;
    earnings_quality: EarningsQualityPillar;
  };
  watchpoints: RiskWatchpoint[];
  generated_at: string;
}

interface RiskIntelligenceViewProps {
  ticker: string;
  onSelectTicker?: (ticker: string) => void;
}

export const RiskIntelligenceView: React.FC<RiskIntelligenceViewProps> = ({
  ticker,
  onSelectTicker,
}) => {
  const [data, setData] = useState<RiskData | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const sym = ticker || 'ASIANPAINT.NS';

  const loadRiskData = async () => {
    setLoading(true);
    setError(null);

    try {
      const res = await fetch(`${API_BASE}/companies/${encodeURIComponent(sym)}/risk`);
      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}));
        throw new Error(errJson.detail || `Server error: ${res.statusText}`);
      }

      const resData: RiskData = await res.json();
      setData(resData);
    } catch (err: any) {
      setError(err.message || 'Failed to fetch risk intelligence analysis');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadRiskData();
  }, [sym]);

  const getTierColor = (tier: string) => {
    switch (tier?.toLowerCase()) {
      case 'low':
        return {
          badge: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30',
          text: 'text-emerald-400',
          bg: 'bg-emerald-500',
        };
      case 'moderate':
        return {
          badge: 'bg-amber-500/10 text-amber-400 border-amber-500/30',
          text: 'text-amber-400',
          bg: 'bg-amber-500',
        };
      case 'elevated':
        return {
          badge: 'bg-orange-500/10 text-orange-400 border-orange-500/30',
          text: 'text-orange-400',
          bg: 'bg-orange-500',
        };
      case 'high':
        return {
          badge: 'bg-rose-500/10 text-rose-400 border-rose-500/30',
          text: 'text-rose-400',
          bg: 'bg-rose-500',
        };
      default:
        return {
          badge: 'bg-slate-500/10 text-slate-400 border-slate-500/30',
          text: 'text-slate-400',
          bg: 'bg-slate-500',
        };
    }
  };

  if (loading && !data) {
    return (
      <div className="bg-navy-900 border border-navy-800 rounded-xl p-12 text-center text-slate-400">
        <RefreshCw className="h-8 w-8 text-gold-accent animate-spin mx-auto mb-3" />
        <p className="text-sm font-medium text-slate-200">Evaluating 4 Quantitative Risk Pillars...</p>
        <p className="text-xs text-slate-500 mt-1">Analyzing Leverage, Margin Volatility, Valuation Stretch, and Cash Conversion for {sym}</p>
      </div>
    );
  }

  if (error && !data) {
    return (
      <div className="bg-navy-900 border border-rose-500/30 rounded-xl p-8 text-center">
        <AlertTriangle className="h-8 w-8 text-rose-400 mx-auto mb-3" />
        <h3 className="text-base font-semibold text-white">Risk Intelligence Error</h3>
        <p className="text-xs text-rose-300 mt-1 max-w-md mx-auto">{error}</p>
        <button
          onClick={loadRiskData}
          className="mt-4 px-4 py-2 rounded-lg bg-navy-800 text-xs font-medium text-slate-200 hover:text-white border border-navy-700"
        >
          Retry Risk Analysis
        </button>
      </div>
    );
  }

  if (!data) return null;

  const overallColors = getTierColor(data.risk_level);
  const p1 = data.pillars.leverage_liquidity;
  const p2 = data.pillars.profitability_stability;
  const p3 = data.pillars.valuation_stretch;
  const p4 = data.pillars.earnings_quality;

  return (
    <div className="space-y-6">
      {/* 1. Header Banner */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-navy-900/90 border border-navy-800 rounded-xl p-5 shadow-sm">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-lg bg-gold-500/10 border border-gold-500/30 text-gold-accent">
            <ShieldAlert className="h-6 w-6" />
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
              Multi-Pillar Institutional Risk Intelligence & Grounded Watchpoints
            </p>
          </div>
        </div>

        <button
          onClick={loadRiskData}
          disabled={loading}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-navy-800 hover:bg-navy-750 text-slate-300 hover:text-white border border-navy-700 text-xs font-medium transition-colors self-start sm:self-auto"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`} />
          <span>Refresh Risk</span>
        </button>
      </div>

      {/* 2. Composite Risk Score Hero Card */}
      <div className="bg-gradient-to-br from-navy-900 to-navy-850 border border-navy-800 rounded-xl p-6 shadow-md">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-6">
          <div className="flex items-center gap-5">
            {/* Score Ring / Badge */}
            <div className="relative flex items-center justify-center h-20 w-20 rounded-2xl bg-navy-950 border border-navy-800 shadow-inner">
              <div className="text-center">
                <span className="text-2xl font-extrabold text-white leading-none">
                  {data.overall_score}
                </span>
                <span className="text-[10px] text-slate-500 block">/ 100</span>
              </div>
            </div>

            <div>
              <div className="flex items-center gap-2">
                <span className="text-xs uppercase font-semibold text-slate-400 tracking-wider">
                  Composite Institutional Risk
                </span>
                <span className={`px-2.5 py-0.5 rounded-full text-xs font-bold border ${overallColors.badge}`}>
                  {data.risk_level} Risk
                </span>
              </div>
              <p className="text-sm font-semibold text-slate-200 mt-1">
                {data.risk_level === 'Low'
                  ? 'Strong balance sheet profile and resilient cash conversion with minimal structural solvency risk.'
                  : data.risk_level === 'Moderate'
                  ? 'Balanced financial profile with manageable leverage, though requiring active tracking of valuation multiples.'
                  : 'Elevated risk detected across valuation stretch or cash flow conversion metrics.'}
              </p>
            </div>
          </div>

          {/* Quick Pillar Scores Overview */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 md:border-l md:border-navy-800 md:pl-6">
            <div>
              <span className="text-[10px] uppercase font-semibold text-slate-400">Leverage</span>
              <div className="text-sm font-bold text-slate-200 mt-0.5">{p1.pillar_score}/100</div>
              <span className={`text-[10px] font-medium ${getTierColor(p1.risk_level).text}`}>{p1.risk_level}</span>
            </div>
            <div>
              <span className="text-[10px] uppercase font-semibold text-slate-400">Stability</span>
              <div className="text-sm font-bold text-slate-200 mt-0.5">{p2.pillar_score}/100</div>
              <span className={`text-[10px] font-medium ${getTierColor(p2.risk_level).text}`}>{p2.risk_level}</span>
            </div>
            <div>
              <span className="text-[10px] uppercase font-semibold text-slate-400">Valuation</span>
              <div className="text-sm font-bold text-slate-200 mt-0.5">{p3.pillar_score}/100</div>
              <span className={`text-[10px] font-medium ${getTierColor(p3.risk_level).text}`}>{p3.risk_level}</span>
            </div>
            <div>
              <span className="text-[10px] uppercase font-semibold text-slate-400">Quality</span>
              <div className="text-sm font-bold text-slate-200 mt-0.5">{p4.pillar_score}/100</div>
              <span className={`text-[10px] font-medium ${getTierColor(p4.risk_level).text}`}>{p4.risk_level}</span>
            </div>
          </div>
        </div>
      </div>

      {/* 3. Four Color-Coded Risk Pillar Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
        {/* Pillar 1: Leverage & Liquidity */}
        <div className="bg-navy-900 border border-navy-800 rounded-xl p-5 shadow-sm space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-navy-800">
            <div className="flex items-center gap-2">
              <Scale className="h-4 w-4 text-cyan-400" />
              <h3 className="text-xs font-bold text-white uppercase tracking-wider">
                1. Leverage & Liquidity
              </h3>
            </div>
            <span className={`px-2 py-0.5 rounded text-[11px] font-bold border ${getTierColor(p1.risk_level).badge}`}>
              {p1.risk_level} ({p1.pillar_score}/100)
            </span>
          </div>

          <div className="grid grid-cols-3 gap-3">
            <div className="p-2.5 rounded-lg bg-navy-850 border border-navy-800">
              <span className="text-[10px] uppercase font-medium text-slate-400">Debt to Equity</span>
              <div className="text-base font-bold text-slate-100 mt-0.5">
                {p1.debt_to_equity !== null ? `${p1.debt_to_equity.toFixed(2)}x` : '—'}
              </div>
            </div>
            <div className="p-2.5 rounded-lg bg-navy-850 border border-navy-800">
              <span className="text-[10px] uppercase font-medium text-slate-400">Interest Coverage</span>
              <div className="text-base font-bold text-slate-100 mt-0.5">
                {p1.interest_coverage !== null ? `${p1.interest_coverage.toFixed(1)}x` : '—'}
              </div>
            </div>
            <div className="p-2.5 rounded-lg bg-navy-850 border border-navy-800">
              <span className="text-[10px] uppercase font-medium text-slate-400">Current Ratio</span>
              <div className="text-base font-bold text-slate-100 mt-0.5">
                {p1.current_ratio !== null ? `${p1.current_ratio.toFixed(2)}x` : '—'}
              </div>
            </div>
          </div>

          <p className="text-xs text-slate-300 leading-relaxed bg-navy-950/40 p-3 rounded-lg border border-navy-850">
            {p1.assessment}
          </p>
        </div>

        {/* Pillar 2: Profitability & Margin Stability */}
        <div className="bg-navy-900 border border-navy-800 rounded-xl p-5 shadow-sm space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-navy-800">
            <div className="flex items-center gap-2">
              <Activity className="h-4 w-4 text-emerald-400" />
              <h3 className="text-xs font-bold text-white uppercase tracking-wider">
                2. Profitability & Margin Stability
              </h3>
            </div>
            <span className={`px-2 py-0.5 rounded text-[11px] font-bold border ${getTierColor(p2.risk_level).badge}`}>
              {p2.risk_level} ({p2.pillar_score}/100)
            </span>
          </div>

          <div className="grid grid-cols-3 gap-3">
            <div className="p-2.5 rounded-lg bg-navy-850 border border-navy-800">
              <span className="text-[10px] uppercase font-medium text-slate-400">OPM Std Dev</span>
              <div className="text-base font-bold text-slate-100 mt-0.5">
                {p2.opm_std_dev.toFixed(2)}%
              </div>
            </div>
            <div className="p-2.5 rounded-lg bg-navy-850 border border-navy-800">
              <span className="text-[10px] uppercase font-medium text-slate-400">YoY Sales Growth</span>
              <div className="text-base font-bold text-slate-100 mt-0.5 flex items-center gap-1">
                {p2.latest_revenue_growth_pct !== null ? `${p2.latest_revenue_growth_pct > 0 ? '+' : ''}${p2.latest_revenue_growth_pct.toFixed(1)}%` : '—'}
                {p2.revenue_contracting && <AlertTriangle className="h-3.5 w-3.5 text-rose-400" />}
              </div>
            </div>
            <div className="p-2.5 rounded-lg bg-navy-850 border border-navy-800">
              <span className="text-[10px] uppercase font-medium text-slate-400">OPM Delta</span>
              <div className="text-base font-bold text-slate-100 mt-0.5">
                {p2.latest_opm_change_pp !== null ? `${p2.latest_opm_change_pp > 0 ? '+' : ''}${p2.latest_opm_change_pp.toFixed(2)} pp` : '—'}
              </div>
            </div>
          </div>

          <p className="text-xs text-slate-300 leading-relaxed bg-navy-950/40 p-3 rounded-lg border border-navy-850">
            {p2.assessment}
          </p>
        </div>

        {/* Pillar 3: Valuation Stretch */}
        <div className="bg-navy-900 border border-navy-800 rounded-xl p-5 shadow-sm space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-navy-800">
            <div className="flex items-center gap-2">
              <PieChart className="h-4 w-4 text-purple-400" />
              <h3 className="text-xs font-bold text-white uppercase tracking-wider">
                3. Valuation Stretch
              </h3>
            </div>
            <span className={`px-2 py-0.5 rounded text-[11px] font-bold border ${getTierColor(p3.risk_level).badge}`}>
              {p3.risk_level} ({p3.pillar_score}/100)
            </span>
          </div>

          <div className="grid grid-cols-3 gap-3">
            <div className="p-2.5 rounded-lg bg-navy-850 border border-navy-800">
              <span className="text-[10px] uppercase font-medium text-slate-400">Trailing P/E</span>
              <div className="text-base font-bold text-slate-100 mt-0.5">
                {p3.current_pe !== null ? `${p3.current_pe.toFixed(2)}x` : '—'}
              </div>
            </div>
            <div className="p-2.5 rounded-lg bg-navy-850 border border-navy-800">
              <span className="text-[10px] uppercase font-medium text-slate-400">Historical Avg P/E</span>
              <div className="text-base font-bold text-slate-100 mt-0.5">
                {p3.historical_avg_pe !== null ? `${p3.historical_avg_pe.toFixed(2)}x` : '—'}
              </div>
            </div>
            <div className="p-2.5 rounded-lg bg-navy-850 border border-navy-800">
              <span className="text-[10px] uppercase font-medium text-slate-400">DCF Downside</span>
              <div className="text-base font-bold text-slate-100 mt-0.5">
                {p3.dcf_downside_pct > 0 ? `-${p3.dcf_downside_pct.toFixed(1)}%` : '0.0%'}
              </div>
            </div>
          </div>

          <p className="text-xs text-slate-300 leading-relaxed bg-navy-950/40 p-3 rounded-lg border border-navy-850">
            {p3.assessment}
          </p>
        </div>

        {/* Pillar 4: Earnings Quality */}
        <div className="bg-navy-900 border border-navy-800 rounded-xl p-5 shadow-sm space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-navy-800">
            <div className="flex items-center gap-2">
              <ShieldCheck className="h-4 w-4 text-gold-accent" />
              <h3 className="text-xs font-bold text-white uppercase tracking-wider">
                4. Earnings Quality & Cash Conversion
              </h3>
            </div>
            <span className={`px-2 py-0.5 rounded text-[11px] font-bold border ${getTierColor(p4.risk_level).badge}`}>
              {p4.risk_level} ({p4.pillar_score}/100)
            </span>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="p-2.5 rounded-lg bg-navy-850 border border-navy-800">
              <span className="text-[10px] uppercase font-medium text-slate-400">FCF / Net Income</span>
              <div className="text-base font-bold text-slate-100 mt-0.5">
                {p4.fcf_to_net_income !== null ? `${p4.fcf_to_net_income.toFixed(2)}x` : '—'}
              </div>
            </div>
            <div className="p-2.5 rounded-lg bg-navy-850 border border-navy-800">
              <span className="text-[10px] uppercase font-medium text-slate-400">Conversion Status</span>
              <div className="text-xs font-bold mt-1">
                {p4.is_conversion_warning ? (
                  <span className="text-rose-400 flex items-center gap-1">
                    <AlertCircle className="h-3.5 w-3.5" /> Under 0.70 Drag
                  </span>
                ) : (
                  <span className="text-emerald-400 flex items-center gap-1">
                    <CheckCircle2 className="h-3.5 w-3.5" /> Healthy (&gt;0.70)
                  </span>
                )}
              </div>
            </div>
          </div>

          <p className="text-xs text-slate-300 leading-relaxed bg-navy-950/40 p-3 rounded-lg border border-navy-850">
            {p4.assessment}
          </p>
        </div>
      </div>

      {/* 4. Grounded AI Risk Watchpoints Card */}
      <div className="bg-navy-900 border border-navy-800 rounded-xl p-5 shadow-sm space-y-4">
        <div className="flex items-center justify-between pb-3 border-b border-navy-800">
          <div className="flex items-center gap-2">
            <Sparkles className="h-4 w-4 text-gold-accent" />
            <h3 className="text-xs font-bold text-white uppercase tracking-wider">
              Institutional AI Watchpoints (Gemini 3.8 Flash RAG)
            </h3>
          </div>
          <span className="text-[10px] font-medium text-slate-400">
            Grounded in Neon PostgreSQL Multi-Year Statements
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {data.watchpoints.map((wp, idx) => {
            const tierColors = getTierColor(wp.severity);
            return (
              <div
                key={idx}
                className="bg-navy-950/60 border border-navy-800/80 rounded-xl p-4 flex flex-col justify-between space-y-3"
              >
                <div>
                  <div className="flex items-center justify-between gap-2 mb-2">
                    <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider truncate">
                      {wp.category}
                    </span>
                    <span className={`px-2 py-0.5 rounded text-[9px] font-bold border ${tierColors.badge}`}>
                      {wp.severity}
                    </span>
                  </div>
                  <h4 className="text-xs font-bold text-white leading-snug">
                    {wp.title}
                  </h4>
                  <p className="text-xs text-slate-300 mt-2 leading-relaxed">
                    {wp.description}
                  </p>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};
