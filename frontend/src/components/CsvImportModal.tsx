'use client';

import React, { useState, useRef } from 'react';
import { 
  X, 
  UploadCloud, 
  FileSpreadsheet, 
  Download, 
  CheckCircle2, 
  AlertTriangle, 
  AlertCircle, 
  RefreshCw, 
  ArrowRight,
  Database,
  Layers,
  HelpCircle
} from 'lucide-react';
import { API_BASE } from '@/lib/api';

export interface CsvPreviewRow {
  row_number: number;
  is_valid: boolean;
  errors: string[];
  is_duplicate: boolean;
  data: {
    fiscal_year?: number;
    fiscal_period?: string;
    statement_type?: string;
    revenue?: number | null;
    gross_profit?: number | null;
    operating_income?: number | null;
    net_income?: number | null;
    total_assets?: number | null;
    current_assets?: number | null;
    total_liabilities?: number | null;
    current_liabilities?: number | null;
    total_equity?: number | null;
    cash_and_equivalents?: number | null;
    total_debt?: number | null;
    operating_cash_flow?: number | null;
    capital_expenditure?: number | null;
    free_cash_flow?: number | null;
    source?: string;
    [key: string]: any;
  };
}

export interface CsvPreviewResponse {
  success: boolean;
  company_id: number;
  total_rows: number;
  valid_rows_count: number;
  duplicate_rows_count: number;
  error_rows_count: number;
  preview_rows: CsvPreviewRow[];
  detected_columns: string[];
  missing_required_columns: string[];
}

interface CsvImportModalProps {
  isOpen: boolean;
  onClose: () => void;
  companyId: number;
  companyTicker: string;
  companyName: string;
  onImportSuccess?: () => void;
}

