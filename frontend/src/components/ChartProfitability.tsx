'use client';

import React from 'react';

interface ChartProfitabilityProps {
  grossMargin?: number | null;
  ebitdaMargin?: number | null;
  operatingMargin?: number | null;
  netMargin?: number | null;
}

export const ChartProfitability: React.FC<ChartProfitabilityProps> = ({
  grossMargin = 46.2,
  ebitdaMargin = null,
  operatingMargin = 31.4,
  netMargin = 25.8,
}) => {
  const metrics = [
    { label: 'Gross Margin', value: grossMargin, barColor: '#EAB308' },
    { label: 'EBITDA Margin', value: ebitdaMargin, barColor: '#818CF8' },
    { label: 'Operating Margin', value: operatingMargin, barColor: '#22D3EE' },
    { label: 'Net Profit Margin', value: netMargin, barColor: '#34D399' },
  ].filter((m) => m.value !== null && m.value !== undefined);

  // Fallback if all filtered out
  const displayMetrics = metrics.length > 0 ? metrics : [
    { label: 'Gross Margin', value: grossMargin, barColor: '#EAB308' },
    { label: 'Operating Margin', value: operatingMargin, barColor: '#22D3EE' },
    { label: 'Net Profit Margin', value: netMargin, barColor: '#34D399' },
  ];

  return (
    <div className="bg-[#11141B] border border-white/[0.07] rounded-xl p-5 flex flex-col justify-between shadow-[0_1px_0_0_rgba(255,255,255,0.04)_inset]">
      <div>
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <h3 className="font-semibold text-sm text-white">Profitability Margins</h3>
            <span className="text-[10px] uppercase font-mono px-1.5 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
              Live Engine
            </span>
          </div>
          <span className="text-xs text-slate-400 font-mono">LTM Normalized</span>
        </div>
        <p className="text-xs text-slate-400 mb-6">
          Operating efficiency, cash generation, and earnings retention ratios.
        </p>

        <div className="space-y-4">
          {displayMetrics.map((m) => {
            const hasData = m.value !== null && m.value !== undefined;
            return (
              <div key={m.label}>
                <div className="flex justify-between text-xs mb-1.5 font-mono">
                  <span className="text-slate-300 font-sans font-medium">{m.label}</span>
                  <span className="text-white font-bold tabular-nums">
                    {hasData ? `${m.value?.toFixed(1)}%` : 'N/A'}
                  </span>
                </div>
                <div className="h-2 w-full bg-[#090B0F] rounded-full overflow-hidden p-0.5 border border-white/[0.08]">
                  <div
                    className="h-full rounded-full transition-all duration-700"
                    style={{
                      width: hasData ? `${Math.min(Math.max(m.value || 0, 0), 100)}%` : '0%',
                      backgroundColor: hasData ? m.barColor : 'transparent',
                    }}
                  />
                </div>
              </div>
            );
          })}
        </div>
      </div>

      <div className="mt-6 pt-3 border-t border-white/[0.06] text-[11px] text-slate-400 flex items-center justify-between font-mono">
        <span>Benchmark: Top Decile</span>
        <span className="text-emerald-400 font-medium font-sans">Above Sector Median</span>
      </div>
    </div>
  );
};
