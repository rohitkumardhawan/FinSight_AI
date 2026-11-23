"""
FinSight AI — Institutional Discounted Cash Flow (DCF) Engine
============================================================
Performs deterministic institutional DCF valuation modeling:
- Auto-seeds defaults from Neon Postgres financial_periods and metadata_json
- 5–10 year Free Cash Flow projection with historical CAGR clamping (4%–22%)
- Gordon Growth Terminal Value & Enterprise/Equity Value calculation
- 5x5 Sensitivity Matrix (WACC vs Terminal Growth)
- Strict validation: wacc > terminal_growth + 0.01 (HTTP 422 on violation)
"""

from typing import List, Dict, Any, Optional
import math
import logging
from pydantic import BaseModel, Field
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.company import Company
from app.models.dataset import FinancialPeriod
from app.financial.metrics import calculate_net_debt

logger = logging.getLogger(__name__)


class DCFRequest(BaseModel):
    """User-provided parameter overrides for DCF valuation."""
    growth_rate: Optional[float] = Field(None, description="Projected annual FCF growth rate (e.g. 0.10 or 10.0)")
    wacc: Optional[float] = Field(None, description="Weighted Average Cost of Capital (e.g. 0.115 or 11.5)")
    terminal_growth_rate: Optional[float] = Field(None, description="Terminal growth rate (e.g. 0.04 or 4.0)")
    projection_years: Optional[int] = Field(5, ge=5, le=10, description="Projection horizon in years (5 to 10)")
    free_cash_flow: Optional[float] = Field(None, description="Base year Free Cash Flow override")
    net_debt: Optional[float] = Field(None, description="Net debt override (Total Debt - Cash)")
    shares_outstanding: Optional[float] = Field(None, description="Total diluted shares outstanding override")
    current_price: Optional[float] = Field(None, description="Current market share price override")


class ProjectedPeriod(BaseModel):
    year: int
    fiscal_year_label: str
    projected_fcf: float
    discount_factor: float
    pv_fcf: float


class SensitivityMatrix(BaseModel):
    wacc_rates: List[float]
    terminal_growth_rates: List[float]
    matrix: List[List[Optional[float]]]


class DCFResponse(BaseModel):
    symbol: str
    company_name: str
    currency: str
    current_price: float
    intrinsic_value: float
    upside_downside_pct: float
    enterprise_value: float
    equity_value: float
    pv_cash_flows: float
    pv_terminal_value: float
    terminal_value: float
    net_debt: float
    shares_outstanding: float
    fcf_base: float
    fcf_estimated: bool
    growth_rate: float
    historical_cagr: float
    wacc: float
    terminal_growth_rate: float
    projection_years: int
    projected_periods: List[ProjectedPeriod]
    sensitivity_matrix: SensitivityMatrix


def normalize_rate(val: Optional[float]) -> Optional[float]:
    """Converts percentage figures like 11.5 or 4.0 into decimal 0.115 or 0.04."""
    if val is None:
        return None
    if abs(val) > 1.0:
        return round(val / 100.0, 6)
    return round(val, 6)


def calculate_historical_cagr(annual_periods: List[FinancialPeriod]) -> float:
    """
    Computes 3Y-5Y revenue/operating CAGR from available annual periods.
    Clamps the result to 4.0% - 22.0% (0.04 - 0.22), with default fallback of 10.0% (0.10).
    """
    if len(annual_periods) < 2:
        return 0.10

    # Sort ascending by fiscal year
    sorted_periods = sorted(annual_periods, key=lambda p: p.fiscal_year or 0)
    # Pick oldest usable and newest
    first_p = sorted_periods[0]
    last_p = sorted_periods[-1]

    years = (last_p.fiscal_year or 0) - (first_p.fiscal_year or 0)
    if years <= 0:
        return 0.10

    # Try revenue CAGR first
    start_rev = (first_p.metrics_json or {}).get("revenue")
    end_rev = (last_p.metrics_json or {}).get("revenue")

    if start_rev and end_rev and start_rev > 0 and end_rev > 0:
        try:
            cagr = (end_rev / start_rev) ** (1.0 / years) - 1.0
            return max(0.04, min(0.22, round(cagr, 4)))
        except (ValueError, ZeroDivisionError, OverflowError):
            pass

    # Try net income if revenue not available
    start_ni = (first_p.metrics_json or {}).get("net_income")
    end_ni = (last_p.metrics_json or {}).get("net_income")
    if start_ni and end_ni and start_ni > 0 and end_ni > 0:
        try:
            cagr = (end_ni / start_ni) ** (1.0 / years) - 1.0
            return max(0.04, min(0.22, round(cagr, 4)))
        except (ValueError, ZeroDivisionError, OverflowError):
            pass

    return 0.10


