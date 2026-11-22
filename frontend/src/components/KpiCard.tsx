'use client';

import React from 'react';
import { ArrowUpRight, ArrowDownRight } from 'lucide-react';

interface KpiCardProps {
  label: string;
  value?: string | null;
  change?: string | null;
  isPositive?: boolean;
  subtext?: string | null;
}

export const KpiCard: React.FC<KpiCardProps> = ({
  label,
  value,
  change,
  isPositive = true,
  subtext,
}) => {
  const displayValue = value && value.trim() !== '' ? value : 'N/A';
  const displayChange = change && change.trim() !== '' ? change : null;
  const displaySubtext = subtext && subtext.trim() !== '' ? subtext : 'Simulated Metric';

  return (
    <div className="bg-navy-900 border border-navy-800 hover:border-gold-500/30 rounded-xl p-5 transition-all duration-300 hover:shadow-lg hover:shadow-navy-950/50 group relative overflow-hidden">
      {/* Subtle Gold Accent Top Border on Hover */}
      <div className="absolute top-0 left-0 right-0 h-0.5 bg-gradient-to-r from-transparent via-gold-500/0 to-transparent group-hover:via-gold-500/60 transition-all duration-500" />

      <div className="flex items-center justify-between text-xs text-slate-400 mb-2">
        <span className="font-medium tracking-wide uppercase text-[11px]">{label}</span>
        <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-navy-800 text-slate-400 border border-navy-700">
          DEMO
        </span>
      </div>

      <div className="flex items-baseline justify-between gap-2 mt-1">
        <span className="text-2xl font-bold tracking-tight text-white group-hover:text-gold-400 transition-colors">
          {displayValue}
        </span>
        {displayChange && (
          <div
            className={`flex items-center gap-1 text-xs font-semibold px-2 py-0.5 rounded-full ${
              isPositive
                ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                : 'bg-rose-500/10 text-rose-400 border border-rose-500/20'
            }`}
          >
            {isPositive ? (
              <ArrowUpRight className="h-3.5 w-3.5" />
            ) : (
              <ArrowDownRight className="h-3.5 w-3.5" />
            )}
            <span>{displayChange}</span>
          </div>
        )}
      </div>

      <p className="text-[11px] text-slate-400 mt-3 pt-2 border-t border-navy-800/80 flex items-center justify-between">
        <span>{displaySubtext}</span>
        <span className="text-[10px] text-emerald-400 font-mono">LIVE</span>
      </p>
    </div>
  );
};
