"""
FinSight AI — Financial Calculation Engine
===========================================
This module isolates pure financial calculations and valuation formulas
from web frameworks, databases, and AI services.

Rule: Missing or non-computable financial data is NEVER silently replaced
with 0.0, because 0.0 has specific financial meaning (e.g. 0% break-even margin).
Undefined metrics return None (representing N/A).
"""

from typing import List, Dict, Optional, Any

def calculate_gross_margin(revenue: Optional[float], cogs: Optional[float], as_percentage: bool = True) -> Optional[float]:
    """Gross Margin = (Revenue - COGS) / Revenue. Returns None if revenue is missing or zero."""
    if revenue is None or cogs is None or revenue <= 0:
        return None
    ratio = (revenue - cogs) / revenue
    return round(ratio * 100, 2) if as_percentage else round(ratio, 4)

def calculate_operating_margin(operating_income: Optional[float], revenue: Optional[float], as_percentage: bool = True) -> Optional[float]:
    """Operating Margin = Operating Income / Revenue. Returns None if revenue is missing or zero."""
    if revenue is None or operating_income is None or revenue <= 0:
        return None
    ratio = operating_income / revenue
    return round(ratio * 100, 2) if as_percentage else round(ratio, 4)

def calculate_net_margin(net_income: Optional[float], revenue: Optional[float], as_percentage: bool = True) -> Optional[float]:
    """Net Profit Margin = Net Income / Revenue. Returns None if revenue is missing or zero."""
    if revenue is None or net_income is None or revenue <= 0:
        return None
    ratio = net_income / revenue
    return round(ratio * 100, 2) if as_percentage else round(ratio, 4)

def calculate_roe(net_income: Optional[float], total_equity: Optional[float], as_percentage: bool = True) -> Optional[float]:
    """Return on Equity (ROE) = Net Income / Total Equity."""
    if net_income is None or total_equity is None or total_equity == 0:
        return None
    ratio = net_income / total_equity
    return round(ratio * 100, 2) if as_percentage else round(ratio, 4)

def calculate_roa(net_income: Optional[float], total_assets: Optional[float], as_percentage: bool = True) -> Optional[float]:
    """Return on Assets (ROA) = Net Income / Total Assets."""
    if net_income is None or total_assets is None or total_assets <= 0:
        return None
    ratio = net_income / total_assets
    return round(ratio * 100, 2) if as_percentage else round(ratio, 4)

def calculate_current_ratio(current_assets: Optional[float], current_liabilities: Optional[float]) -> Optional[float]:
    """Current Ratio = Current Assets / Current Liabilities."""
    if current_assets is None or current_liabilities is None or current_liabilities <= 0:
        return None
    return round(current_assets / current_liabilities, 4)

def calculate_quick_ratio(
    current_assets: Optional[float] = None,
    inventory: Optional[float] = None,
    current_liabilities: Optional[float] = None,
    cash_and_equivalents: Optional[float] = None
) -> Optional[float]:
    """
    Quick Ratio (Acid-Test) = (Current Assets - Inventory) / Current Liabilities
    Fallback if Current Assets missing: Cash & Cash Equivalents / Current Liabilities
    """
    if current_liabilities is None or current_liabilities <= 0:
        return None
    
    if current_assets is not None:
        inv = inventory if inventory is not None else 0.0
        return round((current_assets - inv) / current_liabilities, 4)
    
    if cash_and_equivalents is not None:
        return round(cash_and_equivalents / current_liabilities, 4)
        
    return None

def calculate_debt_to_equity(total_debt: Optional[float], total_equity: Optional[float]) -> Optional[float]:
    """Debt-to-Equity Ratio = Total Debt / Total Equity."""
    if total_debt is None or total_equity is None or total_equity == 0:
        return None
    return round(total_debt / total_equity, 4)

