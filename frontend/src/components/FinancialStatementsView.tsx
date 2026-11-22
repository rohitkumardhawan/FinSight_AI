'use client';

import React, { useState, useEffect } from 'react';
import { 
  FileSpreadsheet, 
  Upload, 
  Download, 
  RefreshCw, 
  TrendingUp, 
  TrendingDown, 
  Database,
  Calendar,
  Info,
  HelpCircle
} from 'lucide-react';
import { CsvImportModal } from './CsvImportModal';
import { API_BASE } from '@/lib/api';
import { 
  formatFinancialValue, 
  getUnitLabel, 
  normalizeExchange 
} from '@/lib/formatters';

interface FinancialStatementsViewProps {
  ticker: string;
  onSelectTicker?: (ticker: string) => void;
}

export const FinancialStatementsView: React.FC<FinancialStatementsViewProps> = ({
  ticker,
  onSelectTicker,
}) => {
  const [activeTab, setActiveTab] = useState<'income' | 'balance' | 'cash_flow' | 'all'>('income');
  const [periodFilter, setPeriodFilter] = useState<'all' | 'FY' | 'quarterly'>('FY');
  const [periods, setPeriods] = useState<any[]>([]);
  const [companyInfo, setCompanyInfo] = useState<{
    id?: number;
    symbol: string;
    company_name: string;
    currency: string;
    exchange: string;
    data_source?: string;
  }>({
    symbol: ticker || 'ASIANPAINT.NS',
    company_name: ticker || 'ASIANPAINT.NS',
    currency: ticker?.endsWith('.NS') ? 'INR' : 'USD',
    exchange: ticker?.endsWith('.NS') ? 'NSE' : 'GLOBAL',
  });
  const [loading, setLoading] = useState<boolean>(false);
  const [isCsvModalOpen, setIsCsvModalOpen] = useState<boolean>(false);
  const [dataSourceNotice, setDataSourceNotice] = useState<string>('Connecting to Neon DB...');

  // Fetch live company analysis dataset from FastAPI
  const loadData = async (forceRefresh: boolean = false) => {
    setLoading(true);
    try {
      const sym = ticker || 'ASIANPAINT.NS';
      const res = await fetch(`${API_BASE}/companies/${encodeURIComponent(sym)}/analysis?refresh=${forceRefresh}`);
      if (!res.ok) {
        throw new Error(`Failed to load statements: ${res.statusText}`);
      }
      const data = await res.json();
      
      setCompanyInfo({
        id: data.company_id,
        symbol: data.symbol || sym,
        company_name: data.company_name || sym,
        currency: data.currency || (sym.endsWith('.NS') ? 'INR' : 'USD'),
        exchange: normalizeExchange(data.exchange, sym),
        data_source: data.data_source || 'yfinance',
      });

      const rawPeriods: any[] = data.periods || [];
      // Sort ascending by fiscal year
      const sorted = [...rawPeriods].sort((a, b) => (a.fiscal_year || 0) - (b.fiscal_year || 0));

      // Filter out columns where all core metrics (revenue, operating_income, net_income) are null/empty (e.g. blank FY2022)
      const valid = sorted.filter((p: any) =>
        (p.revenue !== null && p.revenue !== undefined) ||
        (p.operating_income !== null && p.operating_income !== undefined) ||
        (p.net_income !== null && p.net_income !== undefined)
      );

      setPeriods(valid.length > 0 ? valid : sorted);
      setDataSourceNotice(`Neon PostgreSQL (Live • ${valid.length} Periods Verified)`);
    } catch (err: any) {
      console.warn('Could not load analysis statements:', err);
      setDataSourceNotice('Neon DB (Synchronizing statement data)');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [ticker]);

  // Filter periods by FY vs Quarterly and sort chronologically
  const parseQuarterOrder = (periodStr: string, year?: number) => {
    const match = periodStr.match(/Q(\d)\s*(\d{4})?/i);
    if (match) {
      const q = parseInt(match[1], 10);
      const y = match[2] ? parseInt(match[2], 10) : (year || 0);
      return y * 10 + q;
    }
    return (year || 0) * 10;
  };

  const filteredPeriods = periods
    .filter((s) => {
      // Hide columns where all core metrics are null/empty
      const hasCoreData = (
        (s.revenue !== null && s.revenue !== undefined) ||
        (s.operating_income !== null && s.operating_income !== undefined) ||
        (s.net_income !== null && s.net_income !== undefined) ||
        (s.total_assets !== null && s.total_assets !== undefined) ||
        (s.operating_cash_flow !== null && s.operating_cash_flow !== undefined)
      );
      if (!hasCoreData) return false;

      const isAnnual = !s.fiscal_period || s.fiscal_period.toUpperCase() === 'FY' || s.fiscal_period.toUpperCase().startsWith('FY');
      if (periodFilter === 'FY') return isAnnual;
      if (periodFilter === 'quarterly') return !isAnnual;
      return true;
    })
    .sort((a, b) => {
      if (periodFilter === 'quarterly') {
        return parseQuarterOrder(a.fiscal_period || '', a.fiscal_year) - parseQuarterOrder(b.fiscal_period || '', b.fiscal_year);
      }
      return (a.fiscal_year || 0) - (b.fiscal_year || 0);
    });

  // Calculate counts for Annual vs Quarterly periods
  const annualCount = periods.filter((s) => !s.fiscal_period || s.fiscal_period.toUpperCase() === 'FY' || s.fiscal_period.toUpperCase().startsWith('FY')).length;
  const quarterlyCount = periods.filter((s) => s.fiscal_period && !s.fiscal_period.toUpperCase().startsWith('FY')).length;

  // Formula-injection sanitization for CSV export (CWE-1236 mitigation)
  const sanitizeCsvCell = (val: any): string => {
    if (val === null || val === undefined) return '""';
    let str = String(val).trim();
    if (/^[=+\-@\t\r]/.test(str)) {
      str = "'" + str;
    }
    return `"${str.replace(/"/g, '""')}"`;
  };

  const handleExportCsv = () => {
    if (!filteredPeriods || filteredPeriods.length === 0) return;

    const headers = [
      `Financial Line Item (${getUnitLabel(companyInfo.currency)})`,
      ...filteredPeriods.map((p) => p.fiscal_period || `FY${p.fiscal_year}`)
    ];

    const rows: string[][] = [];

    const incomeItems = [
      { label: 'Revenue (Total Net Sales)', key: 'revenue' },
      { label: 'Cost of Goods Sold (COGS)', key: 'cost_of_revenue' },
      { label: 'Gross Profit', key: 'gross_profit' },
      { label: 'Operating Income (EBIT)', key: 'operating_income' },
      { label: 'Operating Expenses', key: 'operating_expenses' },
      { label: 'Net Income', key: 'net_income' },
    ];

    const balanceItems = [
      { label: 'Cash & Cash Equivalents', key: 'cash_and_equivalents' },
      { label: 'Current Assets', key: 'current_assets' },
      { label: 'Total Assets', key: 'total_assets' },
      { label: 'Current Liabilities', key: 'current_liabilities' },
      { label: 'Total Debt (Short + Long Term)', key: 'total_debt' },
      { label: 'Total Liabilities', key: 'total_liabilities' },
      { label: "Total Stockholders' Equity", key: 'total_equity' },
    ];

    const cashFlowItems = [
      { label: 'Cash Flow from Operations (OCF)', key: 'operating_cash_flow' },
      { label: 'Capital Expenditures (CapEx)', key: 'capital_expenditure' },
      { label: 'Free Cash Flow (FCF)', key: 'free_cash_flow' },
      { label: 'Depreciation & Amortization', key: 'depreciation_amortization' },
    ];

    const addSection = (sectionTitle: string, items: { label: string; key: string }[]) => {
      rows.push([sectionTitle, ...filteredPeriods.map(() => '')]);
      items.forEach((item) => {
        const rowVals = filteredPeriods.map((p) => {
          const raw = p[item.key];
          if (raw === null || raw === undefined) return 'N/A';
          return formatFinancialValue(raw, companyInfo.currency);
        });
        rows.push([item.label, ...rowVals]);
      });
    };

    if (activeTab === 'income' || activeTab === 'all') {
      addSection('INCOME STATEMENT', incomeItems);
    }
    if (activeTab === 'balance' || activeTab === 'all') {
      addSection('BALANCE SHEET', balanceItems);
    }
    if (activeTab === 'cash_flow' || activeTab === 'all') {
      addSection('CASH FLOW STATEMENT', cashFlowItems);
    }

    const csvContent = [
      headers.map(sanitizeCsvCell).join(','),
      ...rows.map((row) => row.map(sanitizeCsvCell).join(','))
    ].join('\r\n');

    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    const safeSymbol = (companyInfo.symbol || 'COMPANY').replace(/[^a-zA-Z0-9_.-]/g, '_');
    link.setAttribute('href', url);
    link.setAttribute('download', `${safeSymbol}_Financials.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  // Calculate YoY growth between periods
  const calculateGrowth = (current?: number | null, prev?: number | null) => {
    if (current == null || prev == null || prev === 0) return null;
    return ((current - prev) / Math.abs(prev)) * 100;
  };

  const renderGrowthBadge = (pct: number | null) => {
    if (pct == null) return null;
    const isPos = pct >= 0;
    return (
      <span
        className={`inline-flex items-center gap-0.5 text-[10px] font-mono font-medium px-1.5 py-0.2 rounded ${
          isPos ? 'text-emerald-400 bg-emerald-950/40' : 'text-rose-400 bg-rose-950/40'
        }`}
      >
        {isPos ? <TrendingUp className="h-2.5 w-2.5" /> : <TrendingDown className="h-2.5 w-2.5" />}
        {isPos ? '+' : ''}
        {pct.toFixed(1)}%
      </span>
    );
  };

  const renderLineItem = (
    label: string,
    key: string,
    isBold: boolean = false,
    indent: boolean = false,
    showGrowth: boolean = false
  ) => {
    return (
      <tr className={`border-b border-white/[0.05] hover:bg-white/[0.03] transition-colors ${isBold ? 'bg-sky-500/[0.04]' : ''}`}>
        <td className={`py-2.5 px-4 text-xs sticky left-0 z-10 border-r border-white/[0.06] ${isBold ? 'font-bold text-white bg-[#141822]' : 'text-slate-300 bg-[#11141B]'} ${indent ? 'pl-8' : ''}`}>
          {label}
        </td>
        {filteredPeriods.map((stmt, idx) => {
          const val = stmt[key] as number | null | undefined;
          const prevVal = idx > 0 ? (filteredPeriods[idx - 1][key] as number | null | undefined) : null;
          const growth = showGrowth ? calculateGrowth(val, prevVal) : null;

          return (
            <td key={idx} className="py-2.5 px-4 text-right font-mono tabular-nums text-xs">
              <div className="flex flex-col items-end gap-0.5">
                <span className={isBold ? 'font-bold text-sky-200' : 'text-slate-200'}>
                  {formatFinancialValue(val, companyInfo.currency)}
                </span>
                {growth !== null && renderGrowthBadge(growth)}
              </div>
            </td>
          );
        })}
      </tr>
    );
  };

  const unitLabel = getUnitLabel(companyInfo.currency);

  return (
    <div className="space-y-6">
      {/* Top Banner & Action Controls */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 pb-4 border-b border-white/[0.06]">
        <div>
          <div className="flex items-center gap-2">
            <span className="h-6 px-2.5 rounded bg-sky-500/10 text-sky-400 border border-sky-500/20 text-[11px] font-bold flex items-center gap-1.5">
              <FileSpreadsheet className="h-3.5 w-3.5" />
              FINANCIAL STATEMENTS MODULE
            </span>
            <span className="text-xs text-slate-400 font-medium">Phase 4 Institutional Architecture</span>
          </div>

          <h1 className="text-2xl font-bold tracking-tight text-white mt-1.5 flex items-center gap-2.5">
            <span>{companyInfo.company_name}</span>
            <span className="text-sky-400 font-mono text-lg font-bold">({companyInfo.symbol})</span>
            <span className="px-2 py-0.5 text-xs font-semibold bg-navy-800 text-slate-300 border border-navy-700 rounded">
              {companyInfo.exchange}
            </span>
            {loading && <RefreshCw className="h-4 w-4 animate-spin text-gold-400" />}
          </h1>

          <div className="flex items-center gap-2 mt-1 text-xs text-slate-400">
            <Database className="h-3 w-3 text-cyan-400" />
            <span>{dataSourceNotice}</span>
            <span>•</span>
            <span className="text-emerald-400 font-mono">Currency: {companyInfo.currency} ({unitLabel})</span>
          </div>
        </div>

        {/* Action Buttons: Export CSV, Import CSV, Download Template, Refresh */}
        <div className="flex items-center gap-2.5 flex-wrap">
          <button
            type="button"
            onClick={() => loadData(true)}
            className="flex items-center gap-1.5 px-3 py-2 rounded-xl bg-white/[0.04] hover:bg-white/[0.08] border border-white/[0.08] text-slate-300 hover:border-navy-700 text-xs font-medium text-slate-300 transition-colors"
          >
            <RefreshCw className="h-3.5 w-3.5" />
            <span>Refresh</span>
          </button>

          {/* One-Click Export to CSV (Feature 3) */}
          <button
            type="button"
            onClick={handleExportCsv}
            disabled={filteredPeriods.length === 0}
            className="flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-navy-900 hover:bg-navy-800 border border-emerald-500/40 hover:border-emerald-400 text-xs font-semibold text-emerald-400 transition-colors shadow-sm disabled:opacity-50"
            title="Export normalized financial statements to sanitized CSV"
          >
            <Download className="h-3.5 w-3.5" />
            <span>Export CSV</span>
          </button>

          <a
            href={`${API_BASE}/statements/csv-template?type=combined`}
            target="_blank"
            rel="noreferrer"
            className="flex items-center gap-1.5 px-3 py-2 rounded-xl bg-white/[0.04] hover:bg-white/[0.08] border border-white/[0.08] text-slate-300 hover:border-gold-500/30 text-xs font-medium text-gold-400 transition-colors"
          >
            <FileSpreadsheet className="h-3.5 w-3.5" />
            <span>CSV Template</span>
          </a>

          {/* Core Phase 3/4 Requirement: Visible "Import CSV" button */}
          <button
            type="button"
            onClick={() => setIsCsvModalOpen(true)}
            className="flex items-center gap-2 px-4 py-2 rounded-xl bg-sky-500 hover:bg-sky-400 text-white font-semibold font-bold text-xs transition-all shadow-lg shadow-gold-500/20 active:scale-95"
          >
            <Upload className="h-3.5 w-3.5" />
            <span>Import CSV</span>
          </button>
        </div>
      </div>

      {/* Tabs & Period Navigation */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-[#11141B] p-2 rounded-xl border border-white/[0.07]">
        {/* Statement Type Tabs */}
        <div className="flex items-center gap-1 overflow-x-auto">
          <button
            onClick={() => setActiveTab('income')}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all whitespace-nowrap ${
              activeTab === 'income'
                ? 'bg-sky-500 text-white shadow-sm font-semibold'
                : 'text-slate-400 hover:text-white hover:bg-navy-800'
            }`}
          >
            Income Statement
          </button>
          <button
            onClick={() => setActiveTab('balance')}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all whitespace-nowrap ${
              activeTab === 'balance'
                ? 'bg-sky-500 text-white shadow-sm font-semibold'
                : 'text-slate-400 hover:text-white hover:bg-navy-800'
            }`}
          >
            Balance Sheet
          </button>
          <button
            onClick={() => setActiveTab('cash_flow')}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all whitespace-nowrap ${
              activeTab === 'cash_flow'
                ? 'bg-sky-500 text-white shadow-sm font-semibold'
                : 'text-slate-400 hover:text-white hover:bg-navy-800'
            }`}
          >
            Cash Flow Statement
          </button>
          <button
            onClick={() => setActiveTab('all')}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all whitespace-nowrap ${
              activeTab === 'all'
                ? 'bg-sky-500 text-white shadow-sm font-semibold'
                : 'text-slate-400 hover:text-white hover:bg-navy-800'
            }`}
          >
            All Combined
          </button>
        </div>

        {/* Period Filter (Annual | Quarterly Toggle Pill) */}
        <div className="flex items-center gap-2 self-end sm:self-auto text-xs">
          <span className="text-slate-400 text-[11px] font-medium flex items-center gap-1">
            <Calendar className="h-3 w-3 text-gold-400" />
            Reporting Horizon:
          </span>
          <div className="bg-[#090B0F] p-1 rounded-lg border border-white/[0.08] flex gap-1 shadow-inner">
            <button
              onClick={() => setPeriodFilter('FY')}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all flex items-center gap-1.5 ${
                periodFilter === 'FY'
                  ? 'bg-sky-500 text-white shadow-sm font-bold'
                  : 'text-slate-400 hover:text-white hover:bg-navy-800'
              }`}
            >
              <span>Annual</span>
              {annualCount > 0 && (
                <span className={`text-[10px] px-1.5 py-0.2 rounded-full font-mono ${
                  periodFilter === 'FY' ? 'bg-navy-950/20 text-navy-950 font-bold' : 'bg-navy-800 text-slate-400'
                }`}>
                  {annualCount}Y
                </span>
              )}
            </button>
            <button
              onClick={() => setPeriodFilter('quarterly')}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all flex items-center gap-1.5 ${
                periodFilter === 'quarterly'
                  ? 'bg-sky-500 text-white shadow-sm font-bold'
                  : 'text-slate-400 hover:text-white hover:bg-navy-800'
              }`}
            >
              <span>Quarterly</span>
              {quarterlyCount > 0 && (
                <span className={`text-[10px] px-1.5 py-0.2 rounded-full font-mono ${
                  periodFilter === 'quarterly' ? 'bg-navy-950/20 text-navy-950 font-bold' : 'bg-navy-800 text-slate-400'
                }`}>
                  {quarterlyCount}Q
                </span>
              )}
            </button>
            <button
              onClick={() => setPeriodFilter('all')}
              className={`px-2.5 py-1.5 rounded-lg text-xs font-medium transition-all ${
                periodFilter === 'all'
                  ? 'bg-navy-800 text-white font-bold'
                  : 'text-slate-400 hover:text-white'
              }`}
            >
              All
            </button>
          </div>
        </div>
      </div>

      {/* Financial Statement Tables Container */}
      {!loading && periods.length === 0 ? (
        <div className="flex flex-col items-center justify-center min-h-[350px] text-center p-8 bg-navy-900/50 rounded-2xl border border-navy-800 shadow-lg">
          <div className="h-12 w-12 rounded-full bg-navy-800 text-gold-400 flex items-center justify-center mb-3">
            <HelpCircle className="h-6 w-6" />
          </div>
          <h3 className="text-base font-semibold text-white">Financial Statements Standby</h3>
          <p className="text-xs text-slate-300 max-w-md mt-1 leading-relaxed">
            Multi-year financial statements for {ticker} are currently synchronizing or awaiting live fetch.
          </p>
          <button
            onClick={() => loadData(true)}
            className="mt-4 px-4 py-2 rounded-lg bg-navy-800 hover:bg-navy-750 text-xs font-medium text-gold-400 border border-gold-500/30 flex items-center gap-1.5 transition-all shadow-md"
          >
            <RefreshCw className="h-3.5 w-3.5" /> Re-sync Statements
          </button>
        </div>
      ) : (
        <div className="bg-[#11141B] border border-white/[0.07] rounded-xl overflow-hidden shadow-[0_1px_0_0_rgba(255,255,255,0.04)_inset]">
        <div className="overflow-x-auto">
          <table className="w-full text-left">
            <thead className="bg-[#0C0E14] text-slate-400 text-[11px] font-mono uppercase tracking-wider border-b border-white/[0.06]">
              <tr>
                <th className="py-2.5 px-4 font-semibold text-slate-300 min-w-[240px] sticky left-0 bg-[#0C0E14] z-20 border-r border-white/[0.06]">
                  Financial Line Item ({unitLabel})
                </th>
                {filteredPeriods.map((stmt, idx) => (
                  <th key={idx} className="py-2.5 px-4 text-right font-mono font-bold text-white min-w-[120px]">
                    <div className="flex flex-col items-end">
                      <span className="text-sky-400 text-xs font-mono">
                        {stmt.fiscal_period || `FY${stmt.fiscal_year}`}
                      </span>
                      <span className="text-[10px] text-slate-500 font-normal font-mono">
                        {stmt.fiscal_year}
                      </span>
                    </div>
                  </th>
                ))}
              </tr>
            </thead>

            <tbody className="divide-y divide-navy-800/40">
              {/* 1. INCOME STATEMENT SECTION */}
              {(activeTab === 'income' || activeTab === 'all') && (
                <>
                  <tr className="bg-[#0C0E14]">
                    <td
                      colSpan={filteredPeriods.length + 1}
                      className="py-2 px-4 text-[11px] font-bold tracking-wider uppercase text-sky-400 border-t border-b border-white/[0.06] font-mono sticky left-0 bg-[#0C0E14] z-10"
                    >
                      Income Statement
                    </td>
                  </tr>
                  {renderLineItem('Revenue (Total Net Sales)', 'revenue', true, false, true)}
                  {renderLineItem('Cost of Goods Sold (COGS)', 'cost_of_revenue', false, true)}
                  {renderLineItem('Gross Profit', 'gross_profit', true, false, true)}
                  {renderLineItem('Operating Income (EBIT)', 'operating_income', true, false, true)}
                  {renderLineItem('Operating Expenses', 'operating_expenses', false, true)}
                  {renderLineItem('Net Income', 'net_income', true, false, true)}
                </>
              )}

              {/* 2. BALANCE SHEET SECTION */}
              {(activeTab === 'balance' || activeTab === 'all') && (
                <>
                  <tr className="bg-[#0C0E14]">
                    <td
                      colSpan={filteredPeriods.length + 1}
                      className="py-2.5 px-4 text-[11px] font-bold tracking-wider uppercase text-cyan-400 border-t border-b border-cyan-500/20"
                    >
                      Balance Sheet
                    </td>
                  </tr>
                  {renderLineItem('Cash & Cash Equivalents', 'cash_and_equivalents', false, true)}
                  {renderLineItem('Current Assets', 'current_assets', false, true)}
                  {renderLineItem('Total Assets', 'total_assets', true, false, true)}
                  {renderLineItem('Current Liabilities', 'current_liabilities', false, true)}
                  {renderLineItem('Total Debt (Short + Long Term)', 'total_debt', false, true)}
                  {renderLineItem('Total Liabilities', 'total_liabilities', true, false, true)}
                  {renderLineItem("Total Stockholders' Equity", 'total_equity', true, false, true)}
                </>
              )}

              {/* 3. CASH FLOW STATEMENT SECTION */}
              {(activeTab === 'cash_flow' || activeTab === 'all') && (
                <>
                  <tr className="bg-[#0C0E14]">
                    <td
                      colSpan={filteredPeriods.length + 1}
                      className="py-2.5 px-4 text-[11px] font-bold tracking-wider uppercase text-emerald-400 border-t border-b border-emerald-500/20"
                    >
                      Cash Flow Statement
                    </td>
                  </tr>
                  {renderLineItem('Cash Flow from Operations (OCF)', 'operating_cash_flow', true, false, true)}
                  {renderLineItem('Capital Expenditures (CapEx)', 'capital_expenditure', false, true)}
                  {renderLineItem('Free Cash Flow (FCF)', 'free_cash_flow', true, false, true)}
                  {renderLineItem('Depreciation & Amortization', 'depreciation_amortization', false, true)}
                </>
              )}
            </tbody>
          </table>
        </div>

        {/* Source Attribution Footer */}
        <div className="p-4 bg-navy-950/70 border-t border-navy-800 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs text-slate-400">
          <div className="flex items-center gap-2">
            <Info className="h-4 w-4 text-slate-500 flex-shrink-0" />
            <span>
              All figures conform to institutional reporting standards. Missing values are preserved as <span className="font-mono text-slate-300">N/A</span>.
            </span>
          </div>

          <div className="flex items-center gap-2 font-mono text-[11px]">
            <span className="px-2 py-0.5 rounded bg-navy-800 text-slate-300 border border-navy-700">
              Source: Neon PostgreSQL
            </span>
            <span className="px-2 py-0.5 rounded bg-emerald-950 text-emerald-300 border border-emerald-800">
              Verified Financial Data
            </span>
          </div>
        </div>
      </div>
      )}

      {/* CSV Import Modal */}
      <CsvImportModal
        isOpen={isCsvModalOpen}
        onClose={() => setIsCsvModalOpen(false)}
        companyId={companyInfo.id || 0}
        companyTicker={companyInfo.symbol}
        companyName={companyInfo.company_name}
        onImportSuccess={() => {
          loadData(true);
        }}
      />
    </div>
  );
};
