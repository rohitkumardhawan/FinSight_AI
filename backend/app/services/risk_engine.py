"""
FinSight AI — Institutional Risk Intelligence Engine
===================================================
Computes 4 deterministic institutional risk pillars from Neon Postgres data:
1. Leverage & Liquidity (Debt-to-Equity, Interest Coverage, Current Ratio)
2. Profitability & Margin Stability (OPM % standard deviation, YoY revenue & margin contraction)
3. Valuation Stretch (Current P/E vs Historical Avg P/E, DCF downside)
4. Earnings Quality (Cash conversion ratio: FCF / Net Income < 0.70 warning)

Returns overall_score (0-100), risk_level (Low, Moderate, Elevated, High),
detailed pillar figures, and 3 grounded Gemini 3.8 Flash watchpoints (with deterministic fallback).
"""

from typing import List, Dict, Any, Optional
import math
import statistics
import logging
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from google import genai
from google.genai import types

from app.core.config import settings
from app.models.company import Company
from app.models.dataset import FinancialPeriod
from app.services.dcf_engine import calculate_dcf

logger = logging.getLogger(__name__)


class LeverageLiquidityPillar(BaseModel):
    pillar_score: float
    risk_level: str
    debt_to_equity: Optional[float]
    interest_coverage: Optional[float]
    current_ratio: Optional[float]
    total_debt: Optional[float]
    cash_and_equivalents: Optional[float]
    net_debt: Optional[float]
    assessment: str


class ProfitabilityStabilityPillar(BaseModel):
    pillar_score: float
    risk_level: str
    opm_std_dev: float
    historical_opms: List[float]
    latest_revenue_growth_pct: Optional[float]
    revenue_contracting: bool
    latest_opm_change_pp: Optional[float]
    margin_contracting: bool
    assessment: str


class ValuationStretchPillar(BaseModel):
    pillar_score: float
    risk_level: str
    current_pe: Optional[float]
    historical_avg_pe: Optional[float]
    pe_stretch_multiple: Optional[float]
    dcf_intrinsic_value: float
    dcf_downside_pct: float
    assessment: str


class EarningsQualityPillar(BaseModel):
    pillar_score: float
    risk_level: str
    fcf_to_net_income: Optional[float]
    is_conversion_warning: bool
    free_cash_flow: Optional[float]
    net_income: Optional[float]
    assessment: str


class RiskWatchpoint(BaseModel):
    category: str
    title: str
    description: str
    severity: str  # "Low", "Moderate", "Elevated", "High"


class RiskIntelligenceResponse(BaseModel):
    symbol: str
    company_name: str
    currency: str
    overall_score: float = Field(..., ge=0, le=100, description="Overall Risk Score (0 = lowest risk, 100 = extreme risk)")
    risk_level: str = Field(..., description="Risk Level: Low, Moderate, Elevated, High")
    pillars: Dict[str, Any]
    watchpoints: List[RiskWatchpoint]
    generated_at: str


def _get_genai_client() -> Optional[genai.Client]:
    """Returns an authenticated Google GenAI Client with 7s timeout if API key is present."""
    if not settings.GEMINI_API_KEY:
        return None
    try:
        return genai.Client(
            api_key=settings.GEMINI_API_KEY,
            http_options=types.HttpOptions(timeout=7000)
        )
    except Exception as e:
        logger.error(f"Failed to initialize Google GenAI Client in risk engine: {e}")
        return None


def get_risk_tier(score: float) -> str:
    """Translates 0-100 score into standard institutional risk tier."""
    if score <= 25:
        return "Low"
    elif score <= 50:
        return "Moderate"
    elif score <= 75:
        return "Elevated"
    else:
        return "High"


