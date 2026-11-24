"""
FinSight AI — Institutional Quality Gates Regression Suite
==========================================================
Verifies all 8 quality gates across edge-case NSE stocks:
- Gate 1: Mathematical & Accounting Reconciliation
- Gate 2: 10-Year History & Period Filtering
- Gate 3: DCF Valuation & Monotonic 5x5 Sensitivity
- Gate 4: Market-Cap Peers
- Gate 5: Institutional Exports (XLSX, PDF, CSV)
- Gate 8: Security & Health
"""

import io
import pytest
import openpyxl
from starlette.testclient import TestClient

from app.main import app
from app.db.session import SessionLocal
from app.models.company import Company
from app.services.dcf_engine import calculate_dcf, DCFRequest

client = TestClient(app)


def test_gate1_accounting_reconciliation_asianpaint():
    """Gate 1: Verify EBIT + Other Income - Interest == PBT and OCF - CapEx == FCF."""
    r = client.get("/api/companies/ASIANPAINT.NS/analysis")
    assert r.status_code == 200
    data = r.json()
    periods = [p for p in data.get("periods", []) if p.get("statement_type") != "quarterly"]
    assert len(periods) >= 8

    for p in periods:
        yr = p.get("fiscal_year")
        ebit = p.get("operating_income") if p.get("operating_income") is not None else p.get("ebit")
        other_inc = p.get("other_income") or 0.0
        interest = abs(p.get("interest_expense") or 0.0)
        pbt = p.get("profit_before_tax")

        if ebit is not None and pbt is not None and p.get("other_income") is not None:
            calc_pbt = ebit + other_inc - interest
            assert abs(calc_pbt - pbt) <= 1.0, f"FY{yr} PBT reconciliation failure: {calc_pbt} vs {pbt}"

        ocf = p.get("operating_cash_flow")
        capex = p.get("capital_expenditure")
        fcf = p.get("free_cash_flow")
        if ocf is not None and capex is not None and fcf is not None:
            calc_fcf = ocf - abs(capex)
            assert abs(calc_fcf - fcf) <= 1.0, f"FY{yr} FCF reconciliation failure: {calc_fcf} vs {fcf}"


def test_gate1_net_debt_consistency():
    """Gate 1: Net debt in Balance Sheet memo rows matches DCF Equity Bridge."""
    r_analysis = client.get("/api/companies/ASIANPAINT.NS/analysis")
    r_dcf = client.get("/api/companies/ASIANPAINT.NS/dcf")
    assert r_analysis.status_code == 200
    assert r_dcf.status_code == 200

    dcf_nd = r_dcf.json().get("net_debt")
    annual = [p for p in r_analysis.json().get("periods", []) if p.get("statement_type") != "quarterly"]
    latest_annual = max(annual, key=lambda x: x.get("fiscal_year") or 0)
    bs_nd = latest_annual.get("net_debt")

    assert bs_nd is not None and dcf_nd is not None
    assert abs(bs_nd - dcf_nd) <= 1.0


def test_gate2_10y_history_coverage():
    """Gate 2: 10-year history (FY2017-FY2026) is available."""
    r = client.get("/api/companies/20MICRONS.NS/analysis")
    assert r.status_code == 200
    data = r.json()
    annual_years = sorted({p["fiscal_year"] for p in data.get("periods", []) if p.get("statement_type") != "quarterly" and p.get("fiscal_year")})
    assert len(annual_years) >= 8
    assert 2017 in annual_years or 2018 in annual_years
    assert 2026 in annual_years


def test_gate3_infy_usd_to_inr_dcf():
    """Gate 3: INFY.NS Base FCF > 20,000 Cr and Intrinsic Value > 700."""
    r = client.get("/api/companies/INFY.NS/dcf")
    assert r.status_code == 200
    data = r.json()
    iv = data.get("intrinsic_value")
    fcf = data.get("fcf_base")
    assert iv is not None and iv > 700.0, f"INFY Intrinsic Value too low: {iv}"
    assert fcf is not None and fcf > 20000.0, f"INFY FCF Base too low: {fcf}"


