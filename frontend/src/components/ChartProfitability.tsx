'use client';

import React from 'react';
import { PieChart, Info } from 'lucide-react';

interface ChartProfitabilityProps {
  grossMargin?: number | null;
  operatingMargin?: number | null;
  netMargin?: number | null;
}

export const ChartProfitability: React.FC<ChartProfitabilityProps> = ({
  grossMargin = 46.2,
  operatingMargin = 31.4,
  netMargin = 25.8,
}) => {
  const metrics = [
    { label: 'Gross Margin', value: grossMargin, barColor: '#EAB308' },
    { label: 'Operating Margin', value: operatingMargin, barColor: '#22D3EE' },
    { label: 'Net Profit Margin', value: netMargin, barColor: '#34D399' },
  ];

  return (
    <div className="bg-navy-900 border border-navy-800 rounded-xl p-5 flex flex-col justify-between">
      <div>
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <h3 className="font-semibold text-sm text-white">Profitability Margins</h3>
            <span className="text-[10px] uppercase font-mono px-1.5 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
              Live Engine
            </span>
          </div>
          <span className="text-xs text-slate-400">LTM Normalized</span>
        </div>
        <p className="text-xs text-slate-400 mb-6">
          Operating efficiency and earnings retention ratios.
        </p>

        <div className="space-y-4">
          {metrics.map((m) => {
            const hasData = m.value !== null && m.value !== undefined;
            return (
              <div key={m.label}>
                <div className="flex justify-between text-xs mb-1.5">
                  <span className="text-slate-300 font-medium">{m.label}</span>
                  <span className="text-white font-bold font-mono">
                    {hasData ? `${m.value?.toFixed(1)}%` : 'N/A'}
                  </span>
                </div>
                <div className="h-2.5 w-full bg-navy-950 rounded-full overflow-hidden p-0.5 border border-navy-800">
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

      <div className="mt-6 pt-3 border-t border-navy-800 text-[11px] text-slate-400 flex items-center justify-between">
        <span>Benchmark: Top Decile</span>
        <span className="text-emerald-400 font-medium">Above Sector Median</span>
      </div>
    </div>
  );
};
