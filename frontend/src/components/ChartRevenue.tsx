'use client';

import React, { useState } from 'react';
import { formatFinancialValue } from '@/lib/formatters';

interface DataPoint {
  period: string;
  revenue: number;
  gross_profit: number;
  net_income: number;
}

interface ChartRevenueProps {
  data: DataPoint[];
  ticker: string;
  currency?: string;
}

export const ChartRevenue: React.FC<ChartRevenueProps> = ({ data, ticker, currency = 'INR' }) => {
  const [hoverIndex, setHoverIndex] = useState<number | null>(null);
  const [timeframe, setTimeframe] = useState<'6M' | '1Y' | '3Y' | '5Y'>('5Y');

  if (!data || data.length === 0) return null;

  // Timeframe slice
  const getFilteredData = () => {
    if (timeframe === '6M') return data.slice(-2);
    if (timeframe === '1Y') return data.slice(-3);
    if (timeframe === '3Y') return data.slice(-4);
    return data;
  };

  const activeData = getFilteredData().length > 1 ? getFilteredData() : data;

  const maxVal = Math.max(...activeData.map((d) => d.revenue), 1) * 1.15;
  const height = 240;
  const width = 560;
  const paddingX = 48;
  const paddingY = 30;

  const getX = (index: number) => {
    if (activeData.length <= 1) return width / 2;
    return paddingX + (index * (width - 2 * paddingX)) / (activeData.length - 1);
  };

  const getY = (val: number) => {
    return height - paddingY - (Math.max(val, 0) / maxVal) * (height - 2 * paddingY);
  };

  // SVG paths
  const revenuePoints = activeData.map((d, i) => `${getX(i)},${getY(d.revenue)}`).join(' ');
  const netIncomePoints = activeData.map((d, i) => `${getX(i)},${getY(d.net_income)}`).join(' ');

  const areaPath = `M ${getX(0)},${getY(activeData[0].revenue)} ${activeData
    .slice(1)
    .map((d, i) => `L ${getX(i + 1)},${getY(d.revenue)}`)
    .join(' ')} L ${getX(activeData.length - 1)},${height - paddingY} L ${getX(0)},${height - paddingY} Z`;

  return (
    <div className="bg-[#11141B] border border-white/[0.07] rounded-xl p-5 relative shadow-[0_1px_0_0_rgba(255,255,255,0.04)_inset]">
      {/* Chart Header & Controls */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4">
        <div>
          <div className="flex items-center gap-2">
            <h3 className="font-semibold text-sm text-white">Revenue & Net Income Trajectory</h3>
            <span className="text-[10px] uppercase font-mono px-1.5 py-0.2 rounded bg-sky-500/10 text-sky-400 border border-sky-500/20">
              Audited
            </span>
          </div>
          <p className="text-xs text-slate-400 mt-0.5">Multi-year financial expansion curve</p>
        </div>

        {/* Timeframe Pill Toggles & Legend */}
        <div className="flex items-center gap-3">
          {/* Timeframe Pills */}
          <div className="flex items-center bg-[#090B0F] p-0.5 rounded-lg border border-white/[0.08]">
            {(['6M', '1Y', '3Y', '5Y'] as const).map((tf) => (
              <button
                key={tf}
                onClick={() => setTimeframe(tf)}
                className={`px-2 py-0.5 text-[10px] font-mono font-medium rounded transition-all ${
                  timeframe === tf
                    ? 'bg-sky-500 text-white font-bold shadow-sm'
                    : 'text-slate-400 hover:text-white'
                }`}
              >
                {tf}
              </button>
            ))}
          </div>

          {/* Legend */}
          <div className="hidden sm:flex items-center gap-3 text-xs pl-2 border-l border-white/[0.08]">
            <div className="flex items-center gap-1.5 text-slate-300 text-[11px]">
              <span className="h-2 w-2 rounded-full bg-sky-400 shadow-sm shadow-sky-400/50" />
              <span>Revenue</span>
            </div>
            <div className="flex items-center gap-1.5 text-slate-300 text-[11px]">
              <span className="h-2 w-2 rounded-full bg-emerald-400" />
              <span>Net Income</span>
            </div>
          </div>
        </div>
      </div>

      {/* SVG Chart */}
      <div className="w-full overflow-hidden">
        <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-60 overflow-visible">
          <defs>
            <linearGradient id="skyAreaGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#38BDF8" stopOpacity="0.22" />
              <stop offset="100%" stopColor="#38BDF8" stopOpacity="0.0" />
            </linearGradient>
          </defs>

          {/* Grid lines */}
          {[0.25, 0.5, 0.75, 1.0].map((ratio, i) => {
            const y = height - paddingY - ratio * (height - 2 * paddingY);
            return (
              <g key={i}>
                <line
                  x1={paddingX}
                  y1={y}
                  x2={width - paddingX}
                  y2={y}
                  stroke="rgba(255, 255, 255, 0.06)"
                  strokeDasharray="3 3"
                  strokeWidth="0.8"
                />
                <text
                  x={paddingX - 8}
                  y={y + 3}
                  fill="#64748B"
                  fontSize="9"
                  fontFamily="monospace"
                  textAnchor="end"
                >
                  {formatFinancialValue(ratio * maxVal, currency)}
                </text>
              </g>
            );
          })}

          {/* Area fill */}
          <path d={areaPath} fill="url(#skyAreaGrad)" />

          {/* Revenue Line */}
          <polyline
            fill="none"
            stroke="#38BDF8"
            strokeWidth="2.5"
            strokeLinecap="round"
            strokeLinejoin="round"
            points={revenuePoints}
          />

          {/* Net Income Line */}
          <polyline
            fill="none"
            stroke="#10B981"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeDasharray="3 3"
            points={netIncomePoints}
          />

          {/* Data Points & Dark Glass Tooltip */}
          {activeData.map((d, i) => {
            const cx = getX(i);
            const cy = getY(d.revenue);
            const isHovered = hoverIndex === i;

            return (
              <g key={i} className="cursor-pointer">
                {/* Period label */}
                <text
                  x={cx}
                  y={height - paddingY + 18}
                  fill="#94A3B8"
                  fontSize="10"
                  fontFamily="monospace"
                  textAnchor="middle"
                  fontWeight={isHovered ? 'bold' : 'normal'}
                >
                  {d.period}
                </text>

                {/* Point dot */}
                <circle
                  cx={cx}
                  cy={cy}
                  r={isHovered ? 6 : 4}
                  fill="#090B0F"
                  stroke="#38BDF8"
                  strokeWidth="2"
                  className="transition-all"
                  onMouseEnter={() => setHoverIndex(i)}
                  onMouseLeave={() => setHoverIndex(null)}
                />

                {/* Dark Glass Tooltip with tabular-nums */}
                {isHovered && (
                  <g pointerEvents="none">
                    <line
                      x1={cx}
                      y1={paddingY}
                      x2={cx}
                      y2={height - paddingY}
                      stroke="rgba(56, 189, 248, 0.4)"
                      strokeWidth="1"
                      strokeDasharray="2 2"
                    />
                    <rect
                      x={Math.min(Math.max(cx - 65, 10), width - 140)}
                      y={Math.max(cy - 52, 5)}
                      width="130"
                      height="46"
                      rx="8"
                      fill="#0C0E14"
                      stroke="rgba(255, 255, 255, 0.15)"
                      strokeWidth="1"
                    />
                    <text
                      x={Math.min(Math.max(cx - 65, 10) + 65, width - 75)}
                      y={Math.max(cy - 52, 5) + 16}
                      fill="#F8FAFC"
                      fontSize="10"
                      fontFamily="monospace"
                      textAnchor="middle"
                      fontWeight="bold"
                    >
                      {d.period}
                    </text>
                    <text
                      x={Math.min(Math.max(cx - 65, 10) + 65, width - 75)}
                      y={Math.max(cy - 52, 5) + 29}
                      fill="#38BDF8"
                      fontSize="9"
                      fontFamily="monospace"
                      textAnchor="middle"
                    >
                      Rev: {formatFinancialValue(d.revenue, currency)}
                    </text>
                    <text
                      x={Math.min(Math.max(cx - 65, 10) + 65, width - 75)}
                      y={Math.max(cy - 52, 5) + 40}
                      fill="#10B981"
                      fontSize="9"
                      fontFamily="monospace"
                      textAnchor="middle"
                    >
                      Net: {formatFinancialValue(d.net_income, currency)}
                    </text>
                  </g>
                )}
              </g>
            );
          })}
        </svg>
      </div>
    </div>
  );
};