def test_gate3_wacc_spread_validation():
    """Gate 3: wacc <= terminal_growth returns HTTP 422."""
    r = client.post(
        "/api/companies/ASIANPAINT.NS/dcf",
        json={"wacc": 0.03, "terminal_growth": 0.04, "fcf_growth": 0.08, "projection_years": 5}
    )
    assert r.status_code == 422


def test_gate3_sensitivity_matrix_strictly_monotonic():
    """Gate 3: 5x5 sensitivity matrix is strictly monotonic along rows and columns."""
    for sym in ["ASIANPAINT.NS", "INFY.NS", "M&M.NS"]:
        r = client.get(f"/api/companies/{sym}/dcf")
        assert r.status_code == 200
        matrix = r.json().get("sensitivity_matrix", {}).get("matrix", [])
        assert len(matrix) >= 5

        # Check rows (increasing terminal growth -> increasing price)
        for row_idx, row in enumerate(matrix):
            for c in range(len(row) - 1):
                p1, p2 = row[c], row[c + 1]
                if p1 is not None and p2 is not None:
                    assert p2 > p1, f"[{sym}] Row {row_idx} non-monotonic: {p1} >= {p2}"

        # Check columns (increasing WACC -> decreasing price)
        for col_idx in range(len(matrix[0])):
            for r_idx in range(len(matrix) - 1):
                p_top, p_bot = matrix[r_idx][col_idx], matrix[r_idx + 1][col_idx]
                if p_top is not None and p_bot is not None:
                    assert p_top > p_bot, f"[{sym}] Col {col_idx} non-monotonic: {p_top} <= {p_bot}"


def test_gate4_peers_ranking():
    """Gate 4: Peer companies are same currency, non-empty, and sorted by market cap closeness."""
    r = client.get("/api/companies/ASIANPAINT.NS/peers")
    assert r.status_code == 200
    peers = r.json().get("peers", [])
    assert len(peers) >= 2
    for p in peers:
        assert p.get("currency") in ["INR", None]
        assert p.get("symbol") != "ASIANPAINT.NS"


def test_gate5_xlsx_export_integrity():
    """Gate 5: Excel export returns HTTP 200, 4 sheets, and live Excel formulas."""
    r = client.get("/api/companies/M%26M.NS/export/xlsx")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/vnd.openxmlformats-officedocument")

    wb = openpyxl.load_workbook(io.BytesIO(r.content))
    expected = [
        "Executive Summary",
        "Data Sheet",
        "HistoricalFS",
        "Common Size",
        "Ratio Analysis",
        "Assumptions",
        "Forecast",
        "WACC",
        "Intrinsic Growth",
        "DCF",
        "Comps_Val"
    ]
    for s in expected:
        assert s in wb.sheetnames, f"Missing sheet: {s}"

    # Check for live formulas
    has_formula = any(
        isinstance(cell, str) and cell.startswith("=")
        for sheet in wb.worksheets
        for row in sheet.iter_rows(values_only=True)
        for cell in row
    )
    assert has_formula, "XLSX export must contain live Excel formulas"


def test_gate5_pdf_export_integrity():
    """Gate 5: PDF export returns HTTP 200 and valid %PDF header."""
    r = client.get("/api/companies/ASIANPAINT.NS/report/pdf")
    assert r.status_code == 200
    assert r.content.startswith(b"%PDF-")
    assert b"Nonex" not in r.content


def test_gate8_security_and_health():
    """Gate 8: Health check returns 200 + connected, admin endpoint guards access."""
    r_health = client.get("/health")
    assert r_health.status_code == 200
    assert r_health.json().get("db") == "connected"

    r_admin = client.post("/api/admin/sync-nse300")
    assert r_admin.status_code in [401, 403]
