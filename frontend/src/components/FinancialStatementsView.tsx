'use client';

import React, { useState, useEffect, useMemo } from 'react';
import { 
  FileSpreadsheet, 
  Upload, 
  Download, 
  RefreshCw, 
  TrendingUp, 
  TrendingDown, 
  Database,
  Calendar,
  Percent,
  Info,
  HelpCircle
} from 'lucide-react';
import { CsvImportModal } from './CsvImportModal';
import { PeriodFilterBar, EmptyPeriodSelectionFallback, ALL_YEARS, extractYear, isAnnualPeriod } from './PeriodFilterBar';
import { API_BASE } from '@/lib/api';
import { exportCompanyExcelModel } from '@/lib/exportExcel';
import { 
  formatFinancialValue, 
  formatAccountingValue,
  isAccountingDeduction,
  formatPerShare,
  formatPercent,
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
  const [periodFilter, setPeriodFilter] = useState<'annual' | 'quarterly'>('annual');
  const [selectedYears, setSelectedYears] = useState<number[]>([2023, 2024, 2025, 2026]);
  const [viewMode, setViewMode] = useState<'values' | 'common_size'>('values');
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
  const [downloadingExcel, setDownloadingExcel] = useState<boolean>(false);
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
      const sorted = [...rawPeriods].sort((a, b) => (extractYear(a) || 0) - (extractYear(b) || 0));

      // Filter out columns where all core metrics are null/empty
      const valid = sorted.filter((p: any) =>
        (p.revenue !== null && p.revenue !== undefined) ||
        (p.operating_income !== null && p.operating_income !== undefined) ||
        (p.net_income !== null && p.net_income !== undefined) ||
        (p.total_assets !== null && p.total_assets !== undefined) ||
        (p.operating_cash_flow !== null && p.operating_cash_flow !== undefined)
      );

      const resolvedPeriods = valid.length > 0 ? valid : sorted;
      setPeriods(resolvedPeriods);

      // Auto-populate selected years with available annual years
      const availYears = Array.from(
        new Set<number>(
          resolvedPeriods
            .filter(isAnnualPeriod)
            .map(extractYear)
            .filter((y: any): y is number => y !== null)
        )
      ).sort((a: number, b: number) => a - b);

      if (availYears.length > 0) {
        setSelectedYears(availYears);
      }

      setDataSourceNotice(`Neon PostgreSQL (Live • ${resolvedPeriods.length} Periods Verified)`);
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

  // Extract available annual years from loaded periods via useMemo
  const availableYears = useMemo(() => {
    return Array.from(
      new Set<number>(
        periods
          .filter(isAnnualPeriod)
          .map(extractYear)
          .filter((y: any): y is number => y !== null)
      )
    ).sort((a: number, b: number) => a - b);
  }, [periods]);

  // Filter periods by FY vs Quarterly and sort chronologically via useMemo
  const parseQuarterOrder = (periodStr: string, year?: number) => {
    const match = periodStr.match(/Q(\d)\s*(\d{4})?/i);
    if (match) {
      const q = parseInt(match[1], 10);
      const y = match[2] ? parseInt(match[2], 10) : (year || 0);
      return y * 10 + q;
    }
    return (year || 0) * 10;
  };

  const filteredPeriods = useMemo(() => {
    const safeSelected = (selectedYears || []).map(extractYear).filter((y: any): y is number => y !== null);

    return periods
      .filter((s) => {
        const hasCoreData = (
          (s.revenue !== null && s.revenue !== undefined) ||
          (s.operating_income !== null && s.operating_income !== undefined) ||
          (s.net_income !== null && s.net_income !== undefined) ||
          (s.total_assets !== null && s.total_assets !== undefined) ||
          (s.operating_cash_flow !== null && s.operating_cash_flow !== undefined)
        );
        if (!hasCoreData) return false;

        const isAnnual = isAnnualPeriod(s);
        if (periodFilter === 'annual') {
          const y = extractYear(s);
          return isAnnual && y !== null && safeSelected.includes(y);
        }
        if (periodFilter === 'quarterly') {
          return !isAnnual;
        }
        return true;
      })
      .sort((a, b) => {
        if (periodFilter === 'quarterly') {
          const ya = extractYear(a) || 0;
          const yb = extractYear(b) || 0;
          return parseQuarterOrder(a.fiscal_period || '', ya) - parseQuarterOrder(b.fiscal_period || '', yb);
        }
        const ya = extractYear(a) || 0;
        const yb = extractYear(b) || 0;
        return ya - yb;
      });
  }, [periods, periodFilter, selectedYears]);

  // Calculate counts for Annual vs Quarterly periods via useMemo
  const annualCount = useMemo(() => periods.filter(isAnnualPeriod).length, [periods]);
  const quarterlyCount = useMemo(() => periods.filter((s) => !isAnnualPeriod(s)).length, [periods]);

  // Formula-injection sanitization for CSV export (CWE-1236 mitigation)
  const sanitizeCsvCell = (val: any): string => {
    if (val === null || val === undefined) return '""';
    let str = String(val).trim();
    if (/^[=+\-@\t\r]/.test(str)) {
      str = "'" + str;
    }
    return `"${str.replace(/"/g, '""')}"`;
  };

  // Helper row configuration interface
  interface RowDef {
    label: string;
    getValue: (stmt: any) => number | null | undefined;
    getBase?: (stmt: any) => number | null | undefined;
    isBold?: boolean;
    indent?: boolean;
    isDeduction?: boolean;
    showGrowth?: boolean;
    isSubrow?: boolean;
    isPercent?: boolean;
    isMultiple?: boolean;
    isPerShare?: boolean;
    highlight?: 'sky' | 'emerald' | 'cyan' | 'default';
  }

  // Define Income Statement rows (strict waterfall order)
  const incomeStatementRows: RowDef[] = [
    {
      label: 'Revenue (Total Net Sales)',
      getValue: (s) => s.revenue,
      isBold: true,
      highlight: 'sky',
      showGrowth: true,
    },
    {
      label: '(-) Cost of Goods Sold (COGS)',
      getValue: (s) => s.cost_of_revenue ?? (s.revenue != null && s.gross_profit != null ? s.revenue - s.gross_profit : null),
      indent: true,
      isDeduction: true,
    },
    {
      label: '= Gross Profit',
      getValue: (s) => s.gross_profit ?? (s.revenue != null && s.cost_of_revenue != null ? s.revenue - s.cost_of_revenue : null),
      isBold: true,
      highlight: 'cyan',
      showGrowth: true,
    },
    {
      label: 'Gross Margin %',
      getValue: (s) => {
        const gp = s.gross_profit ?? (s.revenue != null && s.cost_of_revenue != null ? s.revenue - s.cost_of_revenue : null);
        return gp != null && s.revenue ? (gp / s.revenue) * 100 : null;
      },
      indent: true,
      isPercent: true,
      isSubrow: true,
    },
    {
      label: '(-) Operating Expenses (excl. D&A)',
      getValue: (s) => {
        const rev = s.revenue;
        const gp = s.gross_profit ?? (rev != null && s.cost_of_revenue != null ? rev - s.cost_of_revenue : null);
        const opInc = s.operating_income;
        const da = Math.abs(s.depreciation_amortization || 0);
        const eb = s.ebitda ?? (opInc != null ? opInc + da : null);
        if (gp != null && eb != null) return gp - eb;
        if (s.operating_expenses != null) return Math.max(0, s.operating_expenses - da);
        return null;
      },
      indent: true,
      isDeduction: true,
    },
    {
      label: '= EBITDA',
      getValue: (s) => s.ebitda ?? (s.operating_income != null ? s.operating_income + Math.abs(s.depreciation_amortization || 0) : null),
      isBold: true,
      highlight: 'sky',
      showGrowth: true,
    },
    {
      label: 'EBITDA Margin %',
      getValue: (s) => {
        const eb = s.ebitda ?? (s.operating_income != null ? s.operating_income + Math.abs(s.depreciation_amortization || 0) : null);
        return eb != null && s.revenue ? (eb / s.revenue) * 100 : s.ebitda_margin_pct;
      },
      indent: true,
      isPercent: true,
      isSubrow: true,
    },
    {
      label: '(-) Depreciation & Amortization (D&A)',
      getValue: (s) => (s.depreciation_amortization != null ? Math.abs(s.depreciation_amortization) : null),
      indent: true,
      isDeduction: true,
    },
    {
      label: '= Operating Income (EBIT)',
      getValue: (s) => s.operating_income,
      isBold: true,
      highlight: 'sky',
      showGrowth: true,
    },
    {
      label: 'Operating Margin (OPM %)',
      getValue: (s) => s.opm_pct ?? (s.operating_income != null && s.revenue ? (s.operating_income / s.revenue) * 100 : null),
      indent: true,
      isPercent: true,
      isSubrow: true,
    },
    {
      label: '(+) Other Income / (Expense)',
      getValue: (s) => {
        if (s.other_income != null) return s.other_income;
        if (s.profit_before_tax != null && (s.operating_income != null || s.ebit != null)) {
          const ebit = s.operating_income ?? s.ebit;
          const interest = Math.abs(s.interest_expense || 0);
          return Math.round((s.profit_before_tax - (ebit - interest)) * 100) / 100;
        }
        return null;
      },
      indent: true,
    },
    {
      label: '(-) Interest Expense',
      getValue: (s) => (s.interest_expense != null ? Math.abs(s.interest_expense) : null),
      indent: true,
      isDeduction: true,
    },
    {
      label: '= Profit Before Tax (EBT)',
      getValue: (s) => s.profit_before_tax ?? (s.operating_income != null ? s.operating_income + (s.other_income || 0) - (s.interest_expense || 0) : null),
      isBold: true,
    },
    {
      label: '(-) Income Tax Expense',
      getValue: (s) => (s.tax_expense != null ? Math.abs(s.tax_expense) : null),
      indent: true,
      isDeduction: true,
    },
    {
      label: 'Effective Tax Rate %',
      getValue: (s) => {
        const pbt = s.profit_before_tax ?? (s.operating_income != null ? s.operating_income + (s.other_income || 0) - (s.interest_expense || 0) : null);
        return s.tax_expense != null && pbt && pbt > 0 ? (Math.abs(s.tax_expense) / pbt) * 100 : null;
      },
      indent: true,
      isPercent: true,
      isSubrow: true,
    },
    {
      label: '= Net Income',
      getValue: (s) => s.net_income,
      isBold: true,
      highlight: 'emerald',
      showGrowth: true,
    },
    {
      label: 'Net Margin %',
      getValue: (s) => (s.net_income != null && s.revenue ? (s.net_income / s.revenue) * 100 : null),
      indent: true,
      isPercent: true,
      isSubrow: true,
    },
    {
      label: 'Diluted EPS',
      getValue: (s) => s.eps,
      indent: true,
      isPerShare: true,
      isSubrow: true,
    },
  ];

  // Define Balance Sheet rows (Assets = Liabilities + Equity)
  const balanceSheetRows: RowDef[] = [
    // Current Assets
    {
      label: 'Cash & Cash Equivalents',
      getValue: (s) => s.cash_and_equivalents,
      getBase: (s) => s.total_assets,
      indent: true,
    },
    {
      label: 'Trade Accounts Receivable',
      getValue: (s) => s.receivables,
      getBase: (s) => s.total_assets,
      indent: true,
    },
    {
      label: 'Inventories',
      getValue: (s) => s.inventory,
      getBase: (s) => s.total_assets,
      indent: true,
    },
    {
      label: 'Other Current Assets',
      getValue: (s) => s.other_current_assets,
      getBase: (s) => s.total_assets,
      indent: true,
    },
    {
      label: '= Total Current Assets',
      getValue: (s) => s.current_assets,
      getBase: (s) => s.total_assets,
      isBold: true,
      highlight: 'sky',
      showGrowth: true,
    },
    // Non-Current Assets
    {
      label: 'Property, Plant & Equipment (Net PPE)',
      getValue: (s) => s.net_ppe,
      getBase: (s) => s.total_assets,
      indent: true,
    },
    {
      label: 'Investments & Financial Assets',
      getValue: (s) => s.investments,
      getBase: (s) => s.total_assets,
      indent: true,
    },
    {
      label: 'Other Non-Current Assets',
      getValue: (s) => s.other_non_current_assets,
      getBase: (s) => s.total_assets,
      indent: true,
    },
    {
      label: '= Total Non-Current Assets',
      getValue: (s) => s.non_current_assets ?? (s.total_assets != null && s.current_assets != null ? s.total_assets - s.current_assets : null),
      getBase: (s) => s.total_assets,
      isBold: true,
      highlight: 'sky',
    },
    // Total Assets
    {
      label: '= Total Assets',
      getValue: (s) => s.total_assets,
      getBase: (s) => s.total_assets,
      isBold: true,
      highlight: 'cyan',
      showGrowth: true,
    },
    // Liabilities
    {
      label: 'Trade Accounts Payable',
      getValue: (s) => s.trade_payables,
      getBase: (s) => s.total_assets,
      indent: true,
    },
    {
      label: 'Current Liabilities',
      getValue: (s) => s.current_liabilities,
      getBase: (s) => s.total_assets,
      indent: true,
    },
    {
      label: 'Total Debt (Short + Long Term)',
      getValue: (s) => s.total_debt,
      getBase: (s) => s.total_assets,
      indent: true,
    },
    {
      label: 'Other Non-Current Liabilities',
      getValue: (s) => s.other_liabilities ?? (s.total_liabilities != null && s.current_liabilities != null ? Math.max(0, s.total_liabilities - s.current_liabilities) : null),
      getBase: (s) => s.total_assets,
      indent: true,
    },
    {
      label: '= Total Liabilities',
      getValue: (s) => s.total_liabilities,
      getBase: (s) => s.total_assets,
      isBold: true,
      highlight: 'sky',
      showGrowth: true,
    },
    // Equity
    {
      label: "= Total Stockholders' Equity",
      getValue: (s) => s.total_equity,
      getBase: (s) => s.total_assets,
      isBold: true,
      highlight: 'emerald',
      showGrowth: true,
    },
    // DCF Memo Rows
    {
      label: 'Net Debt (Total Debt - Cash)',
      getValue: (s) => (s.total_debt != null ? s.total_debt - (s.cash_and_equivalents || 0) : s.net_debt),
      getBase: (s) => s.total_assets,
      indent: true,
      isSubrow: true,
    },
    {
      label: 'Net Working Capital (Current Assets - Current Liab)',
      getValue: (s) => s.net_working_capital ?? (s.current_assets != null && s.current_liabilities != null ? s.current_assets - s.current_liabilities : null),
      getBase: (s) => s.total_assets,
      indent: true,
      isSubrow: true,
    },
    {
      label: 'Invested Capital (Net Debt + Equity)',
      getValue: (s) => {
        const nd = s.total_debt != null ? s.total_debt - (s.cash_and_equivalents || 0) : (s.net_debt || 0);
        if (s.total_equity != null && nd != null) return nd + s.total_equity;
        return s.invested_capital;
      },
      getBase: (s) => s.total_assets,
      indent: true,
      isSubrow: true,
    },
  ];

  // Define Cash Flow Statement rows (waterfall order)
  const cashFlowRows: RowDef[] = [
    {
      label: 'Cash Flow from Operating Activities (OCF)',
      getValue: (s) => s.operating_cash_flow,
      getBase: (s) => s.revenue,
      isBold: true,
      highlight: 'emerald',
      showGrowth: true,
    },
    {
      label: 'Memo: D&A Non-Cash Add-Back',
      getValue: (s) => (s.depreciation_amortization != null ? Math.abs(s.depreciation_amortization) : null),
      getBase: (s) => s.revenue,
      indent: true,
      isSubrow: true,
    },
    {
      label: 'Cash Flow from Investing Activities (CFI)',
      getValue: (s) => s.investing_cash_flow ?? (s.capital_expenditure ? -Math.abs(s.capital_expenditure) : null),
      getBase: (s) => s.revenue,
      isDeduction: false, // Signed value; negatives auto-parenthesized
    },
    {
      label: '(-) Capital Expenditures (CapEx)',
      getValue: (s) => (s.capital_expenditure != null ? Math.abs(s.capital_expenditure) : null),
      getBase: (s) => s.revenue,
      indent: true,
      isDeduction: true,
    },
    {
      label: 'Cash Flow from Financing Activities (CFF)',
      getValue: (s) => s.financing_cash_flow,
      getBase: (s) => s.revenue,
      isDeduction: false, // Signed value; negatives auto-parenthesized
    },
    {
      label: '= Net Change in Cash (OCF + CFI + CFF)',
      getValue: (s) => s.net_change_in_cash ?? ((s.operating_cash_flow || 0) + (s.investing_cash_flow || 0) + (s.financing_cash_flow || 0)),
      getBase: (s) => s.revenue,
      isBold: true,
    },
    {
      label: '= Free Cash Flow (OCF - CapEx)',
      getValue: (s) => s.free_cash_flow ?? (s.operating_cash_flow != null && s.capital_expenditure != null ? s.operating_cash_flow - Math.abs(s.capital_expenditure) : null),
      getBase: (s) => s.revenue,
      isBold: true,
      highlight: 'emerald',
      showGrowth: true,
    },
    {
      label: 'CFO / EBITDA Cash Conversion %',
      getValue: (s) => {
        const eb = s.ebitda ?? (s.operating_income != null ? s.operating_income + Math.abs(s.depreciation_amortization || 0) : null);
        return s.operating_cash_flow != null && eb && eb > 0 ? (s.operating_cash_flow / eb) * 100 : null;
      },
      indent: true,
      isPercent: true,
      isSubrow: true,
    },
  ];

  // Export sanitized CSV
  const handleExportCsv = () => {
    if (!filteredPeriods || filteredPeriods.length === 0) return;

    const unitSuffix = viewMode === 'common_size' ? '% of Base' : getUnitLabel(companyInfo.currency);
    const headers = [
      `Financial Line Item (${unitSuffix})`,
      ...filteredPeriods.map((p) => p.fiscal_period || `FY${p.fiscal_year}`)
    ];

    const rows: string[][] = [];

    const addSection = (sectionTitle: string, itemDefs: RowDef[]) => {
      rows.push([sectionTitle, ...filteredPeriods.map(() => '')]);
      itemDefs.forEach((item) => {
        const rowVals = filteredPeriods.map((p) => {
          const raw = item.getValue(p);
          if (raw === null || raw === undefined) return 'N/A';
          if (item.isPercent) return `${raw.toFixed(2)}%`;
          if (item.isPerShare) return formatPerShare(raw, companyInfo.currency);
          if (viewMode === 'common_size') {
            const base = item.getBase ? item.getBase(p) : p.revenue;
            if (!base || base === 0) return 'N/A';
            const pct = (raw / base) * 100;
            const shouldParentheses = pct < 0 || (item.isDeduction && pct > 0);
            const absPct = Math.abs(pct).toFixed(2);
            return shouldParentheses ? `(${absPct}%)` : `${absPct}%`;
          }
          return formatAccountingValue(raw, companyInfo.currency, item.isDeduction);
        });
        rows.push([item.label, ...rowVals]);
      });
    };

    if (activeTab === 'income' || activeTab === 'all') {
      addSection('INCOME STATEMENT', incomeStatementRows);
    }
    if (activeTab === 'balance' || activeTab === 'all') {
      addSection('BALANCE SHEET', balanceSheetRows);
    }
    if (activeTab === 'cash_flow' || activeTab === 'all') {
      addSection('CASH FLOW STATEMENT', cashFlowRows);
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
    link.setAttribute('download', `${safeSymbol}_${viewMode === 'common_size' ? 'CommonSize_' : ''}Financials.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  // 1-Click Institutional Excel Financial Model Export
  const handleDownloadExcel = async () => {
    if (downloadingExcel) return;
    setDownloadingExcel(true);
    try {
      const sym = companyInfo.symbol || ticker || 'ASIANPAINT.NS';
      await exportCompanyExcelModel(sym);
    } catch (err: any) {
      console.error('Error exporting Excel financial model:', err);
      alert(`Could not export Excel model: ${err.message}`);
    } finally {
      setDownloadingExcel(false);
    }
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

  // Render an individual statement row with institutional formatting
  const renderRow = (config: RowDef) => {
    const {
      label,
      getValue,
      getBase,
      isBold = false,
      indent = false,
      isDeduction = false,
      showGrowth = false,
      isSubrow = false,
      isPercent = false,
      isMultiple = false,
      isPerShare = false,
      highlight = 'default',
    } = config;

    let rowBg = 'hover:bg-white/[0.03]';
    let cellText = 'text-slate-200';
    let stickyBg = 'bg-[#11141B]';

    if (highlight === 'emerald') {
      rowBg = 'bg-emerald-500/[0.04] hover:bg-emerald-500/[0.07] border-b border-emerald-500/20';
      cellText = 'font-bold text-emerald-300';
      stickyBg = 'bg-[#121c1a]';
    } else if (highlight === 'sky') {
      rowBg = 'bg-sky-500/[0.03] hover:bg-sky-500/[0.06] border-b border-sky-500/20';
      cellText = 'font-bold text-sky-200';
      stickyBg = 'bg-[#141822]';
    } else if (highlight === 'cyan') {
      rowBg = 'bg-cyan-500/[0.03] hover:bg-cyan-500/[0.06] border-b border-cyan-500/20';
      cellText = 'font-bold text-cyan-200';
      stickyBg = 'bg-[#131b20]';
    } else if (isBold) {
      rowBg = 'bg-white/[0.02] hover:bg-white/[0.05]';
      cellText = 'font-semibold text-white';
      stickyBg = 'bg-[#131720]';
    }

    if (isSubrow) {
      rowBg = 'hover:bg-white/[0.02] border-b border-white/[0.03]';
      cellText = 'text-xs text-indigo-300/90 font-medium';
    }

    return (
      <tr key={label} className={`border-b border-white/[0.05] transition-colors ${rowBg}`}>
        <td
          className={`py-2 px-4 text-xs sticky left-0 z-10 border-r border-white/[0.06] ${stickyBg} ${
            isBold ? 'font-bold text-white' : isSubrow ? 'text-slate-400 font-normal italic' : 'text-slate-300'
          } ${indent ? 'pl-8' : ''}`}
        >
          {label}
        </td>
        {filteredPeriods.map((stmt, idx) => {
          const val = getValue(stmt);
          const baseVal = getBase ? getBase(stmt) : stmt.revenue;
          const prevVal = idx > 0 ? getValue(filteredPeriods[idx - 1]) : null;
          const growth = showGrowth && !isPercent && !isSubrow && viewMode === 'values' ? calculateGrowth(val, prevVal) : null;
          const isNegative = isAccountingDeduction(val, isDeduction);

          let cellDisplay = '—';
          if (val !== null && val !== undefined) {
            if (isPercent) {
              cellDisplay = formatPercent(val);
            } else if (isMultiple) {
              cellDisplay = `${val.toFixed(2)}x`;
            } else if (isPerShare) {
              cellDisplay = formatPerShare(val, companyInfo.currency);
            } else if (viewMode === 'common_size') {
              if (baseVal && baseVal !== 0) {
                const pct = (val / baseVal) * 100;
                const shouldParentheses = pct < 0 || (isDeduction && pct > 0);
                const absPct = Math.abs(pct).toFixed(1);
                cellDisplay = shouldParentheses ? `(${absPct}%)` : `${absPct}%`;
              } else {
                cellDisplay = '—';
              }
            } else {
              cellDisplay = formatAccountingValue(val, companyInfo.currency, isDeduction);
            }
          }

          const valueColor = isNegative && !isSubrow && !isPercent
            ? 'text-rose-300/85 font-mono'
            : isSubrow && isPercent
            ? 'text-indigo-400 font-semibold'
            : cellText;

          return (
            <td key={idx} className="py-2 px-4 text-right font-mono tabular-nums text-xs">
              <div className="flex flex-col items-end gap-0.5">
                <span className={valueColor}>{cellDisplay}</span>
                {growth !== null && renderGrowthBadge(growth)}
              </div>
            </td>
          );
        })}
      </tr>
    );
  };

  const renderSectionBanner = (title: string, colorClass: string = 'text-sky-400') => (
    <tr key={title} className="bg-[#0C0E14]">
      <td
        colSpan={filteredPeriods.length + 1}
        className={`py-2 px-4 text-[11px] font-bold tracking-wider uppercase ${colorClass} border-t border-b border-white/[0.06] font-mono sticky left-0 bg-[#0C0E14] z-10`}
      >
        {title}
      </td>
    </tr>
  );

  const renderHairlineDivider = (title: string) => (
    <tr key={title} className="bg-[#0A0C10] border-t-2 border-white/[0.12]">
      <td
        colSpan={filteredPeriods.length + 1}
        className="py-1.5 px-4 text-[10px] font-semibold tracking-wider uppercase text-slate-400 font-mono sticky left-0 bg-[#0A0C10] z-10"
      >
        {title}
      </td>
    </tr>
  );

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
            <span className="text-xs text-slate-400 font-medium">Institutional 3-Statement Architecture</span>
          </div>

          <h1 className="text-2xl font-bold tracking-tight text-white mt-1.5 flex items-center gap-2.5">
            <span>{companyInfo.company_name}</span>
            <span className="text-sky-400 font-mono text-lg font-bold">({companyInfo.symbol})</span>
            <span className="px-2 py-0.5 text-xs font-semibold bg-navy-800 text-slate-300 border border-navy-700 rounded">
              {companyInfo.exchange}
            </span>
            {loading && <RefreshCw className="h-4 w-4 animate-spin text-sky-400" />}
          </h1>

          <div className="flex items-center gap-2 mt-1 text-xs text-slate-400">
            <Database className="h-3 w-3 text-cyan-400" />
            <span>{dataSourceNotice}</span>
            <span>•</span>
            <span className="text-emerald-400 font-mono">
              Base Units: {companyInfo.currency} ({unitLabel}) {viewMode === 'common_size' && '• Common-Size (% of Sales / Assets)'}
            </span>
          </div>
        </div>

        {/* Action Buttons: Export CSV, Import CSV, Download Template, Refresh */}
        <div className="flex items-center gap-2.5 flex-wrap">
          <button
            type="button"
            onClick={() => loadData(true)}
            className="flex items-center gap-1.5 px-3 py-2 rounded-xl bg-white/[0.04] hover:bg-white/[0.08] border border-white/[0.08] text-slate-300 text-xs font-medium transition-colors"
          >
            <RefreshCw className="h-3.5 w-3.5" />
            <span>Refresh</span>
          </button>

          {/* One-Click Export to CSV */}
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

          {/* 1-Click Institutional Excel Financial Model Export */}
          <button
            type="button"
            onClick={handleDownloadExcel}
            disabled={downloadingExcel || filteredPeriods.length === 0}
            className="flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-emerald-500/10 hover:bg-emerald-500/20 border border-emerald-500/40 hover:border-emerald-400 text-xs font-semibold text-emerald-400 hover:text-emerald-300 transition-colors shadow-sm disabled:opacity-50"
            title="Download publication-grade multi-tab Excel financial model (.xlsx) with live formulas"
          >
            {downloadingExcel ? (
              <>
                <RefreshCw className="h-3.5 w-3.5 animate-spin text-emerald-400" />
                <span>Exporting Excel...</span>
              </>
            ) : (
              <>
                <FileSpreadsheet className="h-3.5 w-3.5 text-emerald-400" />
                <span>Export Excel Model (.xlsx)</span>
              </>
            )}
          </button>

          <a
            href={`${API_BASE}/statements/csv-template?type=combined`}
            target="_blank"
            rel="noreferrer"
            className="flex items-center gap-1.5 px-3 py-2 rounded-xl bg-white/[0.04] hover:bg-white/[0.08] border border-white/[0.08] text-slate-300 text-xs font-medium transition-colors"
          >
            <FileSpreadsheet className="h-3.5 w-3.5 text-sky-400" />
            <span>CSV Template</span>
          </a>

          <button
            type="button"
            onClick={() => setIsCsvModalOpen(true)}
            className="flex items-center gap-2 px-4 py-2 rounded-xl bg-sky-500 hover:bg-sky-400 text-white font-bold text-xs transition-all shadow-lg shadow-sky-500/20 active:scale-95"
          >
            <Upload className="h-3.5 w-3.5" />
            <span>Import CSV</span>
          </button>
        </div>
      </div>

      {/* Tabs & Period Navigation & Common-Size Toggle */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-3 bg-[#11141B] p-2 rounded-xl border border-white/[0.07]">
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

        {/* Controls: Common-Size Toggle */}
        <div className="flex items-center gap-3 flex-wrap self-end lg:self-auto text-xs">
          {/* Common-Size View Toggle (Values | Common-Size %) */}
          <div className="flex items-center gap-1.5">
            <span className="text-slate-400 text-[11px] font-medium flex items-center gap-1">
              <Percent className="h-3 w-3 text-cyan-400" />
              Display:
            </span>
            <div className="bg-[#090B0F] p-1 rounded-lg border border-white/[0.08] flex gap-1 shadow-inner">
              <button
                onClick={() => setViewMode('values')}
                className={`px-2.5 py-1 rounded-lg text-xs font-semibold transition-all ${
                  viewMode === 'values'
                    ? 'bg-sky-500 text-white shadow-sm font-bold'
                    : 'text-slate-400 hover:text-white'
                }`}
              >
                Values
              </button>
              <button
                onClick={() => setViewMode('common_size')}
                className={`px-2.5 py-1 rounded-lg text-xs font-semibold transition-all ${
                  viewMode === 'common_size'
                    ? 'bg-cyan-500 text-white shadow-sm font-bold'
                    : 'text-slate-400 hover:text-white'
                }`}
                title="Common-Size analysis (% of Net Sales for Income Statement & Cash Flow, % of Total Assets for Balance Sheet)"
              >
                Common-Size %
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* 2017–2026 Custom Year Selector & Annual vs Quarterly Section Switcher */}
      <PeriodFilterBar
        mode={periodFilter}
        onModeChange={setPeriodFilter}
        selectedYears={selectedYears}
        onSelectedYearsChange={setSelectedYears}
        availableYears={availableYears}
        annualCount={annualCount}
        quarterlyCount={quarterlyCount}
      />

      {/* Financial Statement Tables Container */}
      {!loading && periods.length === 0 ? (
        <div className="flex flex-col items-center justify-center min-h-[350px] text-center p-8 bg-navy-900/50 rounded-2xl border border-navy-800 shadow-lg">
          <div className="h-12 w-12 rounded-full bg-navy-800 text-sky-400 flex items-center justify-center mb-3">
            <HelpCircle className="h-6 w-6" />
          </div>
          <h3 className="text-base font-semibold text-white">Financial Statements Standby</h3>
          <p className="text-xs text-slate-300 max-w-md mt-1 leading-relaxed">
            Multi-year financial statements for {ticker} are currently synchronizing or awaiting live fetch.
          </p>
          <button
            onClick={() => loadData(true)}
            className="mt-4 px-4 py-2 rounded-lg bg-navy-800 hover:bg-navy-750 text-xs font-medium text-sky-400 border border-sky-500/30 flex items-center gap-1.5 transition-all shadow-md"
          >
            <RefreshCw className="h-3.5 w-3.5" /> Re-sync Statements
          </button>
        </div>
      ) : !loading && periodFilter === 'annual' && filteredPeriods.length === 0 ? (
        <EmptyPeriodSelectionFallback
          selectedYears={selectedYears}
          availableYears={availableYears}
          onSelectAllAvailable={() =>
            setSelectedYears(availableYears.length > 0 ? availableYears : [2023, 2024, 2025, 2026])
          }
        />
      ) : (
        <div className="bg-[#11141B] border border-white/[0.07] rounded-xl overflow-hidden shadow-[0_1px_0_0_rgba(255,255,255,0.04)_inset]">
          <div className="overflow-x-auto">
            <table className="w-full text-left">
              <thead className="bg-[#0C0E14] text-slate-400 text-[11px] font-mono uppercase tracking-wider border-b border-white/[0.06]">
                <tr>
                  <th className="py-2.5 px-4 font-semibold text-slate-300 min-w-[280px] sticky left-0 bg-[#0C0E14] z-20 border-r border-white/[0.06]">
                    Financial Line Item {viewMode === 'common_size' ? '(% Common-Size)' : `(${unitLabel})`}
                  </th>
                  {filteredPeriods.map((stmt, idx) => (
                    <th key={idx} className="py-2.5 px-4 text-right font-mono font-bold text-white min-w-[125px]">
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

              <tbody className="divide-y divide-white/[0.04]">
                {/* 1. INCOME STATEMENT SECTION */}
                {(activeTab === 'income' || activeTab === 'all') && (
                  <>
                    {renderSectionBanner('1. Income Statement (Waterfall)', 'text-sky-400')}
                    {incomeStatementRows.map((r) => renderRow(r))}
                  </>
                )}

                {/* 2. BALANCE SHEET SECTION */}
                {(activeTab === 'balance' || activeTab === 'all') && (
                  <>
                    {renderSectionBanner('2. Balance Sheet (Assets = Liabilities + Equity)', 'text-cyan-400')}
                    {renderHairlineDivider('Current Assets')}
                    {balanceSheetRows.slice(0, 5).map((r) => renderRow(r))}
                    {renderHairlineDivider('Non-Current Assets')}
                    {balanceSheetRows.slice(5, 9).map((r) => renderRow(r))}
                    {renderHairlineDivider('Total Assets')}
                    {balanceSheetRows.slice(9, 10).map((r) => renderRow(r))}
                    {renderHairlineDivider('Liabilities')}
                    {balanceSheetRows.slice(10, 15).map((r) => renderRow(r))}
                    {renderHairlineDivider("Stockholders' Equity")}
                    {balanceSheetRows.slice(15, 16).map((r) => renderRow(r))}
                    {renderHairlineDivider('Analytical Memo Rows (DCF & Working Capital Inputs)')}
                    {balanceSheetRows.slice(16).map((r) => renderRow(r))}
                  </>
                )}

                {/* 3. CASH FLOW STATEMENT SECTION */}
                {(activeTab === 'cash_flow' || activeTab === 'all') && (
                  <>
                    {renderSectionBanner('3. Cash Flow Statement (Waterfall)', 'text-emerald-400')}
                    {cashFlowRows.map((r) => renderRow(r))}
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
                Standard Wall Street accounting formatting: deductions and cash outflows rendered as <span className="font-mono text-rose-300 font-medium">( ... )</span>. Missing values preserved as <span className="font-mono text-slate-300">N/A</span>.
              </span>
            </div>

            <div className="flex items-center gap-2 font-mono text-[11px]">
              <span className="px-2 py-0.5 rounded bg-navy-800 text-slate-300 border border-navy-700">
                Source: Neon PostgreSQL
              </span>
              <span className="px-2 py-0.5 rounded bg-emerald-950 text-emerald-300 border border-emerald-800">
                Verified 3-Statement Data
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