export const CsvImportModal: React.FC<CsvImportModalProps> = ({
  isOpen,
  onClose,
  companyId,
  companyTicker,
  companyName,
  onImportSuccess,
}) => {
  const [statementType, setStatementType] = useState<string>('annual_combined');
  const [file, setFile] = useState<File | null>(null);
  const [rawCsvText, setRawCsvText] = useState<string>('');
  const [showRawInput, setShowRawInput] = useState<boolean>(false);
  const [isDragging, setIsDragging] = useState<boolean>(false);
  const [loadingPreview, setLoadingPreview] = useState<boolean>(false);
  const [importing, setImporting] = useState<boolean>(false);
  const [previewData, setPreviewData] = useState<CsvPreviewResponse | null>(null);
  const [overwriteDuplicates, setOverwriteDuplicates] = useState<boolean>(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [importResult, setImportResult] = useState<{
    success: boolean;
    statements_inserted: number;
    statements_updated: number;
    calculated_ratios: number;
    message: string;
  } | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);

  if (!isOpen) return null;

  // 1. Download CSV Template
  const handleDownloadTemplate = () => {
    const templateTypeMap: Record<string, string> = {
      annual_combined: 'combined',
      income_statement: 'income_statement',
      balance_sheet: 'balance_sheet',
      cash_flow: 'cash_flow',
    };
    const queryType = templateTypeMap[statementType] || 'combined';
    window.open(`${API_BASE}/statements/csv-template?type=${queryType}`, '_blank');
  };

  // 2. Process CSV File / Text for Preview
  const handleParsePreview = async (csvPayload: { file?: File; text?: string }) => {
    setLoadingPreview(true);
    setErrorMessage(null);
    setImportResult(null);

    try {
      let response: Response;

      if (csvPayload.file) {
        const formData = new FormData();
        formData.append('file', csvPayload.file);
        response = await fetch(
          `${API_BASE}/companies/${companyId}/statements/csv-preview?default_statement_type=${statementType}`,
          {
            method: 'POST',
            body: formData,
          }
        );
      } else if (csvPayload.text) {
        response = await fetch(
          `${API_BASE}/companies/${companyId}/statements/csv-preview?default_statement_type=${statementType}`,
          {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              csv_text: csvPayload.text,
              default_statement_type: statementType,
            }),
          }
        );
      } else {
        throw new Error('Please select a file or enter CSV data.');
      }

      if (!response.ok) {
        const errJson = await response.json().catch(() => ({}));
        throw new Error(errJson.detail || `Server returned error status ${response.status}`);
      }

      const data: CsvPreviewResponse = await response.json();
      setPreviewData(data);
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to parse CSV.');
      setPreviewData(null);
    } finally {
      setLoadingPreview(false);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      const selected = e.target.files[0];
      setFile(selected);
      handleParsePreview({ file: selected });
    }
  };

  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      const selected = e.dataTransfer.files[0];
      setFile(selected);
      handleParsePreview({ file: selected });
    }
  };

  const handleDragOver = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = () => {
    setIsDragging(false);
  };

  // 3. Confirm & Execute CSV Import into Neon DB
  const handleConfirmImport = async () => {
    if (!previewData || previewData.valid_rows_count === 0) return;

    setImporting(true);
    setErrorMessage(null);

    try {
      const response = await fetch(
        `${API_BASE}/companies/${companyId}/statements/csv-import`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            preview_rows: previewData.preview_rows,
            overwrite_duplicates: overwriteDuplicates,
          }),
        }
      );

      if (!response.ok) {
        const errJson = await response.json().catch(() => ({}));
        throw new Error(errJson.detail || `Import failed with status ${response.status}`);
      }

      const resData = await response.json();
      setImportResult({
        success: true,
        statements_inserted: resData.statements_inserted || 0,
        statements_updated: resData.statements_updated || 0,
        calculated_ratios: resData.calculated_ratios || 0,
        message: resData.message || 'Statements imported successfully.',
      });

      if (onImportSuccess) {
        onImportSuccess();
      }
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to complete database import.');
    } finally {
      setImporting(false);
    }
  };

  const resetAll = () => {
    setFile(null);
    setRawCsvText('');
    setPreviewData(null);
    setErrorMessage(null);
    setImportResult(null);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6 overflow-y-auto">
      {/* Backdrop */}
      <div 
        className="fixed inset-0 bg-black/80 backdrop-blur-sm transition-opacity" 
        onClick={onClose} 
      />

      {/* Modal Dialog */}
      <div className="relative w-full max-w-4xl bg-navy-900 border border-navy-700 rounded-2xl shadow-2xl z-10 flex flex-col max-h-[90vh] overflow-hidden">
        {/* Header */}
        <div className="px-6 py-4 border-b border-navy-800 flex items-center justify-between bg-navy-950/60">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-xl bg-gold-500/10 border border-gold-500/30 flex items-center justify-center text-gold-400">
              <FileSpreadsheet className="h-5 w-5" />
            </div>
            <div>
              <h2 className="text-lg font-bold text-white flex items-center gap-2">
                <span>Import Financial Statements (CSV)</span>
                <span className="text-xs px-2 py-0.5 rounded-full bg-cyan-950 text-cyan-400 border border-cyan-800 font-mono">
                  {companyTicker}
                </span>
              </h2>
              <p className="text-xs text-slate-400">
                Target: <span className="text-slate-200 font-medium">{companyName}</span> • Neon Database Storage with Pure Python Ratio Calculation
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="h-8 w-8 rounded-lg bg-navy-800 hover:bg-navy-700 text-slate-400 hover:text-white flex items-center justify-center transition-colors"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Modal Body */}
        <div className="p-6 overflow-y-auto space-y-6 flex-1">
          {/* Step 1: Controls & Template Download */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 bg-navy-950/50 p-4 rounded-xl border border-navy-800">
            <div>
              <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1.5">
                Statement Structure
              </label>
              <select
                value={statementType}
                onChange={(e) => setStatementType(e.target.value)}
                className="w-full bg-navy-900 border border-navy-700 rounded-lg px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-gold-500"
              >
                <option value="annual_combined">Annual Combined (Income + Balance Sheet + Cash Flow)</option>
                <option value="income_statement">Income Statement Only (Revenue, COGS, Net Income)</option>
                <option value="balance_sheet">Balance Sheet Only (Assets, Liabilities, Equity)</option>
                <option value="cash_flow">Cash Flow Statement Only (OCF, CapEx, FCF)</option>
              </select>
            </div>

            <div className="flex flex-col justify-end">
              <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1.5">
                Official CSV Templates
              </label>
              <button
                type="button"
                onClick={handleDownloadTemplate}
                className="w-full flex items-center justify-center gap-2 px-3 py-2 rounded-lg bg-navy-800 hover:bg-navy-700 border border-navy-700 hover:border-gold-500/40 text-xs font-medium text-gold-400 transition-colors"
              >
                <Download className="h-3.5 w-3.5" />
                <span>Download Sample CSV Template</span>
              </button>
            </div>
          </div>

          {/* Error Message Banner */}
          {errorMessage && (
            <div className="p-3.5 rounded-xl bg-rose-950/40 border border-rose-500/30 flex items-start gap-3 text-xs text-rose-300">
              <AlertTriangle className="h-4 w-4 text-rose-400 flex-shrink-0 mt-0.5" />
              <div>
                <span className="font-semibold">Validation Error:</span> {errorMessage}
              </div>
            </div>
          )}

          {/* Success Banner */}
          {importResult && (
            <div className="p-4 rounded-xl bg-emerald-950/50 border border-emerald-500/40 flex items-start gap-3.5 text-xs text-emerald-200">
              <CheckCircle2 className="h-5 w-5 text-emerald-400 flex-shrink-0 mt-0.5" />
              <div className="space-y-1">
                <div className="font-bold text-sm text-emerald-300">Import & Ratio Calculation Completed!</div>
                <div>{importResult.message}</div>
                <div className="flex items-center gap-3 font-mono text-[11px] text-emerald-400/90 pt-1">
                  <span>Inserted: {importResult.statements_inserted}</span>
                  <span>•</span>
                  <span>Updated: {importResult.statements_updated}</span>
                  <span>•</span>
                  <span>Ratios Calculated: {importResult.calculated_ratios}</span>
                </div>
              </div>
            </div>
          )}

          {/* Drag & Drop Upload Zone */}
          {!importResult && (
            <div>
              <div
                onDrop={handleDrop}
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
                onClick={() => fileInputRef.current?.click()}
                className={`border-2 border-dashed rounded-xl p-6 text-center cursor-pointer transition-all ${
                  isDragging
                    ? 'border-gold-500 bg-gold-500/5'
                    : 'border-navy-700 hover:border-navy-600 bg-navy-950/30'
                }`}
              >
                <input
                  type="file"
                  ref={fileInputRef}
                  onChange={handleFileChange}
                  accept=".csv"
                  className="hidden"
                />
                <div className="flex flex-col items-center justify-center gap-2">
                  <div className="h-12 w-12 rounded-full bg-navy-800 border border-navy-700 flex items-center justify-center text-slate-300 group-hover:text-gold-400">
                    <UploadCloud className="h-6 w-6 text-gold-400" />
                  </div>
                  <div className="text-sm font-semibold text-white">
                    {file ? file.name : 'Click to browse or drag and drop your CSV file here'}
                  </div>
                  <p className="text-xs text-slate-400">
                    Supports standard format with columns: <code className="text-gold-400/90 font-mono">fiscal_year, fiscal_period, revenue...</code>
                  </p>
                </div>
              </div>

              {/* Paste Raw CSV Alternative */}
              <div className="mt-3 text-right">
                <button
                  type="button"
                  onClick={() => setShowRawInput(!showRawInput)}
                  className="text-xs text-slate-400 hover:text-gold-400 underline underline-offset-4"
                >
                  {showRawInput ? 'Hide direct text input' : 'Or paste CSV data as text'}
                </button>
              </div>

              {showRawInput && (
                <div className="mt-2 space-y-2">
                  <textarea
                    rows={4}
                    value={rawCsvText}
                    onChange={(e) => setRawCsvText(e.target.value)}
                    placeholder="fiscal_year,fiscal_period,statement_type,revenue,cost_of_revenue,gross_profit..."
                    className="w-full bg-navy-950 border border-navy-700 rounded-lg p-3 text-xs font-mono text-slate-200 focus:outline-none focus:border-gold-500"
                  />
                  <div className="flex justify-end">
                    <button
                      type="button"
                      disabled={!rawCsvText.trim() || loadingPreview}
                      onClick={() => handleParsePreview({ text: rawCsvText })}
                      className="px-3 py-1.5 bg-navy-800 hover:bg-navy-700 border border-navy-600 text-xs text-white rounded-lg disabled:opacity-50"
                    >
                      Parse & Preview Text
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Loading Indicator */}
          {loadingPreview && (
            <div className="py-8 flex flex-col items-center justify-center gap-2 text-slate-400">
              <RefreshCw className="h-6 w-6 animate-spin text-gold-400" />
              <span className="text-xs">Parsing CSV and checking database duplicates...</span>
            </div>
          )}

          {/* Step 2: Preview & Validation Table */}
          {previewData && !importResult && (
            <div className="space-y-4">
              {/* Summary Stats */}
              <div className="flex flex-wrap items-center justify-between gap-3 p-3.5 bg-navy-950/60 rounded-xl border border-navy-800 text-xs">
                <div className="flex items-center gap-4">
                  <span className="text-slate-400">
                    Total Rows: <strong className="text-white font-mono">{previewData.total_rows}</strong>
                  </span>
                  <span className="text-emerald-400 flex items-center gap-1 font-medium">
                    <CheckCircle2 className="h-3.5 w-3.5" />
                    Valid: <span className="font-mono">{previewData.valid_rows_count}</span>
                  </span>
                  {previewData.duplicate_rows_count > 0 && (
                    <span className="text-amber-400 flex items-center gap-1 font-medium">
                      <AlertCircle className="h-3.5 w-3.5" />
                      Existing Duplicates: <span className="font-mono">{previewData.duplicate_rows_count}</span>
                    </span>
                  )}
                  {previewData.error_rows_count > 0 && (
                    <span className="text-rose-400 flex items-center gap-1 font-medium">
                      <AlertTriangle className="h-3.5 w-3.5" />
                      Validation Errors: <span className="font-mono">{previewData.error_rows_count}</span>
                    </span>
                  )}
                </div>

                {/* Overwrite Checkbox */}
                <label className="flex items-center gap-2 cursor-pointer text-slate-300">
                  <input
                    type="checkbox"
                    checked={overwriteDuplicates}
                    onChange={(e) => setOverwriteDuplicates(e.target.checked)}
                    className="rounded border-navy-700 bg-navy-900 text-gold-500 focus:ring-0"
                  />
                  <span>Overwrite existing periods</span>
                </label>
              </div>

              {/* Data Preview Table */}
              <div className="border border-navy-800 rounded-xl overflow-hidden bg-navy-950/40">
                <div className="overflow-x-auto max-h-60">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-navy-950 text-slate-400 uppercase text-[10px] tracking-wider sticky top-0 border-b border-navy-800">
                      <tr>
                        <th className="py-2.5 px-3">Row</th>
                        <th className="py-2.5 px-3">Period</th>
                        <th className="py-2.5 px-3">Type</th>
                        <th className="py-2.5 px-3 text-right">Revenue</th>
                        <th className="py-2.5 px-3 text-right">Gross Profit</th>
                        <th className="py-2.5 px-3 text-right">Net Income</th>
                        <th className="py-2.5 px-3 text-right">Total Assets</th>
                        <th className="py-2.5 px-3">Status</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-navy-800/60 font-mono text-[11px]">
                      {previewData.preview_rows.map((row) => (
                        <tr 
                          key={row.row_number} 
                          className={`hover:bg-navy-800/30 ${!row.is_valid ? 'bg-rose-950/20' : ''}`}
                        >
                          <td className="py-2 px-3 text-slate-400">#{row.row_number}</td>
                          <td className="py-2 px-3 font-semibold text-white">
                            {row.data.fiscal_year || '—'} {row.data.fiscal_period || ''}
                          </td>
                          <td className="py-2 px-3 text-slate-300 text-[10px] uppercase">
                            {row.data.statement_type || statementType}
                          </td>
                          <td className="py-2 px-3 text-right text-slate-200">
                            {row.data.revenue != null ? `$${row.data.revenue.toLocaleString()}` : <span className="text-slate-500">N/A</span>}
                          </td>
                          <td className="py-2 px-3 text-right text-slate-200">
                            {row.data.gross_profit != null ? `$${row.data.gross_profit.toLocaleString()}` : <span className="text-slate-500">N/A</span>}
                          </td>
                          <td className="py-2 px-3 text-right text-slate-200">
                            {row.data.net_income != null ? `$${row.data.net_income.toLocaleString()}` : <span className="text-slate-500">N/A</span>}
                          </td>
                          <td className="py-2 px-3 text-right text-slate-200">
                            {row.data.total_assets != null ? `$${row.data.total_assets.toLocaleString()}` : <span className="text-slate-500">N/A</span>}
                          </td>
                          <td className="py-2 px-3">
                            {!row.is_valid ? (
                              <span className="px-2 py-0.5 rounded text-[10px] bg-rose-950 text-rose-300 border border-rose-800" title={row.errors.join(', ')}>
                                Error
                              </span>
                            ) : row.is_duplicate ? (
                              <span className="px-2 py-0.5 rounded text-[10px] bg-amber-950 text-amber-300 border border-amber-800">
                                Duplicate (Update)
                              </span>
                            ) : (
                              <span className="px-2 py-0.5 rounded text-[10px] bg-emerald-950 text-emerald-300 border border-emerald-800">
                                New Record
                              </span>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-navy-800 bg-navy-950/80 flex items-center justify-between">
          <div className="text-xs text-slate-500 flex items-center gap-1.5">
            <Database className="h-3.5 w-3.5 text-cyan-400" />
            <span>Target: Neon PostgreSQL (<span className="text-slate-400 font-mono">financial_statements</span> table)</span>
          </div>

          <div className="flex items-center gap-3">
            {importResult ? (
              <button
                type="button"
                onClick={onClose}
                className="px-4 py-2 rounded-xl bg-gold-500 hover:bg-gold-400 text-navy-950 font-bold text-xs transition-colors"
              >
                Done
              </button>
            ) : (
              <>
                <button
                  type="button"
                  onClick={onClose}
                  className="px-4 py-2 rounded-xl bg-navy-800 hover:bg-navy-700 text-slate-300 text-xs font-semibold transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  disabled={!previewData || previewData.valid_rows_count === 0 || importing}
                  onClick={handleConfirmImport}
                  className="flex items-center gap-2 px-4 py-2 rounded-xl bg-gold-500 hover:bg-gold-400 disabled:bg-navy-800 disabled:text-slate-600 text-navy-950 font-bold text-xs transition-all shadow-md shadow-gold-500/10"
                >
                  {importing ? (
                    <>
                      <RefreshCw className="h-3.5 w-3.5 animate-spin" />
                      <span>Writing to Neon DB...</span>
                    </>
                  ) : (
                    <>
                      <span>Confirm & Import ({previewData?.valid_rows_count || 0} Records)</span>
                      <ArrowRight className="h-3.5 w-3.5" />
                    </>
                  )}
                </button>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
