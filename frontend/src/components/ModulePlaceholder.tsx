'use client';

import React from 'react';
import { 
  Building2, 
  FileSpreadsheet, 
  Percent, 
  Calculator, 
  BrainCircuit, 
  ShieldAlert, 
  FileText,
  Clock,
  Sparkles,
  ChevronRight,
  Database,
  ArrowLeft
} from 'lucide-react';

interface ModulePlaceholderProps {
  sectionId: string;
  ticker: string;
  onBackToOverview: () => void;
}

const MODULE_DETAILS: Record<
  string,
  {
    title: string;
    subtitle: string;
    icon: React.ComponentType<{ className?: string }>;
    features: string[];
    technicalStack: string;
  }
> = {
  'company-analysis': {
    title: 'Company Analysis & Business Model',
    subtitle: 'Comprehensive deep dive into competitive moats, segment revenues, and market positioning.',
    icon: Building2,
    features: [
      'Segment revenue geographic breakdown',
      'Porter’s Five Forces & moat scoring',
      'Management governance & insider trading telemetry',
      'Executive compensation vs shareholder returns'
    ],
    technicalStack: 'PostgreSQL + SEC EDGAR Pipeline + Gemini AI Synthesis'
  },
  'financial-statements': {
    title: 'Three-Statement Financial Modeling',
    subtitle: 'Standardized Income Statement, Balance Sheet, and Cash Flow Statement with historical restatements.',
    icon: FileSpreadsheet,
    features: [
      '10-Year historical 10-K & 10-Q statement drilldowns',
      'GAAP to Non-GAAP reconciliation adjustments',
      'Working capital cycle & cash conversion calculations',
      'One-click Excel & CSV model export'
    ],
    technicalStack: 'Neon PostgreSQL + FastAPI Data Engine'
  },
  'financial-ratios': {
    title: 'Institutional Financial Ratios & Benchmarking',
    subtitle: 'Cross-sectional peer comparison across profitability, liquidity, solvency, and valuation.',
    icon: Percent,
    features: [
      'DuPont ROE 5-stage decomposition',
      'Altman Z-Score & Beneish M-Score risk audits',
      'Historical P/E, EV/Sales, and EV/EBITDA percentile bands',
      'Industry peer quartile distribution'
    ],
    technicalStack: 'NumPy/Pandas Backend Engine + Vector Analytics'
  },
  'dcf-valuation': {
    title: 'Discounted Cash Flow (DCF) Engine',
    subtitle: 'Intrinsic enterprise valuation model with dynamic WACC calculation and sensitivity matrices.',
    icon: Calculator,
    features: [
      'Unlevered Free Cash Flow (UFCF) 5-year projection',
      'Weighted Average Cost of Capital (WACC) capital asset pricing model',
      'Perpetual Growth vs Exit Multiple terminal value toggle',
      '2D Monte Carlo Sensitivity Matrix (WACC vs Terminal Growth)'
    ],
    technicalStack: 'Python Financial Mathematics Engine (`app.financial.metrics`)'
  },
  'ai-research': {
    title: 'AI Research Assistant & Copilot',
    subtitle: 'Autonomous equity research agent synthesizing earnings calls, filings, and analyst transcripts.',
    icon: BrainCircuit,
    features: [
      'Autonomous Q&A against verified 10-K disclosures',
      'Earnings call sentiment inflection detection',
      'Key catalyst and fundamental risk extraction',
      'Automated investment memo generation'
    ],
    technicalStack: 'Google Gemini 3.8 / 3.5 API + Vector Embeddings'
  },
  'risk-intelligence': {
    title: 'Risk Intelligence & Stress Testing',
    subtitle: 'Macroeconomic and portfolio stress-testing against interest rate shocks and supply chain friction.',
    icon: ShieldAlert,
    features: [
      'Fed rate curve sensitivity simulation (+100 bps shock)',
      'FX currency translation exposure breakdown',
      'Debt maturity wall & refinancing cliff audit',
      'Supply chain geographic concentration heatmaps'
    ],
    technicalStack: 'FastAPI Risk Simulation Engine'
  },
  'research-reports': {
    title: 'Institutional Research Reports & Dispatches',
    subtitle: 'Publication-ready equity research briefs and downloadable institutional PDF dossiers.',
    icon: FileText,
    features: [
      'Institutional Wall Street-grade report generator',
      'Custom branding & compliance disclaimers',
      'Analyst rating change notifications & price target tracking',
      'Automated morning research dispatch briefings'
    ],
    technicalStack: 'FastAPI Document Generator + Headless PDF Engine'
  }
};

