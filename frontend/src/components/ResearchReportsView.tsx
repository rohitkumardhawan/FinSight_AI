'use client';

import React, { useState, useEffect } from 'react';
import { 
  FileText, 
  Download, 
  RefreshCw, 
  CheckCircle2, 
  AlertTriangle, 
  ShieldCheck, 
  TrendingUp, 
  TrendingDown, 
  Scale, 
  Layers, 
  Building2, 
  Sparkles,
  ExternalLink,
  ChevronRight,
  Printer
} from 'lucide-react';
import { API_BASE } from '@/lib/api';
import { 
  formatFinancialValue, 
  formatPerShare, 
  formatPercent, 
  normalizeExchange 
} from '@/lib/formatters';

interface FinancialPeriodPreview {
  fiscal_year: number;
  period: string;
  revenue: string;
  operating_income: string;
  opm_pct: string;
  net_income: string;
  eps: string;
  free_cash_flow: string;
}

interface ReportPreviewData {
  company_name: string;
  symbol: string;
  exchange: string;
  currency: string;
  sector: string;
  current_price: number;
  dcf_intrinsic_value: number;
  upside_downside_pct: number;
  rating_stance: string;
  rating_color: string;
  thesis: string;
  dcf_summary: {
    wacc: number;
    terminal_growth_rate: number;
    growth_rate: number;
    enterprise_value: string;
    net_debt: string;
    intrinsic_value: string;
  };
  scenarios?: {
    worst_case?: { fair_value: number; target_pe: number; cagr_pct: number };
    base_case?: { fair_value: number; target_pe: number; cagr_pct: number };
    best_case?: { fair_value: number; target_pe: number; cagr_pct: number };
  };
  risk_summary: {
    overall_score: number;
    risk_level: string;
    pillars: Record<string, any>;
    watchpoints: Array<{
      category: string;
      title: string;
      description: string;
      severity: string;
    }>;
  };
  financials_preview: FinancialPeriodPreview[];
  generated_at: string;
}

interface ResearchReportsViewProps {
  ticker: string;
  onSelectTicker?: (ticker: string) => void;
}