def calculate_risk_intelligence(
    company: Company,
    periods: List[FinancialPeriod]
) -> RiskIntelligenceResponse:
    """
    Computes deterministic risk pillars and grounded watchpoints for a company.
    """
    annual_periods = [
        p for p in periods
        if p.fiscal_year is not None
        and getattr(p, "statement_type", "") != "quarterly"
        and (not getattr(p, "fiscal_period", "") or getattr(p, "fiscal_period", "").startswith("FY"))
    ]
    if not annual_periods:
        annual_periods = periods
    sorted_periods = sorted(annual_periods, key=lambda p: p.fiscal_year or 0)

    latest_p = sorted_periods[-1] if sorted_periods else None
    prev_p = sorted_periods[-2] if len(sorted_periods) >= 2 else None

    latest_m = latest_p.metrics_json or {} if latest_p else {}
    prev_m = prev_p.metrics_json or {} if prev_p else {}

    meta = company.metadata_json or {}
    quote = meta.get("quote") or {}
    currency = company.currency or "INR"

    # =========================================================
    # Pillar 1: Leverage & Liquidity
    # =========================================================
    total_debt = float(latest_m.get("total_debt") or 0.0)
    total_equity = float(latest_m.get("total_equity") or 0.0)
    cash_equiv = float(latest_m.get("cash_and_equivalents") or 0.0)
    net_debt = total_debt - cash_equiv
    curr_assets = float(latest_m.get("current_assets") or 0.0)
    curr_liab = float(latest_m.get("current_liabilities") or 0.0)
    ebit = float(latest_m.get("ebit") or latest_m.get("operating_income") or 0.0)
    interest_exp = float(latest_m.get("interest_expense") or 0.0)

    # Debt to Equity
    de_ratio = round(total_debt / total_equity, 2) if total_equity > 0 else None
    if de_ratio is None:
        de_score = 50.0
    elif de_ratio <= 0.3:
        de_score = 10.0
    elif de_ratio <= 0.8:
        de_score = 25.0
    elif de_ratio <= 1.5:
        de_score = 50.0
    elif de_ratio <= 2.5:
        de_score = 75.0
    else:
        de_score = 95.0

    # Interest Coverage
    if interest_exp <= 0:
        int_coverage = 99.9 if ebit > 0 else 1.0
        coverage_score = 10.0 if ebit > 0 else 75.0
    else:
        int_coverage = round(ebit / interest_exp, 2)
        if int_coverage >= 10.0:
            coverage_score = 10.0
        elif int_coverage >= 5.0:
            coverage_score = 25.0
        elif int_coverage >= 2.5:
            coverage_score = 50.0
        elif int_coverage >= 1.5:
            coverage_score = 75.0
        else:
            coverage_score = 95.0

    # Current Ratio
    if curr_liab > 0 and curr_assets > 0:
        curr_ratio = round(curr_assets / curr_liab, 2)
        if curr_ratio >= 1.6:
            cr_score = 10.0
        elif curr_ratio >= 1.2:
            cr_score = 30.0
        elif curr_ratio >= 1.0:
            cr_score = 50.0
        elif curr_ratio >= 0.8:
            cr_score = 75.0
        else:
            cr_score = 95.0
    else:
        curr_ratio = None
        cr_score = 50.0

    leverage_score = round((de_score + coverage_score + cr_score) / 3.0, 1)
    leverage_tier = get_risk_tier(leverage_score)
    leverage_assessment = (
        f"Debt-to-Equity is {de_ratio if de_ratio is not None else 'N/A'}, "
        f"Interest Coverage is {int_coverage}x, and Current Ratio stands at {curr_ratio if curr_ratio is not None else 'N/A'}."
    )

    pillar_leverage = LeverageLiquidityPillar(
        pillar_score=leverage_score,
        risk_level=leverage_tier,
        debt_to_equity=de_ratio,
        interest_coverage=int_coverage,
        current_ratio=curr_ratio,
        total_debt=total_debt,
        cash_and_equivalents=cash_equiv,
        net_debt=net_debt,
        assessment=leverage_assessment
    )

    # =========================================================
    # Pillar 2: Profitability & Margin Stability
    # =========================================================
    opm_history: List[float] = []
    for p in sorted_periods:
        m = p.metrics_json or {}
        opm = m.get("opm_pct")
        if opm is None and m.get("revenue") and m.get("operating_income") and m["revenue"] > 0:
            opm = (m["operating_income"] / m["revenue"]) * 100.0
        if opm is not None:
            opm_history.append(round(float(opm), 2))

    if len(opm_history) >= 2:
        opm_std_dev = round(statistics.stdev(opm_history), 2)
    elif len(opm_history) == 1:
        opm_std_dev = 0.0
    else:
        opm_std_dev = 2.5

    # OPM volatility score
    if opm_std_dev <= 1.5:
        opm_score = 15.0
    elif opm_std_dev <= 3.0:
        opm_score = 30.0
    elif opm_std_dev <= 5.0:
        opm_score = 55.0
    elif opm_std_dev <= 8.0:
        opm_score = 75.0
    else:
        opm_score = 90.0

    # YoY revenue contraction
    curr_rev = latest_m.get("revenue")
    prev_rev = prev_m.get("revenue")
    revenue_growth_pct: Optional[float] = None
    rev_contracting = False
    if curr_rev and prev_rev and prev_rev > 0:
        revenue_growth_pct = round(((curr_rev - prev_rev) / prev_rev) * 100.0, 2)
        if revenue_growth_pct < 0:
            rev_contracting = True

    # YoY margin contraction
    curr_opm = latest_m.get("opm_pct")
    prev_opm = prev_m.get("opm_pct")
    opm_change_pp: Optional[float] = None
    margin_contracting = False
    if curr_opm is not None and prev_opm is not None:
        opm_change_pp = round(curr_opm - prev_opm, 2)
        if opm_change_pp < -0.5:
            margin_contracting = True

    # Adjust score with penalties
    rev_penalty = 25.0 if rev_contracting else 0.0
    margin_penalty = 20.0 if margin_contracting else 0.0
    stability_score = round(min(100.0, opm_score + rev_penalty + margin_penalty), 1)
    stability_tier = get_risk_tier(stability_score)
    stability_assessment = (
        f"Operating margin standard deviation is {opm_std_dev}%. "
        f"Latest revenue growth is {revenue_growth_pct if revenue_growth_pct is not None else 'N/A'}% "
        f"({'contracting' if rev_contracting else 'expanding'}). "
        f"Latest OPM delta is {opm_change_pp if opm_change_pp is not None else 'N/A'} pp."
    )

    pillar_stability = ProfitabilityStabilityPillar(
        pillar_score=stability_score,
        risk_level=stability_tier,
        opm_std_dev=opm_std_dev,
        historical_opms=opm_history,
        latest_revenue_growth_pct=revenue_growth_pct,
        revenue_contracting=rev_contracting,
        latest_opm_change_pp=opm_change_pp,
        margin_contracting=margin_contracting,
        assessment=stability_assessment
    )

    # =========================================================
    # Pillar 3: Valuation Stretch
    # =========================================================
    # Current P/E
    current_pe = quote.get("trailing_pe") or latest_m.get("pe_ratio")
    current_pe = round(float(current_pe), 2) if current_pe and float(current_pe) > 0 else None

    # Historical average P/E
    pe_history: List[float] = []
    for p in sorted_periods:
        pe = (p.metrics_json or {}).get("pe_ratio")
        if pe and float(pe) > 0:
            pe_history.append(float(pe))

    if pe_history:
        avg_pe = round(statistics.mean(pe_history), 2)
    elif current_pe:
        avg_pe = round(current_pe * 0.9, 2)
    else:
        avg_pe = None

    # Stretch multiple
    if current_pe and avg_pe and avg_pe > 0:
        stretch_multiple = round(current_pe / avg_pe, 2)
        if stretch_multiple <= 0.95:
            stretch_score = 15.0
        elif stretch_multiple <= 1.15:
            stretch_score = 30.0
        elif stretch_multiple <= 1.35:
            stretch_score = 55.0
        elif stretch_multiple <= 1.60:
            stretch_score = 75.0
        else:
            stretch_score = 95.0
    else:
        stretch_multiple = 1.0
        stretch_score = 45.0

    # DCF valuation comparison
    dcf_res = calculate_dcf(company, periods)
    dcf_intrinsic = dcf_res.intrinsic_value
    current_price = dcf_res.current_price

    if current_price > 0 and current_price > dcf_intrinsic:
        dcf_downside_pct = round(((current_price - dcf_intrinsic) / current_price) * 100.0, 2)
        if dcf_downside_pct <= 10.0:
            dcf_score = 35.0
        elif dcf_downside_pct <= 25.0:
            dcf_score = 60.0
        else:
            dcf_score = 85.0
    else:
        dcf_downside_pct = 0.0
        dcf_score = 15.0

    valuation_score = round((stretch_score + dcf_score) / 2.0, 1)
    valuation_tier = get_risk_tier(valuation_score)
    valuation_assessment = (
        f"Current P/E of {current_pe if current_pe is not None else 'N/A'}x compares to {avg_pe if avg_pe is not None else 'N/A'}x historical avg "
        f"(stretch: {stretch_multiple}x). DCF downside risk is {dcf_downside_pct}% relative to intrinsic target of {currency} {dcf_intrinsic}."
    )

    pillar_valuation = ValuationStretchPillar(
        pillar_score=valuation_score,
        risk_level=valuation_tier,
        current_pe=current_pe,
        historical_avg_pe=avg_pe,
        pe_stretch_multiple=stretch_multiple,
        dcf_intrinsic_value=dcf_intrinsic,
        dcf_downside_pct=dcf_downside_pct,
        assessment=valuation_assessment
    )

    # =========================================================
    # Pillar 4: Earnings Quality
    # =========================================================
    fcf = float(latest_m.get("free_cash_flow") or 0.0)
    net_income = float(latest_m.get("net_income") or 0.0)

    if net_income > 0:
        fcf_to_ni = round(fcf / net_income, 2)
        is_warning = bool(fcf_to_ni < 0.70)
        if fcf_to_ni >= 1.0:
            eq_score = 10.0
        elif fcf_to_ni >= 0.85:
            eq_score = 25.0
        elif fcf_to_ni >= 0.70:
            eq_score = 45.0
        elif fcf_to_ni >= 0.50:
            eq_score = 75.0
        else:
            eq_score = 95.0
    else:
        fcf_to_ni = None
        is_warning = True
        eq_score = 80.0

    eq_tier = get_risk_tier(eq_score)
    eq_assessment = (
        f"Free cash flow to net income conversion ratio is {fcf_to_ni if fcf_to_ni is not None else 'N/A'} "
        f"({'WARNING: Cash conversion under 0.70' if is_warning else 'Healthy conversion above 0.70 threshold'})."
    )

    pillar_quality = EarningsQualityPillar(
        pillar_score=eq_score,
        risk_level=eq_tier,
        fcf_to_net_income=fcf_to_ni,
        is_conversion_warning=is_warning,
        free_cash_flow=fcf,
        net_income=net_income,
        assessment=eq_assessment
    )

    # =========================================================
    # Overall Score & Risk Level
    # =========================================================
    overall_score = round(
        0.25 * leverage_score +
        0.25 * stability_score +
        0.25 * valuation_score +
        0.25 * eq_score,
        1
    )
    overall_tier = get_risk_tier(overall_score)

    # =========================================================
    # 3 Grounded Gemini Watchpoints
    # =========================================================
    watchpoints = _generate_watchpoints(
        company=company,
        p1=pillar_leverage,
        p2=pillar_stability,
        p3=pillar_valuation,
        p4=pillar_quality,
        overall_score=overall_score,
        overall_tier=overall_tier
    )

    from datetime import datetime, timezone
    return RiskIntelligenceResponse(
        symbol=company.symbol or company.ticker or "UNKNOWN",
        company_name=company.company_name,
        currency=currency,
        overall_score=overall_score,
        risk_level=overall_tier,
        pillars={
            "leverage_liquidity": pillar_leverage.model_dump(),
            "profitability_stability": pillar_stability.model_dump(),
            "valuation_stretch": pillar_valuation.model_dump(),
            "earnings_quality": pillar_quality.model_dump()
        },
        watchpoints=watchpoints,
        generated_at=datetime.now(timezone.utc).isoformat()
    )