def extract_fcf_and_debt(
    annual_periods: List[FinancialPeriod]
) -> tuple[float, bool, float, float, float]:
    """
    Extracts latest FCF, estimation flag, total debt, cash, and net debt.
    Returns: (fcf_base, fcf_estimated, total_debt, cash_and_equiv, net_debt)
    """
    if not annual_periods:
        return 1_000_000.0, True, 0.0, 0.0, 0.0

    sorted_periods = sorted(annual_periods, key=lambda p: p.fiscal_year or 0)
    latest_metrics = (sorted_periods[-1].metrics_json or {})

    # 1. Total Debt & Cash
    total_debt = float(latest_metrics.get("total_debt") or 0.0)
    cash_equiv = float(latest_metrics.get("cash_and_equivalents") or 0.0)
    net_debt = calculate_net_debt(total_debt, cash_equiv)

    # 2. Free Cash Flow resolution
    fcf = latest_metrics.get("free_cash_flow")
    if fcf is not None and float(fcf) > 0:
        return float(fcf), False, total_debt, cash_equiv, net_debt

    # Try OCF - abs(capex)
    ocf = latest_metrics.get("operating_cash_flow")
    capex = latest_metrics.get("capital_expenditure")
    if ocf is not None and capex is not None:
        calc_fcf = float(ocf) - abs(float(capex))
        if calc_fcf > 0:
            return calc_fcf, False, total_debt, cash_equiv, net_debt

    # Fallback to net_income * 0.8
    net_income = latest_metrics.get("net_income")
    if net_income is not None and float(net_income) > 0:
        return float(net_income) * 0.8, True, total_debt, cash_equiv, net_debt

    # Search previous periods for positive FCF
    for p in reversed(sorted_periods[:-1]):
        m = p.metrics_json or {}
        if m.get("free_cash_flow") and float(m["free_cash_flow"]) > 0:
            return float(m["free_cash_flow"]), False, total_debt, cash_equiv, net_debt
        if m.get("net_income") and float(m["net_income"]) > 0:
            return float(m["net_income"]) * 0.8, True, total_debt, cash_equiv, net_debt

    # Fallback to revenue * 0.08
    rev = latest_metrics.get("revenue")
    if rev and float(rev) > 0:
        return float(rev) * 0.08, True, total_debt, cash_equiv, net_debt

    return 100_000_000.0, True, total_debt, cash_equiv, net_debt


def extract_shares_and_price(
    company: Company,
    latest_metrics: Dict[str, Any]
) -> tuple[float, float]:
    """
    Resolves current market price and total diluted shares outstanding.
    Returns: (current_price, shares_outstanding)
    """
    metadata = company.metadata_json or {}
    quote = metadata.get("quote") or {}

    # Current Price
    price = quote.get("current_price") or metadata.get("current_price") or latest_metrics.get("share_price")
    current_price = float(price) if price and float(price) > 0 else 100.0

    # Market Cap (in trading currency)
    market_cap = float(quote.get("market_cap") or metadata.get("market_cap") or 0.0)

    # Direct Shares Outstanding
    raw_shares = quote.get("shares_outstanding") or metadata.get("shares_outstanding") or quote.get("sharesOutstanding")
    shares = float(raw_shares) if raw_shares and float(raw_shares) > 0 else 0.0

    # Sanity check: if shares is available, verify (shares * current_price) matches market_cap within 5%
    if shares > 0 and market_cap > 0 and current_price > 0:
        implied_ratio = (shares * current_price) / market_cap
        if abs(implied_ratio - 1.0) < 0.05:
            return current_price, shares

    if market_cap > 0 and current_price > 0:
        shares = market_cap / current_price
        if shares > 0:
            return current_price, shares

    # Try net_income / eps
    net_inc = latest_metrics.get("net_income")
    eps = latest_metrics.get("eps")
    if net_inc and eps and float(eps) > 0:
        shares = float(net_inc) / float(eps)
        if shares > 0:
            return current_price, shares

    return current_price, 1_000_000.0


