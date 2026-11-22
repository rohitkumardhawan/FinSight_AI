'use client';

import React, { useState } from 'react';
import { TrendingUp, BarChart3, HelpCircle } from 'lucide-react';

interface DataPoint {
  period: string;
  revenue: number;
  gross_profit: number;
  net_income: number;
}

interface ChartRevenueProps {
  data: DataPoint[];
  ticker: string;
}

export const ChartRevenue: React.FC<ChartRevenueProps> = ({ data, ticker }) => {
  const [hoverIndex, setHoverIndex] = useState<number | null>(null);

  if (!data || data.length === 0) return null;

  const maxVal = Math.max(...data.map((d) => d.revenue)) * 1.15;
  const height = 220;
  const width = 500;
  const paddingX = 40;
  const paddingY = 25;

  const getX = (index: number) => {
    return paddingX + (index * (width - 2 * paddingX)) / (data.length - 1);
  };

  const getY = (val: number) => {
    return height - paddingY - (val / maxVal) * (height - 2 * paddingY);
  };

  // Generate SVG path for revenue line
  const revenuePoints = data.map((d, i) => `${getX(i)},${getY(d.revenue)}`).join(' ');
  const netIncomePoints = data.map((d, i) => `${getX(i)},${getY(d.net_income)}`).join(' ');

  // Gradient area path
  const areaPath = `M ${getX(0)},${getY(data[0].revenue)} ${data
    .slice(1)
    .map((d, i) => `L ${getX(i + 1)},${getY(d.revenue)}`)
    .join(' ')} L ${getX(data.length - 1)},${height - paddingY} L ${getX(0)},${height - paddingY} Z`;

  return (
    <div className="bg-navy-900 border border-navy-800 rounded-xl p-5 relative">
      <div className="flex items-center justify-between mb-4">
        <div>
          <div className="flex items-center gap-2">
            <h3 className="font-semibold text-sm text-white">Revenue & Net Income Trajectory</h3>
            <span className="text-[10px] uppercase font-mono px-1.5 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
              Live Engine
            </span>
          </div>
          <p className="text-xs text-slate-400 mt-0.5">Multi-year trend analysis (Billions USD)</p>
        </div>
        <div className="flex items-center gap-4 text-xs">
          <div className="flex items-center gap-1.5 text-slate-300">
            <span className="h-2 w-2 rounded-full bg-gold-accent shadow-sm shadow-gold-accent/50" />
            <span>Revenue</span>
          </div>
          <div className="flex items-center gap-1.5 text-slate-300">
            <span className="h-2 w-2 rounded-full bg-emerald-400" />
            <span>Net Income</span>
          </div>
        </div>
      </div>

      {/* SVG Chart */}
      <div className="w-full overflow-hidden">
        <svg
          viewBox={`0 0 ${width} ${height}`}
          className="w-full h-56 overflow-visible"
        >
          <defs>
            <linearGradient id="goldAreaGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#D4AF37" stopOpacity="0.25" />
              <stop offset="100%" stopColor="#D4AF37" stopOpacity="0.0" />
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
                  stroke="#1E2F52"
                  strokeDasharray="4 4"
                  strokeWidth="0.8"
                />
                <text
                  x={paddingX - 8}
                  y={y + 3}
                  fill="#64748B"
                  fontSize="9"
                  textAnchor="end"
                >
                  ${Math.round(ratio * maxVal)}B
                </text>
              </g>
            );
          })}

          {/* Area fill */}
          <path d={areaPath} fill="url(#goldAreaGrad)" />

          {/* Revenue Line */}
          <polyline
            fill="none"
            stroke="#D4AF37"
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

          {/* Data Points */}
          {data.map((d, i) => {
            const cx = getX(i);
            const cy = getY(d.revenue);
            const isHovered = hoverIndex === i;

            return (
              <g key={i} className="cursor-pointer">
                {/* Year label */}
                <text
                  x={cx}
                  y={height - paddingY + 16}
                  fill="#94A3B8"
                  fontSize="10"
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
                  fill="#0B1220"
                  stroke="#D4AF37"
                  strokeWidth="2"
                  className="transition-all"
                  onMouseEnter={() => setHoverIndex(i)}
                  onMouseLeave={() => setHoverIndex(null)}
                />

                {/* Hover indicator line & tooltip */}
                {isHovered && (
                  <g>
                    <line
                      x1={cx}
                      y1={paddingY}
                      x2={cx}
                      y2={height - paddingY}
                      stroke="#EAB308"
                      strokeWidth="1"
                      strokeDasharray="2 2"
                    />
                    <rect
                      x={cx - 50}
                      y={cy - 45}
                      width="100"
                      height="38"
                      rx="6"
                      fill="#0F172A"
                      stroke="#334155"
                      strokeWidth="1"
                    />
                    <text
                      x={cx}
                      y={cy - 30}
                      fill="#F8FAFC"
                      fontSize="10"
                      textAnchor="middle"
                      fontWeight="bold"
                    >
                      Rev: ${d.revenue}B
                    </text>
                    <text
                      x={cx}
                      y={cy - 16}
                      fill="#10B981"
                      fontSize="9"
                      textAnchor="middle"
                    >
                      Net Inc: ${d.net_income}B
                    </text>
                  </g>
                )}
              </g>
            );
          })}
        </svg>
      </div>

      <div className="mt-3 pt-3 border-t border-navy-800 flex items-center justify-between text-[11px] text-slate-400">
        <span>CAGR Projection: +11.4%</span>
        <span className="text-gold-400 font-medium">Demonstration Multiples</span>
      </div>
    </div>
  );
};