export const ModulePlaceholder: React.FC<ModulePlaceholderProps> = ({
  sectionId,
  ticker,
  onBackToOverview,
}) => {
  const details = MODULE_DETAILS[sectionId] || {
    title: 'Institutional Module',
    subtitle: 'This financial intelligence module is scheduled for Phase 2 deployment.',
    icon: Sparkles,
    features: ['Real-time market feeds', 'PostgreSQL integration', 'Advanced financial modeling'],
    technicalStack: 'FastAPI + Next.js + PostgreSQL',
  };

  const Icon = details.icon;

  return (
    <div className="space-y-6">
      {/* Top Breadcrumb & Back Action */}
      <div className="flex items-center justify-between">
        <button
          onClick={onBackToOverview}
          className="flex items-center gap-1.5 text-xs text-slate-400 hover:text-gold-400 transition-colors font-medium"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          <span>Return to Institutional Overview</span>
        </button>
        <span className="text-[11px] font-mono px-2.5 py-1 rounded-full bg-gold-500/10 text-gold-400 border border-gold-500/30 font-semibold">
          STAGED FOR PHASE 2
        </span>
      </div>

      {/* Module Hero Banner */}
      <div className="bg-navy-900 border border-navy-800 rounded-2xl p-8 relative overflow-hidden">
        <div className="absolute top-0 right-0 -mr-12 -mt-12 w-64 h-64 rounded-full bg-gold-500/5 blur-3xl pointer-events-none" />

        <div className="flex items-start gap-5">
          <div className="h-14 w-14 rounded-2xl bg-gradient-to-br from-navy-800 to-navy-750 border border-gold-500/30 flex items-center justify-center text-gold-accent shadow-lg flex-shrink-0">
            <Icon className="h-7 w-7 text-gold-accent" />
          </div>
          <div>
            <div className="flex items-center gap-3">
              <h2 className="text-xl font-bold text-white">{details.title}</h2>
              <span className="text-xs font-semibold px-2 py-0.5 rounded bg-navy-800 text-slate-300 border border-navy-700">
                {ticker}
              </span>
            </div>
            <p className="text-sm text-slate-300 mt-1 max-w-2xl leading-relaxed">
              {details.subtitle}
            </p>
          </div>
        </div>
      </div>

      {/* Grid: Architecture & Roadmap */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Planned Features Card */}
        <div className="bg-navy-900 border border-navy-800 rounded-xl p-6">
          <div className="flex items-center gap-2 mb-4">
            <Clock className="h-4 w-4 text-gold-accent" />
            <h3 className="text-sm font-bold text-white uppercase tracking-wider text-[11px]">
              Phase 2 Implementation Roadmap
            </h3>
          </div>
          <ul className="space-y-3">
            {details.features.map((feat, idx) => (
              <li key={idx} className="flex items-start gap-2.5 text-xs text-slate-300">
                <ChevronRight className="h-3.5 w-3.5 text-gold-accent flex-shrink-0 mt-0.5" />
                <span>{feat}</span>
              </li>
            ))}
          </ul>
        </div>

        {/* Engine Architecture & Staging Card */}
        <div className="bg-navy-900 border border-navy-800 rounded-xl p-6 flex flex-col justify-between">
          <div>
            <div className="flex items-center gap-2 mb-4">
              <Database className="h-4 w-4 text-cyan-400" />
              <h3 className="text-sm font-bold text-white uppercase tracking-wider text-[11px]">
                Underlying Technical Architecture
              </h3>
            </div>
            <div className="p-4 rounded-lg bg-navy-950 border border-navy-850 space-y-3">
              <div className="flex justify-between text-xs">
                <span className="text-slate-400">Target Stack:</span>
                <span className="text-slate-200 font-mono text-[11px]">{details.technicalStack}</span>
              </div>
              <div className="flex justify-between text-xs">
                <span className="text-slate-400">Database Layer:</span>
                <span className="text-slate-200 font-medium">PostgreSQL (Neon Cloud)</span>
              </div>
              <div className="flex justify-between text-xs">
                <span className="text-slate-400">AI Intelligence:</span>
                <span className="text-gold-400 font-medium">Google Gemini API</span>
              </div>
              <div className="flex justify-between text-xs">
                <span className="text-slate-400">Safety Rule:</span>
                <span className="text-emerald-400 font-medium">Zero Paid Credits in Phase 1</span>
              </div>
            </div>
          </div>

          <div className="mt-4 pt-4 border-t border-navy-800 text-center">
            <button
              onClick={onBackToOverview}
              className="px-4 py-2 rounded-lg bg-navy-800 hover:bg-navy-750 text-gold-400 text-xs font-semibold border border-gold-500/20 transition-colors w-full"
            >
              Explore Active Phase 1 Dashboard
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