def calculate_dcf(
    company: Company,
    periods: List[FinancialPeriod],
    request: Optional[DCFRequest] = None
) -> DCFResponse:
    """
    Computes a full institutional DCF valuation model for a company.
    Enforces strict validation: wacc > terminal_growth + 0.01
    """
    annual_periods = [
        p for p in periods
        if p.fiscal_year is not None
        and getattr(p, "statement_type", "") != "quarterly"
        and (not getattr(p, "fiscal_period", "") or getattr(p, "fiscal_period", "").startswith("FY"))
    ]
    if not annual_periods:
        annual_periods = periods

    currency = (company.currency or "USD").upper()
    is_inr = (currency == "INR") or (company.symbol or "").endswith((".NS", ".BO"))

    # 1. Determine baseline defaults
    default_wacc = 0.115 if is_inr else 0.090
    default_terminal_growth = 0.040 if is_inr else 0.025
    historical_cagr = calculate_historical_cagr(annual_periods)

    fcf_base_auto, fcf_est_auto, _, _, net_debt_auto = extract_fcf_and_debt(annual_periods)
    latest_metrics = (sorted(annual_periods, key=lambda p: p.fiscal_year or 0)[-1].metrics_json or {}) if annual_periods else {}
    current_price_auto, shares_auto = extract_shares_and_price(company, latest_metrics)

    # 2. Merge overrides from request
    growth_rate = normalize_rate(request.growth_rate) if (request and request.growth_rate is not None) else historical_cagr
    wacc = normalize_rate(request.wacc) if (request and request.wacc is not None) else default_wacc
    terminal_growth = normalize_rate(request.terminal_growth_rate) if (request and request.terminal_growth_rate is not None) else default_terminal_growth
    projection_years = request.projection_years if (request and request.projection_years is not None) else 5
    projection_years = max(5, min(10, projection_years))

    fcf_base = float(request.free_cash_flow) if (request and request.free_cash_flow is not None) else fcf_base_auto
    fcf_estimated = False if (request and request.free_cash_flow is not None) else fcf_est_auto

    net_debt = float(request.net_debt) if (request and request.net_debt is not None) else net_debt_auto
    shares_outstanding = float(request.shares_outstanding) if (request and request.shares_outstanding is not None) else shares_auto
    current_price = float(request.current_price) if (request and request.current_price is not None) else current_price_auto

    # 3. CRITICAL VALIDATION: wacc > terminal_growth + 0.01
    spread = round(wacc - terminal_growth, 6)
    if spread <= 0.01:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"WACC must be at least 1% greater than terminal growth rate (wacc > terminal_growth + 0.01). "
                f"Supplied WACC: {wacc * 100:.2f}%, Terminal Growth: {terminal_growth * 100:.2f}%, Spread: {spread * 100:.2f}%."
            )
        )

    # 4. Project FCFs across projection horizon
    projected_periods: List[ProjectedPeriod] = []
    pv_cash_flows = 0.0
    latest_year = (sorted(annual_periods, key=lambda p: p.fiscal_year or 0)[-1].fiscal_year or 2026) if annual_periods else 2026

    current_fcf = fcf_base
    for t in range(1, projection_years + 1):
        current_fcf = current_fcf * (1.0 + growth_rate)
        discount_factor = 1.0 / ((1.0 + wacc) ** t)
        pv_fcf = current_fcf * discount_factor
        pv_cash_flows += pv_fcf

        projected_periods.append(ProjectedPeriod(
            year=t,
            fiscal_year_label=f"FY{latest_year + t}",
            projected_fcf=round(current_fcf, 2),
            discount_factor=round(discount_factor, 4),
            pv_fcf=round(pv_fcf, 2)
        ))

    # 5. Terminal Value Calculation (Gordon Growth Model)
    # TV_n = [FCF_n * (1 + g)] / (WACC - g)
    fcf_terminal = current_fcf * (1.0 + terminal_growth)
    terminal_value = fcf_terminal / (wacc - terminal_growth)
    pv_terminal_value = terminal_value / ((1.0 + wacc) ** projection_years)

    # 6. Enterprise Value, Equity Value & Per-Share Value
    enterprise_value = pv_cash_flows + pv_terminal_value
    equity_value = enterprise_value - net_debt

    # Guard shares
    safe_shares = shares_outstanding if shares_outstanding > 0 else 1.0
    intrinsic_value = equity_value / safe_shares
    intrinsic_value = max(0.01, round(intrinsic_value, 2))

    # Upside / Downside %
    upside_downside_pct = 0.0
    if current_price > 0:
        upside_downside_pct = round(((intrinsic_value - current_price) / current_price) * 100.0, 2)

    # 7. Compute 5x5 Sensitivity Matrix
    # WACC steps: -2%, -1%, base, +1%, +2%
    # Terminal Growth steps: -1%, -0.5%, base, +0.5%, +1%
    wacc_rates = [round(wacc + delta, 4) for delta in [-0.02, -0.01, 0.0, 0.01, 0.02]]
    tg_rates = [round(terminal_growth + delta, 4) for delta in [-0.01, -0.005, 0.0, 0.005, 0.01]]

    matrix_rows: List[List[Optional[float]]] = []
    for w in wacc_rates:
        row: List[Optional[float]] = []
        for tg in tg_rates:
            # Check feasibility
            if w <= tg + 0.005:
                row.append(None)
                continue

            # Calculate discounted CF for this w
            cf_sum = 0.0
            temp_fcf = fcf_base
            for t in range(1, projection_years + 1):
                temp_fcf = temp_fcf * (1.0 + growth_rate)
                cf_sum += temp_fcf / ((1.0 + w) ** t)

            # Terminal Value for this w and tg
            cell_tv = (temp_fcf * (1.0 + tg)) / (w - tg)
            cell_pv_tv = cell_tv / ((1.0 + w) ** projection_years)
            cell_ev = cf_sum + cell_pv_tv
            cell_eq = cell_ev - net_debt
            cell_price = max(0.01, round(cell_eq / safe_shares, 2))
            row.append(cell_price)
        matrix_rows.append(row)

    return DCFResponse(
        symbol=company.symbol or company.ticker or "UNKNOWN",
        company_name=company.company_name,
        currency=currency,
        current_price=round(current_price, 2),
        intrinsic_value=intrinsic_value,
        upside_downside_pct=upside_downside_pct,
        enterprise_value=round(enterprise_value, 2),
        equity_value=round(equity_value, 2),
        pv_cash_flows=round(pv_cash_flows, 2),
        pv_terminal_value=round(pv_terminal_value, 2),
        terminal_value=round(terminal_value, 2),
        net_debt=round(net_debt, 2),
        shares_outstanding=round(shares_outstanding, 2),
        fcf_base=round(fcf_base, 2),
        fcf_estimated=fcf_estimated,
        growth_rate=round(growth_rate, 4),
        historical_cagr=round(historical_cagr, 4),
        wacc=round(wacc, 4),
        terminal_growth_rate=round(terminal_growth, 4),
        projection_years=projection_years,
        projected_periods=projected_periods,
        sensitivity_matrix=SensitivityMatrix(
            wacc_rates=wacc_rates,
            terminal_growth_rates=tg_rates,
            matrix=matrix_rows
        )
    )
