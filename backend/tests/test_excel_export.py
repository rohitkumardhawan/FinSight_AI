"""
Tests for 1-Click Institutional Excel Financial Model Export (.xlsx):
1. GET /api/companies/ASIANPAINT.NS/export/xlsx returns 200, valid .xlsx content type, and opens cleanly in openpyxl.
2. All 4 sheets ('Executive Summary', '3-Statement Financials', 'Ratios & Peers', 'DCF Valuation') exist.
3. Cells contain live Excel formulas (=) and cross-sheet links, and 5x5 sensitivity matrix uses dynamic NPV formulas.
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
    """Verify live endpoint returns a valid 4-sheet formula-driven workbook for ASIANPAINT.NS."""
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

    # Verify all 4 required sheets exist
    expected_sheets = ["Executive Summary", "3-Statement Financials", "Ratios & Peers", "DCF Valuation"]
    for s in expected_sheets:
        assert s in wb.sheetnames, f"Missing sheet: {s}"

    # 1. Inspect Executive Summary
    ws_exec = wb["Executive Summary"]
    assert "₹ Crores" in str(ws_exec["A2"].value)
    # Check valuation links to DCF Valuation
    assert ws_exec["B17"].value == "='DCF Valuation'!B26"  # EV
    assert ws_exec["B18"].value == "='DCF Valuation'!B27"  # Net Debt
    assert ws_exec["B19"].value == "='DCF Valuation'!B28"  # Equity Value
    assert ws_exec["B20"].value == "='DCF Valuation'!B30"  # Intrinsic Value
    assert ws_exec["B22"].value == "='DCF Valuation'!B32"  # Upside %

    # 2. Inspect 3-Statement Financials
    ws_fin = wb["3-Statement Financials"]
    assert ws_fin["B8"].value == "=B6-B7"       # Gross Profit formula
    assert ws_fin["B11"].value == "=B8-B10"     # EBITDA formula
    assert ws_fin["B14"].value == "=B11-B13"    # EBIT formula
    assert ws_fin["B18"].value == "=B14+B16-B17" # EBT formula
    assert ws_fin["B20"].value == "=B18-B19"    # Net Income formula
    assert ws_fin["B35"].value == "=B32-B25"    # Net Debt memo formula
    assert ws_fin["B45"].value == "=B40-ABS(B42)" # Free Cash Flow formula

    # 3. Inspect Ratios & Peers
    ws_rat = wb["Ratios & Peers"]
    assert ws_rat["B6"].value == "='3-Statement Financials'!B9"   # Gross Margin % link
    assert ws_rat["B7"].value == "='3-Statement Financials'!B12"  # EBITDA Margin % link
    assert "MEDIAN" in str(ws_rat.cell(row=ws_rat.max_row - 1, column=1).value)
    assert "AVERAGE" in str(ws_rat.cell(row=ws_rat.max_row, column=1).value)

    # 4. Inspect DCF Valuation
    ws_dcf = wb["DCF Valuation"]
    # Check assumptions in blue font
    assert ws_dcf["B6"].font.color.rgb in ("0000FF", "000000FF")
    # Check projection schedule formulas
    assert ws_dcf["D16"].value == "=$B$6*(1+$B$7)"
    assert ws_dcf["D18"].value == "=1/(1+$B$8)^D17"
    assert ws_dcf["D19"].value == "=D16*D18"
    assert ws_dcf["B22"].value.startswith("=SUM(D19:")
    assert ws_dcf["B24"].value == "=B23/($B$8-$B$9)"  # Terminal Value
    assert ws_dcf["B26"].value == "=B22+B25"         # Enterprise Value
    assert ws_dcf["B28"].value == "=B26-B27"         # Equity Value
    assert ws_dcf["B30"].value == "=B28/B29"         # Intrinsic Value
    assert ws_dcf["B32"].value == "=(B30/B31)-1"     # Upside %

    # Check 5x5 sensitivity matrix contains closed-form NPV formulas
    matrix_base_cell = ws_dcf["E38"].value  # Base WACC row 38, Base g_term col E
    assert matrix_base_cell is not None
    assert "NPV(" in matrix_base_cell


def test_excel_export_custom_parameters():
    """Verify that custom DCF slider parameters are reflected in the generated workbook."""
    params = {
        "fcf_growth": 14.5,
        "wacc": 12.0,
        "terminal_growth": 4.5,
        "projection_years": 8
    }
    resp = client.get("/api/companies/ASIANPAINT.NS/export/xlsx", params=params)
    assert resp.status_code == 200

    wb = openpyxl.load_workbook(io.BytesIO(resp.content), data_only=False)
    ws_dcf = wb["DCF Valuation"]

    # Verify overridden assumptions
    assert ws_dcf["B7"].value == 0.145  # 14.5%
    assert ws_dcf["B8"].value == 0.12   # 12.0%
    assert ws_dcf["B9"].value == 0.045  # 4.5%

    # Verify 8-year projection columns (D=Yr1, E=Yr2, F=Yr3, G=Yr4, H=Yr5, I=Yr6, J=Yr7, K=Yr8)
    assert ws_dcf["K15"].value == "Year 8"
    assert ws_dcf["B22"].value == "=SUM(D19:K19)"