def _generate_watchpoints(
    company: Company,
    p1: LeverageLiquidityPillar,
    p2: ProfitabilityStabilityPillar,
    p3: ValuationStretchPillar,
    p4: EarningsQualityPillar,
    overall_score: float,
    overall_tier: str
) -> List[RiskWatchpoint]:
    """
    Calls Gemini 3.8 Flash to synthesize 3 institutional watchpoints.
    Falls back gracefully to deterministic rule-based watchpoints if Gemini is unavailable.
    """
    symbol = company.symbol or company.ticker or ""
    client = _get_genai_client()

    if client:
        try:
            prompt = (
                f"You are a Senior Risk Analyst at an institutional equity research fund.\n"
                f"Analyze the following deterministic risk metrics for {company.company_name} ({symbol}):\n\n"
                f"1. Leverage & Liquidity: Debt-to-Equity={p1.debt_to_equity}, Interest Coverage={p1.interest_coverage}x, Current Ratio={p1.current_ratio} (Pillar Score: {p1.pillar_score}/100, Tier: {p1.risk_level})\n"
                f"2. Profitability & Stability: OPM Std Dev={p2.opm_std_dev}%, YoY Revenue Growth={p2.latest_revenue_growth_pct}%, OPM Delta={p2.latest_opm_change_pp} pp (Pillar Score: {p2.pillar_score}/100, Tier: {p2.risk_level})\n"
                f"3. Valuation Stretch: Current P/E={p3.current_pe}x, Historical Avg P/E={p3.historical_avg_pe}x, Stretch={p3.pe_stretch_multiple}x, DCF Downside={p3.dcf_downside_pct}% (Pillar Score: {p3.pillar_score}/100, Tier: {p3.risk_level})\n"
                f"4. Earnings Quality: FCF/Net Income Conversion={p4.fcf_to_net_income}, Conversion Warning={p4.is_conversion_warning} (Pillar Score: {p4.pillar_score}/100, Tier: {p4.risk_level})\n"
                f"Overall Risk Score: {overall_score}/100 ({overall_tier})\n\n"
                f"Generate exactly 3 concise, grounded risk watchpoints for institutional investors.\n"
                f"Output each watchpoint on a separate line in the format:\n"
                f"CATEGORY | TITLE | DESCRIPTION | SEVERITY\n"
                f"Where SEVERITY must be one of: Low, Moderate, Elevated, High."
            )

            resp = client.models.generate_content(
                model="gemini-3.8-flash",
                contents=prompt
            )

            lines = [ln.strip() for ln in (resp.text or "").split("\n") if "|" in ln]
            parsed_wps: List[RiskWatchpoint] = []
            for ln in lines:
                parts = [p.strip() for p in ln.split("|")]
                if len(parts) >= 4:
                    cat, tit, desc, sev = parts[0], parts[1], parts[2], parts[3]
                    sev_clean = sev if sev in ["Low", "Moderate", "Elevated", "High"] else overall_tier
                    parsed_wps.append(RiskWatchpoint(
                        category=cat,
                        title=tit,
                        description=desc,
                        severity=sev_clean
                    ))
            if len(parsed_wps) == 3:
                return parsed_wps
        except Exception as e:
            logger.warning(f"Gemini risk watchpoints generation failed: {e}. Using deterministic fallback.")

    # Deterministic fallback watchpoints
    # 1. Valuation / DCF Watchpoint
    val_sev = p3.risk_level
    if p3.pe_stretch_multiple and p3.pe_stretch_multiple > 1.25:
        val_desc = f"Valuation is elevated at {p3.current_pe}x trailing P/E ({p3.pe_stretch_multiple}x historical average). DCF model indicates {p3.dcf_downside_pct}% downside to base fair value."
    elif p3.dcf_downside_pct > 15.0:
        val_desc = f"Trading at a premium to DCF intrinsic fair value with {p3.dcf_downside_pct}% downside sensitivity to terminal growth and WACC adjustments."
    else:
        val_desc = f"Trading at {p3.current_pe}x P/E with balanced valuation multiples relative to historical averages and DCF projections."

    # 2. Operating & Margin Watchpoint
    op_sev = p2.risk_level
    if p2.margin_contracting:
        op_desc = f"Operating profit margin compressed by {abs(p2.latest_opm_change_pp or 0.0)} pp in the latest period with an historical volatility (std dev) of {p2.opm_std_dev}%."
    elif p2.opm_std_dev > 4.0:
        op_desc = f"High margin variance observed across historical cycles (OPM std dev: {p2.opm_std_dev}%), requiring active tracking of raw material input inflation."
    else:
        op_desc = f"Operating margins demonstrate resilient stability with a tight standard deviation of {p2.opm_std_dev}% across the analyzed multi-year periods."

    # 3. Solvency & Earnings Quality Watchpoint
    eq_sev = "Elevated" if p4.is_conversion_warning else p1.risk_level
    if p4.is_conversion_warning:
        eq_desc = f"FCF conversion ratio of {p4.fcf_to_net_income or 0.0} trails the 0.70 institutional benchmark, signaling potential working capital drag or heightened capital intensity."
    elif p1.debt_to_equity and p1.debt_to_equity > 1.0:
        eq_desc = f"Debt-to-equity ratio of {p1.debt_to_equity} indicates significant financial leverage; monitor interest coverage ({p1.interest_coverage}x) against rate cycles."
    else:
        eq_desc = f"Robust balance sheet profile with Debt-to-Equity at {p1.debt_to_equity or 0.0} and cash conversion meeting institutional standards ({p4.fcf_to_net_income or 1.0}x FCF/NI)."

    return [
        RiskWatchpoint(
            category="Valuation & DCF",
            title="Multiple Stretch & Fair Value Premium",
            description=val_desc,
            severity=val_sev
        ),
        RiskWatchpoint(
            category="Profitability & Margins",
            title="Operating Margin Trajectory & Volatility",
            description=op_desc,
            severity=op_sev
        ),
        RiskWatchpoint(
            category="Solvency & Earnings Quality",
            title="Cash Flow Conversion & Capital Structure",
            description=eq_desc,
            severity=eq_sev
        )
    ]
