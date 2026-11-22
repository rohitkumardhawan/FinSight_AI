'use client';

import React from 'react';
import { Calculator, BrainCircuit, ArrowRight, Sparkles } from 'lucide-react';

interface QuickActionsProps {
  onNavigate: (sectionId: string) => void;
  ticker: string;
}

export const QuickActions: React.FC<QuickActionsProps> = ({ onNavigate, ticker }) => {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      {/* DCF Valuation Card */}
      <div
        onClick={() => onNavigate('dcf-valuation')}
        className="cursor-pointer bg-gradient-to-br from-navy-900 to-navy-850 border border-navy-800 hover:border-gold-500/40 rounded-xl p-5 transition-all duration-300 hover:shadow-lg hover:shadow-navy-950/60 group relative overflow-hidden"
      >
        <div className="flex items-start justify-between">
          <div className="h-10 w-10 rounded-lg bg-gold-500/10 border border-gold-500/30 flex items-center justify-center text-gold-accent mb-3 group-hover:scale-105 transition-transform">
            <Calculator className="h-5 w-5 text-gold-accent" />
          </div>
          <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-navy-800 text-slate-400 border border-navy-700">
            Model Engine
          </span>
        </div>
        <h4 className="text-sm font-bold text-white group-hover:text-gold-400 transition-colors flex items-center gap-1.5">
          <span>Launch DCF Valuation Model</span>
          <ArrowRight className="h-4 w-4 transform group-hover:translate-x-1 transition-transform" />
        </h4>
        <p className="text-xs text-slate-400 mt-1 leading-relaxed">
          Simulate enterprise intrinsic value for {ticker} using custom weighted average cost of capital (WACC) and terminal growth assumptions.
        </p>
      </div>

      {/* AI Research Assistant Card */}
      <div
        onClick={() => onNavigate('ai-research')}
        className="cursor-pointer bg-gradient-to-br from-navy-900 to-navy-850 border border-navy-800 hover:border-gold-500/40 rounded-xl p-5 transition-all duration-300 hover:shadow-lg hover:shadow-navy-950/60 group relative overflow-hidden"
      >
        <div className="flex items-start justify-between">
          <div className="h-10 w-10 rounded-lg bg-cyan-500/10 border border-cyan-500/30 flex items-center justify-center text-cyan-400 mb-3 group-hover:scale-105 transition-transform">
            <BrainCircuit className="h-5 w-5 text-cyan-400" />
          </div>
          <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-navy-800 text-slate-400 border border-navy-700 flex items-center gap-1">
            <Sparkles className="h-3 w-3 text-gold-400" />
            Gemini AI
          </span>
        </div>
        <h4 className="text-sm font-bold text-white group-hover:text-gold-400 transition-colors flex items-center gap-1.5">
          <span>AI Equity Research Synthesis</span>
          <ArrowRight className="h-4 w-4 transform group-hover:translate-x-1 transition-transform" />
        </h4>
        <p className="text-xs text-slate-400 mt-1 leading-relaxed">
          Synthesize 10-K disclosures, earnings call transcript transcripts, and key competitive catalysts powered by Gemini intelligence.
        </p>
      </div>
    </div>
  );
};
