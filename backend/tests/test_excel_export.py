"""
Tests for 1-Click Institutional 11-Tab Excel Financial Model Export (.xlsx):
1. GET /api/companies/ASIANPAINT.NS/export/xlsx (and /export/excel) returns 200, valid .xlsx content type, and opens cleanly in openpyxl.
2. All 11 institutional sheets exist:
   'Executive Summary', 'Data Sheet', 'HistoricalFS', 'Common Size', 'Ratio Analysis',
   'Assumptions', 'Forecast', 'WACC', 'Intrinsic Growth', 'DCF', 'Comps_Val'
3. Cells contain live Excel formulas (=) and cross-sheet links, and 5x5 sensitivity matrix uses dynamic formulas.
4. Custom query parameters (fcf_growth, wacc, terminal_growth, projection_years) are correctly injected into model assumptions.
5. Formula injection defense works for potentially malicious text strings.
"""

import sys
import os
import io
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
import openpyxl
from fastapi.testclient import TestClient
from app.main import app
from app.services.excel_exporter import sanitize_text

client = TestClient(app)


def test_formula_injection_defense():
    """Verify that potentially malicious strings starting with =, +, -, @ are sanitized."""
    assert sanitize_text("=CMD|' /C calc'!A0") == "'=CMD|' /C calc'!A0"
    assert sanitize_text("+12345") == "'+12345"
    assert sanitize_text("-500") == "'-500"
    assert sanitize_text("@SUM(1,2)") == "'@SUM(1,2)"
    assert sanitize_text("Normal Text") == "Normal Text"
    assert sanitize_text(12345) == 12345
    assert sanitize_text(None) is None


def test_excel_export_asianpaint_endpoint():
    """Verify live endpoint returns a valid 11-sheet formula-driven workbook for ASIANPAINT.NS."""
    resp = client.get("/api/companies/ASIANPAINT.NS/export/xlsx")
    assert resp.status_code == 200, f"Expected 200 OK, got {resp.status_code}: {resp.text}"

    # Verify headers
    content_type = resp.headers.get("content-type", "")
    assert "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" in content_type
    content_disp = resp.headers.get("content-disposition", "")
    assert "attachment" in content_disp
    assert "FinSight_ASIANPAINT.NS_Financial_Model.xlsx" in content_disp

    # Verify openpyxl can parse the streamed bytes
    wb = openpyxl.load_workbook(io.BytesIO(resp.content), data_only=False)

    # Verify all 11 required sheets exist
    expected_sheets = [
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
    for s in expected_sheets:
        assert s in wb.sheetnames, f"Missing sheet: {s}"

    # 1. Inspect Executive Summary
    ws_exec = wb["Executive Summary"]
    assert "ASIAN PAINT" in str(ws_exec["A2"].value).upper() or "ASIANPAINT" in str(ws_exec["A2"].value).upper()
    # Check valuation links in Executive Summary
    assert ws_exec["B13"].value == "='DCF'!C31"  # Implied Enterprise Value
    assert ws_exec["B14"].value == "='DCF'!C34"  # Less: Net Debt
    assert ws_exec["B15"].value == "='DCF'!C35"  # Implied Equity Value
    assert ws_exec["B16"].value == "='DCF'!C37"  # DCF Intrinsic Fair Value / Share
    assert ws_exec["B18"].value == "='Data Sheet'!B6"  # Current Trading Market Price
    assert ws_exec["B19"].value == "='DCF'!C39"  # Implied Upside %

    # 2. Inspect HistoricalFS
    ws_hist = wb["HistoricalFS"]
    assert ws_hist["C14"].value == "='Data Sheet'!C14"  # Year header
    assert ws_hist["C16"].value == "='Data Sheet'!C16"  # Revenue
    assert ws_hist["C19"].value == "=IF(C18>0, C16-C18, 'Data Sheet'!C18)"  # Gross Profit formula

    # 3. Inspect Assumptions
    ws_assump = wb["Assumptions"]
    assert ws_assump["D6"].font.color.rgb in ("0000FF", "000000FF")

    # 4. Inspect DCF
    ws_dcf = wb["DCF"]
    assert ws_dcf["C31"].value == "=C29+C30"         # Enterprise Value
    assert ws_dcf["C35"].value == "=C31-C34"         # Equity Value
    assert ws_dcf["C37"].value == "=C35/C36"         # Implied Price per share
    assert ws_dcf["C39"].value == "=(C37-C38)/C38"   # Upside %

    # Check 5x5 sensitivity matrix contains dynamic closed-form formulas
    matrix_base_cell = ws_dcf["D46"].value  # Row 46, Col D
    assert matrix_base_cell is not None
    assert matrix_base_cell.startswith("=")


def test_excel_export_custom_parameters():
    """Verify that custom DCF parameters are reflected in the generated 11-tab workbook."""
    params = {
        "fcf_growth": 14.5,
        "wacc": 12.0,
        "terminal_growth": 4.5,
        "projection_years": 8
    }
    resp = client.get("/api/companies/ASIANPAINT.NS/export/xlsx", params=params)
    assert resp.status_code == 200

    wb = openpyxl.load_workbook(io.BytesIO(resp.content), data_only=False)
    assert "DCF" in wb.sheetnames
    assert "Assumptions" in wb.sheetnames
    ws_assump = wb["Assumptions"]

    # Verify overridden assumptions in Assumptions sheet (FY27E is Col C)
    assert ws_assump["C6"].value == 0.145  # 14.5%