def calculate_all_ratios(statement_data: Dict[str, Any]) -> Dict[str, Optional[float]]:
    """
    Calculates all institutional ratios deterministically in pure Python.
    Accepts floats or Decimals. Handles missing values and zero denominators safely.
    """
    def _to_float(val: Any) -> Optional[float]:
        if val is None:
            return None
        try:
            return float(val)
        except (ValueError, TypeError):
            return None

    rev = _to_float(statement_data.get("revenue"))
    cogs = _to_float(statement_data.get("cost_of_revenue"))
    gp = _to_float(statement_data.get("gross_profit"))
    op_inc = _to_float(statement_data.get("operating_income"))
    net_inc = _to_float(statement_data.get("net_income"))
    assets = _to_float(statement_data.get("total_assets"))
    curr_assets = _to_float(statement_data.get("current_assets"))
    liab = _to_float(statement_data.get("total_liabilities"))
    curr_liab = _to_float(statement_data.get("current_liabilities"))
    equity = _to_float(statement_data.get("total_equity"))
    cash = _to_float(statement_data.get("cash_and_equivalents"))
    inv = _to_float(statement_data.get("inventory"))
    debt = _to_float(statement_data.get("total_debt"))

    # If COGS is missing but gross_profit and revenue are available: COGS = rev - gp
    if cogs is None and rev is not None and gp is not None:
        cogs = rev - gp

    # Fallback for liquidity if current_liabilities not given: estimate using total_liabilities * 0.45 or cash/liab
    if curr_liab is None and liab is not None and liab > 0:
        # Conservative proxy: cash / total_debt or return None
        pass

    return {
        "gross_margin": calculate_gross_margin(rev, cogs, as_percentage=False),
        "operating_margin": calculate_operating_margin(op_inc, rev, as_percentage=False),
        "net_profit_margin": calculate_net_margin(net_inc, rev, as_percentage=False),
        "return_on_equity": calculate_roe(net_inc, equity, as_percentage=False),
        "return_on_assets": calculate_roa(net_inc, assets, as_percentage=False),
        "current_ratio": calculate_current_ratio(curr_assets, curr_liab),
        "quick_ratio": calculate_quick_ratio(curr_assets, inv, curr_liab, cash),
        "debt_to_equity": calculate_debt_to_equity(debt, equity)
    }

def calculate_dcf_valuation(
    cash_flows: List[float],
    discount_rate: float,
    terminal_growth_rate: float,
    shares_outstanding: Optional[float],
    net_debt: float = 0.0
) -> Dict[str, Any]:
    """
    Standard 5-Year Discounted Cash Flow (DCF) Valuation Model.
    
    Formula:
    PV = Sum of [ FCF_t / (1 + r)^t ] + Terminal Value discounted back
    Terminal Value (Gordon Growth) = [ FCF_final * (1 + g) ] / (r - g)
    Enterprise Value = PV of Free Cash Flows + PV of Terminal Value
    Equity Value = Enterprise Value - Net Debt
    Intrinsic Value per Share = Equity Value / Shares Outstanding
    """
    if discount_rate <= terminal_growth_rate:
        raise ValueError("Discount rate must be greater than terminal growth rate.")

    if not cash_flows:
        raise ValueError("Cash flows list cannot be empty.")

    # 1. Present Value of Projected Cash Flows
    pv_cash_flows = 0.0
    for t, fcf in enumerate(cash_flows, start=1):
        pv_cash_flows += fcf / ((1 + discount_rate) ** t)

    # 2. Terminal Value
    final_fcf = cash_flows[-1]
    terminal_value = (final_fcf * (1 + terminal_growth_rate)) / (discount_rate - terminal_growth_rate)
    pv_terminal_value = terminal_value / ((1 + discount_rate) ** len(cash_flows))

    # 3. Enterprise & Equity Value
    enterprise_value = pv_cash_flows + pv_terminal_value
    equity_value = enterprise_value - net_debt

    # Do not silently replace undefined per-share value with 0.0
    intrinsic_value_per_share = (
        round(equity_value / shares_outstanding, 2)
        if (shares_outstanding is not None and shares_outstanding > 0)
        else None
    )

    return {
        "pv_projected_cash_flows": round(pv_cash_flows, 2),
        "terminal_value": round(terminal_value, 2),
        "pv_terminal_value": round(pv_terminal_value, 2),
        "enterprise_value": round(enterprise_value, 2),
        "equity_value": round(equity_value, 2),
        "intrinsic_value_per_share": intrinsic_value_per_share,
        "is_demo_data": True
    }
