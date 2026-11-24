import { API_BASE } from './api';

export interface ExcelExportOptions {
  fcf_growth?: number;
  wacc?: number;
  terminal_growth?: number;
  projection_years?: number;
}

/**
 * Downloads a publication-grade institutional Excel (.xlsx) financial model.
 * Streams directly from GET /api/companies/{symbol}/export/xlsx.
 */
export async function exportCompanyExcelModel(
  symbol: string,
  options?: ExcelExportOptions
): Promise<void> {
  const cleanSym = symbol.trim().toUpperCase();
  const queryParams = new URLSearchParams();

  if (options?.fcf_growth !== undefined && options?.fcf_growth !== null) {
    queryParams.set('fcf_growth', String(options.fcf_growth));
  }
  if (options?.wacc !== undefined && options?.wacc !== null) {
    queryParams.set('wacc', String(options.wacc));
  }
  if (options?.terminal_growth !== undefined && options?.terminal_growth !== null) {
    queryParams.set('terminal_growth', String(options.terminal_growth));
  }
  if (options?.projection_years !== undefined && options?.projection_years !== null) {
    queryParams.set('projection_years', String(options.projection_years));
  }

  const qs = queryParams.toString();
  const url = `${API_BASE}/companies/${encodeURIComponent(cleanSym)}/export/xlsx${qs ? `?${qs}` : ''}`;

  const res = await fetch(url);
  if (!res.ok) {
    const errorText = await res.text().catch(() => '');
    throw new Error(`Excel export failed (HTTP ${res.status}): ${errorText || 'Server Error'}`);
  }

  const blob = await res.blob();
  const downloadUrl = window.URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = downloadUrl;
  a.download = `FinSight_${cleanSym}_Financial_Model.xlsx`;
  document.body.appendChild(a);
  a.click();
  window.URL.revokeObjectURL(downloadUrl);
  document.body.removeChild(a);
}

/**
 * Downloads a raw 10-year + quarterly financial dataset CSV.
 * Streams directly from GET /api/companies/{symbol}/export/csv.
 */
export async function exportCompanyDatasetCsv(symbol: string): Promise<void> {
  const cleanSym = symbol.trim().toUpperCase();
  const url = `${API_BASE}/companies/${encodeURIComponent(cleanSym)}/export/csv`;

  const res = await fetch(url);
  if (!res.ok) {
    const errorText = await res.text().catch(() => '');
    throw new Error(`CSV export failed (HTTP ${res.status}): ${errorText || 'Server Error'}`);
  }

  const blob = await res.blob();
  const downloadUrl = window.URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = downloadUrl;
  a.download = `FinSight_${cleanSym}_10Y_Dataset.csv`;
  document.body.appendChild(a);
  a.click();
  window.URL.revokeObjectURL(downloadUrl);
  document.body.removeChild(a);
}