export const ResearchReportsView: React.FC<ResearchReportsViewProps> = ({
  ticker,
  onSelectTicker,
}) => {
  const [report, setReport] = useState<ReportPreviewData | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [downloading, setDownloading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const sym = ticker || 'ASIANPAINT.NS';

  // 1. Fetch Report Preview
  const fetchReportPreview = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/companies/${encodeURIComponent(sym)}/report/preview`);
      if (!res.ok) {
        throw new Error(`Failed to load research report (HTTP ${res.status})`);
      }
      const data: ReportPreviewData = await res.json();
      setReport(data);
    } catch (err: any) {
      console.error('Error fetching report preview:', err);
      setError(err.message || 'Unable to generate research report preview.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchReportPreview();
  }, [sym]);

  // 2. Download Institutional PDF Report
  const handleDownloadPdf = async () => {
    setDownloading(true);
    try {
      const res = await fetch(`${API_BASE}/companies/${encodeURIComponent(sym)}/report/pdf`);
      if (!res.ok) {
        throw new Error(`PDF generation failed with HTTP ${res.status}`);
      }
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      const cleanSym = (report?.symbol || sym).replace(/\./g, '_');
      a.download = `FinSight_${cleanSym}_Research_Report.pdf`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (err: any) {
      console.error('Error downloading PDF report:', err);
      alert(`Could not download PDF report: ${err.message}`);
    } finally {
      setDownloading(false);
    }
  };

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div className="space-y-2">
            <div className="h-8 w-64 bg-navy-800 rounded animate-pulse"></div>
            <div className="h-4 w-96 bg-navy-850 rounded animate-pulse"></div>
          </div>
          <div className="h-10 w-44 bg-navy-800 rounded animate-pulse"></div>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="h-24 bg-navy-900 border border-navy-800 rounded-xl p-4 animate-pulse"></div>
          ))}
        </div>
        <div className="h-48 bg-navy-900 border border-navy-800 rounded-xl p-6 animate-pulse"></div>
        <div className="h-64 bg-navy-900 border border-navy-800 rounded-xl p-6 animate-pulse"></div>
      </div>
    );
  }

  if (error || !report) {
    const isCold = error && (error.toLowerCase().includes('failed to fetch') || error.toLowerCase().includes('network'));
    return (
      <div className="bg-navy-900 border border-navy-800 rounded-xl p-8 text-center space-y-4 shadow-lg">
        <div className={`h-12 w-12 rounded-full ${isCold ? 'bg-amber-500/10 border-amber-500/30 text-amber-400' : 'bg-rose-500/10 border-rose-500/30 text-rose-400'} flex items-center justify-center mx-auto`}>
          {isCold ? <RefreshCw className="h-6 w-6 animate-spin" /> : <AlertTriangle className="h-6 w-6" />}
        </div>
        <h3 className="text-lg font-bold text-white">
          {isCold ? 'Connecting to Report Engine...' : 'Unable to Load Research Report'}
        </h3>
        <p className="text-sm text-slate-300 max-w-md mx-auto leading-relaxed">
          {isCold ? 'The live market backend on Render may be waking up from standby. Click retry to connect.' : (error || 'No report data available for this symbol.')}
        </p>
        <button
          onClick={fetchReportPreview}
          className="inline-flex items-center gap-2 px-4 py-2 bg-navy-800 hover:bg-navy-750 text-gold-400 border border-gold-500/30 rounded-lg text-sm transition-colors shadow-md"
        >
          <RefreshCw className="h-4 w-4" />
          Retry Report Preview
        </button>
      </div>
    );
  }

  const isUpside = report.upside_downside_pct >= 0;
  const ratingBadgeClass = 
    report.rating_stance.includes('BUY') || report.rating_stance.includes('OVERWEIGHT')
      ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30'
      : report.rating_stance.includes('SELL') || report.rating_stance.includes('UNDERWEIGHT')
      ? 'bg-rose-500/10 text-rose-400 border-rose-500/30'
      : 'bg-amber-500/10 text-amber-400 border-amber-500/30';

  const exchangeLabel = normalizeExchange(report.exchange, report.symbol);

  return (
    <div className="space-y-6">
      {/* 1. Header & Actions Strip */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-2 border-b border-navy-800">
        <div>
          <div className="flex items-center gap-3 flex-wrap">
            <h1 className="text-2xl font-bold text-white tracking-tight flex items-center gap-2">
              <FileText className="h-6 w-6 text-gold-accent" />
              Institutional Research Memo
            </h1>
            <span className={`px-2.5 py-1 rounded-full text-xs font-semibold border ${ratingBadgeClass}`}>
              {report.rating_stance}
            </span>
            <span className="px-2 py-0.5 rounded text-[11px] font-medium bg-navy-800 text-slate-300 border border-navy-700">
              {exchangeLabel}: {report.symbol}
            </span>
          </div>
          <p className="text-xs text-slate-400 mt-1">
            Publication-grade institutional equity memo compiled from canonical Neon PostgreSQL financials, DCF models, and risk scorecard.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={fetchReportPreview}
            disabled={loading}
            className="p-2.5 rounded-lg bg-navy-850 hover:bg-navy-800 text-slate-300 border border-navy-700 transition-colors"
            title="Refresh Preview"
          >
            <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
          </button>
          <button
            onClick={handleDownloadPdf}
            disabled={downloading}
            className="flex items-center gap-2 px-5 py-2.5 rounded-lg bg-gradient-to-r from-gold-500 to-amber-500 hover:from-gold-400 hover:to-amber-400 text-navy-950 font-bold text-sm shadow-lg shadow-gold-500/20 transition-all disabled:opacity-50"
          >
            {downloading ? (
              <>
                <RefreshCw className="h-4 w-4 animate-spin text-navy-950" />
                Generating PDF...
              </>
            ) : (
              <>
                <Download className="h-4 w-4 text-navy-950" />
                Download PDF Report
              </>
            )}
          </button>
        </div>
      </div>

      {/* 2. Key Investment Metrics Cards */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        <div className="bg-navy-900 border border-navy-800 rounded-xl p-3.5">
          <span className="text-[11px] font-medium text-slate-400 uppercase tracking-wider block">Market Price</span>
          <p className="text-lg font-bold text-white mt-1">
            {formatPerShare(report.current_price, report.currency)}
          </p>
          <span className="text-[10px] text-slate-400">Live Quote</span>
        </div>

        <div className="bg-navy-900 border border-navy-800 rounded-xl p-3.5">
          <span className="text-[11px] font-medium text-slate-400 uppercase tracking-wider block">DCF Intrinsic Value</span>
          <p className="text-lg font-bold text-gold-400 mt-1">
            {formatPerShare(report.dcf_intrinsic_value, report.currency)}
          </p>
          <span className="text-[10px] text-slate-400">Fair Value Target</span>
        </div>

        <div className="bg-navy-900 border border-navy-800 rounded-xl p-3.5">
          <span className="text-[11px] font-medium text-slate-400 uppercase tracking-wider block">Implied Upside</span>
          <p className={`text-lg font-bold mt-1 flex items-center gap-1 ${isUpside ? 'text-emerald-400' : 'text-rose-400'}`}>
            {isUpside ? <TrendingUp className="h-4 w-4" /> : <TrendingDown className="h-4 w-4" />}
            {report.upside_downside_pct > 0 ? '+' : ''}{report.upside_downside_pct.toFixed(2)}%
          </p>
          <span className="text-[10px] text-slate-400">{isUpside ? 'Discount to Fair Value' : 'Premium to Fair Value'}</span>
        </div>

        <div className="bg-navy-900 border border-navy-800 rounded-xl p-3.5">
          <span className="text-[11px] font-medium text-slate-400 uppercase tracking-wider block">WACC / TG</span>
          <p className="text-lg font-bold text-slate-200 mt-1">
            {(report.dcf_summary.wacc * 100).toFixed(1)}% / {(report.dcf_summary.terminal_growth_rate * 100).toFixed(1)}%
          </p>
          <span className="text-[10px] text-slate-400">Discount & Terminal Rates</span>
        </div>

        <div className="bg-navy-900 border border-navy-800 rounded-xl p-3.5 col-span-2 md:col-span-1">
          <span className="text-[11px] font-medium text-slate-400 uppercase tracking-wider block">Composite Risk</span>
          <p className="text-lg font-bold text-cyan-400 mt-1 flex items-center gap-1.5">
            <ShieldCheck className="h-4 w-4 text-cyan-400" />
            {report.risk_summary.overall_score}/100
          </p>
          <span className="text-[10px] text-slate-400">{report.risk_summary.risk_level} Risk Tier</span>
        </div>
      </div>

      {/* 3. Executive Investment Thesis */}
      <div className="bg-navy-900 border border-navy-800 rounded-xl p-5 sm:p-6 space-y-4">
        <div className="flex items-center justify-between border-b border-navy-800/80 pb-3">
          <div className="flex items-center gap-2">
            <Sparkles className="h-5 w-5 text-gold-accent" />
            <h2 className="text-base font-bold text-white tracking-tight">Executive Investment Thesis</h2>
          </div>
          <span className="text-[10px] text-slate-400 font-mono bg-navy-800 px-2 py-0.5 rounded border border-navy-700">
            Grounded in Neon DB Canonical Records
          </span>
        </div>

        <div className="space-y-3 text-sm text-slate-300 leading-relaxed font-sans">
          {report.thesis.split('\n\n').map((paragraph, idx) => (
            <p key={idx} className="bg-navy-950/40 border border-navy-800/60 rounded-lg p-3.5">
              {paragraph}
            </p>
          ))}
        </div>
      </div>

      {/* 4. Financial Performance Snapshot (Pruned Historical Financials) */}
      <div className="bg-navy-900 border border-navy-800 rounded-xl p-5 sm:p-6 space-y-4">
        <div className="flex items-center justify-between border-b border-navy-800/80 pb-3">
          <div>
            <h2 className="text-base font-bold text-white tracking-tight">Financial Performance Snapshot</h2>
            <p className="text-xs text-slate-400 mt-0.5">
              Multi-year standardized financials formatted in {report.currency === 'INR' ? '₹ Crores' : '$ Millions / Billions'}
            </p>
          </div>
          <span className="text-xs font-semibold px-2 py-0.5 rounded bg-navy-800 text-slate-300 border border-navy-700">
            {report.financials_preview.length} Periods
          </span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs border-collapse">
            <thead>
              <tr className="bg-navy-950/80 text-slate-400 border-b border-navy-800 font-semibold uppercase tracking-wider">
                <th className="py-2.5 px-3">Metric / Fiscal Period</th>
                {report.financials_preview.map((p) => (
                  <th key={p.fiscal_year} className="py-2.5 px-3 text-right">
                    {p.period}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-navy-800/60 text-slate-200">
              <tr className="hover:bg-navy-850/50 transition-colors">
                <td className="py-2.5 px-3 font-semibold text-white">Revenue</td>
                {report.financials_preview.map((p) => (
                  <td key={p.fiscal_year} className="py-2.5 px-3 text-right font-mono">
                    {p.revenue}
                  </td>
                ))}
              </tr>
              <tr className="hover:bg-navy-850/50 transition-colors">
                <td className="py-2.5 px-3 text-slate-300">Operating Profit (EBIT)</td>
                {report.financials_preview.map((p) => (
                  <td key={p.fiscal_year} className="py-2.5 px-3 text-right font-mono text-slate-300">
                    {p.operating_income}
                  </td>
                ))}
              </tr>
              <tr className="hover:bg-navy-850/50 transition-colors">
                <td className="py-2.5 px-3 text-slate-300">Operating Margin (OPM %)</td>
                {report.financials_preview.map((p) => (
                  <td key={p.fiscal_year} className="py-2.5 px-3 text-right font-mono text-cyan-400">
                    {p.opm_pct}
                  </td>
                ))}
              </tr>
              <tr className="hover:bg-navy-850/50 transition-colors">
                <td className="py-2.5 px-3 font-semibold text-white">Net Income</td>
                {report.financials_preview.map((p) => (
                  <td key={p.fiscal_year} className="py-2.5 px-3 text-right font-mono font-medium text-emerald-400">
                    {p.net_income}
                  </td>
                ))}
              </tr>
              <tr className="hover:bg-navy-850/50 transition-colors">
                <td className="py-2.5 px-3 text-slate-300">Reported EPS</td>
                {report.financials_preview.map((p) => (
                  <td key={p.fiscal_year} className="py-2.5 px-3 text-right font-mono text-slate-300">
                    {p.eps}
                  </td>
                ))}
              </tr>
              <tr className="hover:bg-navy-850/50 transition-colors bg-navy-950/30">
                <td className="py-2.5 px-3 font-semibold text-gold-400">Free Cash Flow (FCF)</td>
                {report.financials_preview.map((p) => (
                  <td key={p.fiscal_year} className="py-2.5 px-3 text-right font-mono font-semibold text-gold-400">
                    {p.free_cash_flow}
                  </td>
                ))}
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      {/* 5. DCF Valuation & Scenarios Summary */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-navy-900 border border-navy-800 rounded-xl p-5 space-y-4">
          <div className="flex items-center gap-2 border-b border-navy-800 pb-3">
            <Scale className="h-5 w-5 text-gold-accent" />
            <h2 className="text-base font-bold text-white">DCF Model Architecture</h2>
          </div>
          <div className="space-y-2.5 text-xs">
            <div className="flex items-center justify-between p-2.5 rounded bg-navy-950/60 border border-navy-800/80">
              <span className="text-slate-400">Projected Enterprise Value</span>
              <span className="font-mono font-semibold text-white">{report.dcf_summary.enterprise_value}</span>
            </div>
            <div className="flex items-center justify-between p-2.5 rounded bg-navy-950/60 border border-navy-800/80">
              <span className="text-slate-400">Net Debt Position</span>
              <span className="font-mono font-semibold text-slate-200">{report.dcf_summary.net_debt}</span>
            </div>
            <div className="flex items-center justify-between p-2.5 rounded bg-navy-950/60 border border-navy-800/80">
              <span className="text-slate-400">Weighted Average Cost of Capital (WACC)</span>
              <span className="font-mono font-semibold text-cyan-400">{(report.dcf_summary.wacc * 100).toFixed(2)}%</span>
            </div>
            <div className="flex items-center justify-between p-2.5 rounded bg-navy-950/60 border border-navy-800/80">
              <span className="text-slate-400">Terminal Growth Rate (g)</span>
              <span className="font-mono font-semibold text-slate-200">{(report.dcf_summary.terminal_growth_rate * 100).toFixed(2)}%</span>
            </div>
            <div className="flex items-center justify-between p-2.5 rounded bg-navy-950/60 border border-navy-800/80">
              <span className="text-slate-400">Intrinsic Fair Value Per Share</span>
              <span className="font-mono font-bold text-gold-400">{report.dcf_summary.intrinsic_value}</span>
            </div>
          </div>
        </div>

        {/* Valuation Scenarios */}
        <div className="bg-navy-900 border border-navy-800 rounded-xl p-5 space-y-4">
          <div className="flex items-center gap-2 border-b border-navy-800 pb-3">
            <Layers className="h-5 w-5 text-cyan-400" />
            <h2 className="text-base font-bold text-white">Valuation Scenario Spectrum</h2>
          </div>
          {report.scenarios && Object.keys(report.scenarios).length > 0 ? (
            <div className="grid grid-cols-3 gap-3 pt-1">
              {/* Worst Case */}
              <div className="p-3 bg-navy-950/70 border border-rose-500/20 rounded-lg text-center space-y-1">
                <span className="text-[10px] uppercase font-bold text-rose-400">Worst Case</span>
                <p className="text-base font-bold text-white font-mono mt-1">
                  {formatPerShare(report.scenarios.worst_case?.fair_value, report.currency)}
                </p>
                <div className="text-[10px] text-slate-400">
                  {report.scenarios.worst_case?.cagr_pct ? `${report.scenarios.worst_case.cagr_pct}% CAGR` : 'Pessimistic'}
                </div>
              </div>

              {/* Base Case */}
              <div className="p-3 bg-navy-950/70 border border-gold-500/30 rounded-lg text-center space-y-1">
                <span className="text-[10px] uppercase font-bold text-gold-400">Base Case</span>
                <p className="text-base font-bold text-gold-300 font-mono mt-1">
                  {formatPerShare(report.scenarios.base_case?.fair_value || report.dcf_intrinsic_value, report.currency)}
                </p>
                <div className="text-[10px] text-slate-400">
                  {report.scenarios.base_case?.cagr_pct ? `${report.scenarios.base_case.cagr_pct}% CAGR` : 'Consensus'}
                </div>
              </div>

              {/* Best Case */}
              <div className="p-3 bg-navy-950/70 border border-emerald-500/20 rounded-lg text-center space-y-1">
                <span className="text-[10px] uppercase font-bold text-emerald-400">Best Case</span>
                <p className="text-base font-bold text-white font-mono mt-1">
                  {formatPerShare(report.scenarios.best_case?.fair_value, report.currency)}
                </p>
                <div className="text-[10px] text-slate-400">
                  {report.scenarios.best_case?.cagr_pct ? `${report.scenarios.best_case.cagr_pct}% CAGR` : 'Optimistic'}
                </div>
              </div>
            </div>
          ) : (
            <div className="p-4 bg-navy-950/50 rounded-lg border border-navy-800 text-xs text-slate-400 text-center">
              Deterministic 3-scenario bracket calibrated against historical CAGR ({((report.dcf_summary.growth_rate || 0.1) * 100).toFixed(1)}%).
            </div>
          )}

          <div className="p-3 bg-navy-950/40 rounded-lg border border-navy-800/60 text-[11px] text-slate-400 space-y-1">
            <span className="text-slate-300 font-semibold block">Scenario Governance</span>
            Scenarios reflect 3Y trailing margin stability, reinvestment rate, and cost of equity calibrated from live exchange data.
          </div>
        </div>
      </div>

      {/* 6. Institutional Risk Intelligence Scorecard */}
      <div className="bg-navy-900 border border-navy-800 rounded-xl p-5 sm:p-6 space-y-4">
        <div className="flex items-center justify-between border-b border-navy-800 pb-3">
          <div className="flex items-center gap-2">
            <ShieldCheck className="h-5 w-5 text-rose-400" />
            <h2 className="text-base font-bold text-white">Institutional Risk Intelligence Scorecard</h2>
          </div>
          <span className="px-2.5 py-1 rounded text-xs font-bold bg-navy-800 text-cyan-400 border border-navy-700">
            Composite Score: {report.risk_summary.overall_score}/100 ({report.risk_summary.risk_level})
          </span>
        </div>

        {/* 4 Pillars Summary Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
          {report.risk_summary.pillars && Object.entries(report.risk_summary.pillars).map(([key, pillar]: [string, any]) => {
            const pillarTitle = key.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
            const levelColor = 
              pillar.risk_level === 'Low' ? 'text-emerald-400 border-emerald-500/30' :
              pillar.risk_level === 'High' ? 'text-rose-400 border-rose-500/30' :
              'text-amber-400 border-amber-500/30';
            
            return (
              <div key={key} className="p-3.5 bg-navy-950/60 border border-navy-800 rounded-lg space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold text-white">{pillarTitle}</span>
                  <span className={`text-[10px] px-1.5 py-0.5 rounded border font-bold ${levelColor}`}>
                    {pillar.risk_level}
                  </span>
                </div>
                <div className="text-lg font-bold text-slate-200 font-mono">
                  {pillar.pillar_score}<span className="text-xs text-slate-500">/100</span>
                </div>
                <p className="text-[11px] text-slate-400 leading-tight">
                  {pillar.assessment}
                </p>
              </div>
            );
          })}
        </div>

        {/* Grounded Watchpoints */}
        {report.risk_summary.watchpoints && report.risk_summary.watchpoints.length > 0 && (
          <div className="pt-2 space-y-2">
            <span className="text-xs font-bold text-slate-300 uppercase tracking-wider block">
              Grounded Institutional Watchpoints
            </span>
            <div className="space-y-2">
              {report.risk_summary.watchpoints.map((wp, idx) => {
                const sevColor = 
                  wp.severity === 'High' ? 'bg-rose-500/10 text-rose-400 border-rose-500/30' :
                  wp.severity === 'Moderate' ? 'bg-amber-500/10 text-amber-400 border-amber-500/30' :
                  'bg-emerald-500/10 text-emerald-400 border-emerald-500/30';

                return (
                  <div key={idx} className="p-3 bg-navy-950/80 border border-navy-800/80 rounded-lg flex items-start gap-3">
                    <span className={`px-2 py-0.5 rounded text-[10px] font-bold border uppercase tracking-wider flex-shrink-0 mt-0.5 ${sevColor}`}>
                      {wp.severity}
                    </span>
                    <div className="space-y-0.5 flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-bold text-white">{wp.title}</span>
                        <span className="text-[10px] text-slate-500">({wp.category})</span>
                      </div>
                      <p className="text-xs text-slate-300 leading-relaxed">{wp.description}</p>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>

      {/* 7. Institutional Disclaimers & Regulatory Notice */}
      <div className="p-4 bg-navy-900/60 border border-navy-800 rounded-xl text-[11px] text-slate-400 space-y-1.5 leading-relaxed">
        <span className="font-semibold text-slate-300 uppercase tracking-wider block text-[10px]">
          Institutional Compliance & Research Notice
        </span>
        <p>
          This research report is automatically compiled by FinSight AI&apos;s institutional valuation engine. All historical financials, statement restatements, and valuation scenarios are grounded in Neon PostgreSQL canonical stores and exchange disclosures. DCF intrinsic values reflect mathematical discounted cash flow models under specified cost of capital and terminal growth parameters.
        </p>
        <p className="text-slate-400 text-[10px]">
          Generated on {new Date(report.generated_at).toLocaleString()} • FinSight AI Architecture v4.0.0 • Confidential
        </p>
      </div>
    </div>
  );
};
