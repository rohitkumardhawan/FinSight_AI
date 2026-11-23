"""
Tests for Live Discrepancies Resolution:
1. Unified Net Debt calculation across Balance Sheet, DCF, and Ratios.
2. Synchronized EV/EBITDA calculation across /analysis and /peers.
3. Reconciled Income Statement Other Income / (Expense) on read.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.financial.metrics import calculate_net_debt, calculate_ev_to_ebitda

client = TestClient(app)


def test_calculate_net_debt_pure_math():
    """Verify Net Debt = Total Debt - Cash & Equivalents."""
    # Asian Paints FY2026 exact numbers: 39,289.30 Cr - 6,728.30 Cr = 32,561.00 Cr
    tot_debt = 39289300000.0
    cash = 6728300000.0
    assert calculate_net_debt(tot_debt, cash) == 32561000000.0

    # Handles None gracefully
    assert calculate_net_debt(None, None) == 0.0
    assert calculate_net_debt(100.0, None) == 100.0
    assert calculate_net_debt(None, 50.0) == -50.0
    assert calculate_net_debt(100.0, 150.0) == -50.0


def test_calculate_ev_to_ebitda_pure_math():
    """Verify EV/EBITDA = (Market Cap + Net Debt) / EBITDA."""
    mcap = 2478589383192.0
    net_debt = 32561000000.0
    ebitda = 68360400000.0
    # EV = 2,511,150,383,192 / 68,360,400,000 = 36.7339 -> 36.73
    assert calculate_ev_to_ebitda(mcap, net_debt, ebitda) == 36.73

    # Edge cases
    assert calculate_ev_to_ebitda(None, net_debt, ebitda) is None
    assert calculate_ev_to_ebitda(mcap, net_debt, None) is None
    assert calculate_ev_to_ebitda(mcap, net_debt, 0.0) is None
    assert calculate_ev_to_ebitda(mcap, net_debt, -100.0) is None


def test_other_income_reconciliation_math():
    """Verify Other Income = PBT - (EBIT - Interest)."""
    pbt = 58618200000.0
    ebit = 54873100000.0
    interest = 2171500000.0
    # 58,618.2 - (54,873.1 - 2,171.5) = 58,618.2 - 52,701.6 = 5,916.60 Cr
    reconciled = round(pbt - (ebit - abs(interest)), 2)
    assert reconciled == 5916600000.0


def test_asianpaint_unified_net_debt_and_other_income_api():
    """GET /api/companies/ASIANPAINT.NS/analysis must dynamically reconcile Net Debt and Other Income."""
    res = client.get("/api/companies/ASIANPAINT.NS/analysis")
    assert res.status_code == 200, f"Expected 200: {res.text}"

    data = res.json()
    periods = data.get("periods", [])
    assert len(periods) > 0

    annual_periods = [
        p for p in periods
        if p.get("statement_type") != "quarterly"
        and not (p.get("fiscal_period") or "").upper().startswith("Q")
    ]
    p_2026 = next((p for p in annual_periods if p.get("fiscal_year") == 2026), None)
    assert p_2026 is not None, "FY2026 period must exist for ASIANPAINT.NS"

    # Net Debt must be 32,561.00 Cr (32561000000.0) not old Yahoo Net Debt 16,204.30 Cr
    assert p_2026.get("net_debt") == 32561000000.0

    # Other income must be reconciled to 5,916.60 Cr (5916600000.0)
    assert p_2026.get("other_income") == 5916600000.0

    # EV/EBITDA on latest period must match peers target EV/EBITDA
    assert p_2026.get("ev_to_ebitda") is not None
    ev_ebitda_analysis = p_2026.get("ev_to_ebitda")

    # Now verify /peers returns the exact same EV/EBITDA
    peer_res = client.get("/api/companies/ASIANPAINT.NS/peers")
    assert peer_res.status_code == 200, f"Expected 200: {peer_res.text}"
    peer_data = peer_res.json()
    target = peer_data.get("target", {})
    assert target.get("symbol") == "ASIANPAINT.NS"
    assert target.get("ev_to_ebitda") == ev_ebitda_analysis, (
        f"/analysis ev_to_ebitda ({ev_ebitda_analysis}) must equal /peers ev_to_ebitda ({target.get('ev_to_ebitda')})"
    )


def test_asianpaint_dcf_net_debt_matches_balance_sheet():
    """GET /api/companies/ASIANPAINT.NS/dcf must report Net Debt equal to FY2026 Balance Sheet Net Debt."""
    dcf_res = client.get("/api/companies/ASIANPAINT.NS/dcf")
    assert dcf_res.status_code == 200, f"Expected 200: {dcf_res.text}"
    dcf_data = dcf_res.json()
    assert dcf_data.get("net_debt") == 32561000000.0
