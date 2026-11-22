"""
FinSight AI — Automated Financial Calculations Test Suite
==========================================================
Tests edge cases, division by zero protection, and non-silent missing data handling.
"""

import pytest
from app.financial.metrics import (
    calculate_gross_margin,
    calculate_operating_margin,
    calculate_net_margin,
    calculate_dcf_valuation
)

def test_gross_margin_calculation():
    # Regular case
    margin = calculate_gross_margin(revenue=100.0, cogs=40.0)
    assert margin == 60.0

def test_gross_margin_zero_or_none_revenue():
    # Missing or zero revenue MUST return None, NOT 0.0 (prevents false break-even representation)
    assert calculate_gross_margin(revenue=0.0, cogs=10.0) is None
    assert calculate_gross_margin(revenue=-50.0, cogs=10.0) is None
    assert calculate_gross_margin(revenue=None, cogs=10.0) is None

def test_operating_margin():
    assert calculate_operating_margin(operating_income=30.0, revenue=100.0) == 30.0
    assert calculate_operating_margin(operating_income=30.0, revenue=0.0) is None

def test_net_margin():
    assert calculate_net_margin(net_income=25.0, revenue=100.0) == 25.0
    assert calculate_net_margin(net_income=25.0, revenue=0.0) is None

def test_dcf_valuation_standard():
    cash_flows = [100.0, 110.0, 121.0, 133.1, 146.4]
    res = calculate_dcf_valuation(
        cash_flows=cash_flows,
        discount_rate=0.09,
        terminal_growth_rate=0.025,
        shares_outstanding=10.0,
        net_debt=50.0
    )
    assert res["is_demo_data"] is True
    assert res["enterprise_value"] > 0
    assert res["equity_value"] > 0
    assert res["intrinsic_value_per_share"] > 0

def test_dcf_valuation_zero_shares_returns_none():
    cash_flows = [100.0, 110.0, 121.0, 133.1, 146.4]
    res = calculate_dcf_valuation(
        cash_flows=cash_flows,
        discount_rate=0.09,
        terminal_growth_rate=0.025,
        shares_outstanding=0.0,
        net_debt=0.0
    )
    # Must NOT silently return 0.0 for intrinsic value when shares are 0
    assert res["intrinsic_value_per_share"] is None

def test_dcf_discount_rate_validation():
    with pytest.raises(ValueError, match="Discount rate must be greater than terminal growth rate"):
        calculate_dcf_valuation(
            cash_flows=[100.0],
            discount_rate=0.02,
            terminal_growth_rate=0.03,
            shares_outstanding=1.0
        )
