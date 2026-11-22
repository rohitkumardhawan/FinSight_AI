"""
FinSight AI — Deterministic Automated Financial Insights Engine
==============================================================
Calculates pure-Python deterministic financial analytics, growth rates,
CAGRs, margins, valuation multiples, and scenario upside/downside models
without relying on non-deterministic black-box LLMs.
"""

from typing import List, Dict, Any, Optional
import math
from app.schemas.dataset import ParsedCompanyDataset, FinancialPeriodRecord


def calculate_cagr(start_val: Optional[float], end_val: Optional[float], years: int) -> Optional[float]:
    """CAGR = (End / Start) ** (1 / years) - 1. Returns percentage rounded to 2 decimals."""
    if start_val is None or end_val is None or start_val <= 0 or end_val <= 0 or years <= 0:
        return None
    try:
        cagr = ((end_val / start_val) ** (1.0 / years) - 1.0) * 100.0
        return round(cagr, 2)
    except (ValueError, ZeroDivisionError, OverflowError):
        return None


def format_currency_value(value: Optional[float], currency: str = "USD") -> str:
    """Formats financial numbers strictly by currency (₹ Cr for INR, $B/$M for USD)."""
    if value is None:
        return "N/A"
    cur = (currency or "").upper()
    if cur in ("INR", "₹"):
        in_cr = value / 1e7
        return f"₹{in_cr:,.2f} Cr"
    sym = "$" if cur in ("USD", "$", "") else f"{cur} "
    abs_val = abs(value)
    if abs_val >= 1e9:
        return f"{sym}{value / 1e9:,.2f}B"
    elif abs_val >= 1e6:
        return f"{sym}{value / 1e6:,.2f}M"
    else:
        return f"{sym}{value:,.2f}"


def format_per_share(value: Optional[float], currency: str = "USD") -> str:
    """Formats per-share price or EPS with currency symbol."""
    if value is None:
        return "N/A"
    cur = (currency or "").upper()
    sym = "₹" if cur in ("INR", "₹") else "$"
    return f"{sym}{value:,.2f}"


def generate_auto_insights(dataset: ParsedCompanyDataset) -> Dict[str, Any]:
    """
    Generates a structured analytical payload from parsed financial records:
    1. KPI cards for dashboard summary strip
    2. Time-series chart arrays (Revenue, Net Profit, OPM %, Margins)
    3. Multi-year ratios table
    4. Trends matrix (10Y, 7Y, 5Y, 3Y, Recent)
    5. Scenario valuation modeling (Trailing vs Best Case vs Worst Case)
    6. Grounded deterministic narrative summary
    """
    # Separate annual periods (FY) from quarterly and special periods (TTM, Best Case, Worst Case)
    annual_periods = [
        p for p in dataset.periods
        if p.fiscal_year is not None
        and getattr(p, "statement_type", "") != "quarterly"
        and (not p.fiscal_period or p.fiscal_period.startswith("FY"))
    ]
    annual_periods.sort(key=lambda p: p.fiscal_year or 0)

    special_periods = {p.fiscal_period: p for p in dataset.periods if p.fiscal_year is None}

    # 1. Calculate YoY Growth and Margins across Annual Periods
    time_series_data = []
    ratio_rows = []

    for idx, p in enumerate(annual_periods):
        prev = annual_periods[idx - 1] if idx > 0 else None
        
        # YoY Revenue Growth %
        rev_growth = None
        if prev and prev.revenue and p.revenue and prev.revenue > 0:
            rev_growth = round(((p.revenue - prev.revenue) / prev.revenue) * 100, 2)

        # YoY Net Income Growth %
        net_inc_growth = None
        if prev and prev.net_income and p.net_income and prev.net_income != 0:
            net_inc_growth = round(((p.net_income - prev.net_income) / abs(prev.net_income)) * 100, 2)

        # Margins
        opm = p.opm_pct
        if opm is None and p.revenue and p.operating_income and p.revenue > 0:
            opm = round((p.operating_income / p.revenue) * 100, 2)

        net_margin = None
        if p.revenue and p.net_income and p.revenue > 0:
            net_margin = round((p.net_income / p.revenue) * 100, 2)

        gross_margin = None
        if p.revenue and p.revenue > 0:
            if p.gross_profit is not None:
                gross_margin = round((p.gross_profit / p.revenue) * 100, 2)
            elif p.cost_of_revenue is not None:
                gross_margin = round(((p.revenue - p.cost_of_revenue) / p.revenue) * 100, 2)

        fcf_margin = None
        if p.revenue and p.free_cash_flow is not None and p.revenue > 0:
            fcf_margin = round((p.free_cash_flow / p.revenue) * 100, 2)

        # Balance Sheet Ratios
        current_ratio = None
        if p.current_assets and p.current_liabilities and p.current_liabilities > 0:
            current_ratio = round(p.current_assets / p.current_liabilities, 2)

        debt_to_equity = None
        if p.total_debt is not None and p.total_equity and p.total_equity > 0:
            debt_to_equity = round(p.total_debt / p.total_equity, 2)

        roe = None
        if p.net_income and p.total_equity and p.total_equity > 0:
            roe = round((p.net_income / p.total_equity) * 100, 2)

        label = f"FY{str(p.fiscal_year)[-2:]}"
        time_series_data.append({
            "period": label,
            "fiscal_year": p.fiscal_year,
            "fiscal_period": p.fiscal_period,
            "revenue": p.revenue,
            "operating_income": p.operating_income,
            "net_income": p.net_income,
            "opm_pct": opm,
            "net_margin_pct": net_margin,
            "gross_margin_pct": gross_margin,
            "fcf": p.free_cash_flow,
            "fcf_margin_pct": fcf_margin,
            "rev_growth_pct": rev_growth,
            "net_growth_pct": net_inc_growth,
            "eps": p.eps,
            "pe_ratio": p.pe_ratio,
            "share_price": p.share_price,
            "total_assets": p.total_assets,
            "total_equity": p.total_equity,
            "total_debt": p.total_debt,
            "current_ratio": current_ratio,
            "debt_to_equity": debt_to_equity,
            "roe_pct": roe,
        })

    # 2. Derive Multi-Year CAGRs if not already provided in Screener TRENDS
    trends = dataset.trends
    if not trends and len(annual_periods) >= 3:
        latest = annual_periods[-1]
        cagr_map: Dict[str, Dict[str, Optional[float]]] = {
            "sales_growth": {},
            "net_profit_growth": {},
        }
        periods_config = [("3 YEARS", 3), ("5 YEARS", 5), ("7 YEARS", 7), ("10 YEARS", 10)]
        for label, span in periods_config:
            if len(annual_periods) > span:
                base_p = annual_periods[-(span + 1)]
                cagr_map["sales_growth"][label] = calculate_cagr(base_p.revenue, latest.revenue, span)
                cagr_map["net_profit_growth"][label] = calculate_cagr(base_p.net_income, latest.net_income, span)
        trends = {
            "headers": [label for label, span in periods_config if len(annual_periods) > span],
            "metrics": cagr_map
        }

    # 3. Scenario Valuation Analysis (Trailing vs Best Case vs Worst Case)
    scenarios = dataset.scenarios or {}
    scenario_insights = None
    trailing = special_periods.get("TTM") or (annual_periods[-1] if annual_periods else None)
    best_case = special_periods.get("Best Case")
    worst_case = special_periods.get("Worst Case")

    if trailing and (best_case or worst_case):
        trailing_price = trailing.share_price
        best_price = best_case.share_price if best_case else None
        worst_price = worst_case.share_price if worst_case else None

        upside_best = None
        if trailing_price and best_price and trailing_price > 0:
            upside_best = round(((best_price - trailing_price) / trailing_price) * 100, 2)

        downside_worst = None
        if trailing_price and worst_price and trailing_price > 0:
            downside_worst = round(((worst_price - trailing_price) / trailing_price) * 100, 2)

        # Historical P/E benchmark
        historical_pes = [p.pe_ratio for p in annual_periods if p.pe_ratio is not None and p.pe_ratio > 0]
        avg_pe = round(sum(historical_pes) / len(historical_pes), 2) if historical_pes else None
        median_pe = None
        if historical_pes:
            sorted_pe = sorted(historical_pes)
            mid = len(sorted_pe) // 2
            median_pe = round(sorted_pe[mid] if len(sorted_pe) % 2 != 0 else (sorted_pe[mid - 1] + sorted_pe[mid]) / 2, 2)

        scenario_insights = {
            "trailing_price": trailing_price,
            "best_case_price": best_price,
            "worst_case_price": worst_price,
            "upside_best_pct": upside_best,
            "downside_worst_pct": downside_worst,
            "trailing_pe": trailing.pe_ratio,
            "historical_avg_pe": avg_pe,
            "historical_median_pe": median_pe,
            "trailing_revenue": trailing.revenue,
            "best_case_revenue": best_case.revenue if best_case else None,
            "worst_case_revenue": worst_case.revenue if worst_case else None,
        }
    elif trailing and (trailing.share_price or trailing.pe_ratio):
        # Deterministic 1-year forward Base / Best / Worst scenarios for auto-fetched equities
        trailing_price = trailing.share_price or 100.0
        current_eps = trailing.eps or (round(trailing_price / trailing.pe_ratio, 2) if trailing.pe_ratio and trailing.pe_ratio > 0 else 5.0)
        historical_pes = [p.pe_ratio for p in annual_periods if p.pe_ratio is not None and p.pe_ratio > 0]
        avg_pe = round(sum(historical_pes) / len(historical_pes), 2) if historical_pes else (trailing.pe_ratio or 22.0)
        median_pe = avg_pe

        # Growth distribution
        growth_rates = [m["net_growth_pct"] for m in time_series_data if m.get("net_growth_pct") is not None]
        base_growth = (sorted(growth_rates)[len(growth_rates)//2] / 100.0) if growth_rates else 0.12
        base_growth = max(min(base_growth, 0.35), -0.15)

        base_eps = round(current_eps * (1.0 + base_growth), 2)
        best_eps = round(current_eps * (1.0 + max(base_growth * 1.5, base_growth + 0.08)), 2)
        worst_eps = round(current_eps * (1.0 + min(base_growth * 0.4, base_growth - 0.06)), 2)

        best_pe = round(avg_pe * 1.15, 2)
        worst_pe = round(avg_pe * 0.85, 2)

        base_price = round(base_eps * avg_pe, 2)
        best_price = round(best_eps * best_pe, 2)
        worst_price = round(worst_eps * worst_pe, 2)

        upside_best = round(((best_price - trailing_price) / trailing_price) * 100, 2) if trailing_price else None
        downside_worst = round(((worst_price - trailing_price) / trailing_price) * 100, 2) if trailing_price else None

        scenario_insights = {
            "trailing_price": trailing_price,
            "base_case_price": base_price,
            "best_case_price": best_price,
            "worst_case_price": worst_price,
            "upside_best_pct": upside_best,
            "downside_worst_pct": downside_worst,
            "trailing_pe": trailing.pe_ratio or round(trailing_price / current_eps, 2),
            "historical_avg_pe": avg_pe,
            "historical_median_pe": median_pe,
            "trailing_revenue": trailing.revenue,
            "best_case_revenue": round(trailing.revenue * 1.18, 2) if trailing.revenue else None,
            "worst_case_revenue": round(trailing.revenue * 0.94, 2) if trailing.revenue else None,
            "is_synthesized": True
        }

    # 4. Generate Institutional KPI Cards
    latest_period = annual_periods[-1] if annual_periods else None
    kpi_cards = []

    # Currency determination
    currency = (dataset.raw_metadata or {}).get("currency")
    if not currency:
        comp_name = (dataset.company_name or "").upper()
        file_name = (dataset.filename or "").upper()
        if (
            comp_name.endswith(".NS")
            or comp_name.endswith(".BO")
            or file_name.endswith(".NS")
            or file_name.endswith(".BO")
            or "PAINTS" in comp_name
            or "RELIANCE" in comp_name
            or "TCS" in comp_name
            or "INFOSYS" in comp_name
            or "HDFC" in comp_name
        ):
            currency = "INR"
        else:
            currency = "USD"

    if latest_period:
        # KPI 1: Revenue
        rev_val = format_currency_value(latest_period.revenue, currency)
        growth_str = ""
        is_pos = True
        if len(time_series_data) >= 2 and time_series_data[-1].get("rev_growth_pct") is not None:
            g = time_series_data[-1]["rev_growth_pct"]
            growth_str = f"{'+' if g >= 0 else ''}{g}% YoY"
            is_pos = g >= 0

        kpi_cards.append({
            "label": "Annual Revenue",
            "value": rev_val,
            "raw_value": latest_period.revenue,
            "change": growth_str,
            "is_positive": is_pos,
            "subtext": f"Latest Period ({time_series_data[-1]['period'] if time_series_data else 'Latest'})"
        })

        # KPI 2: Operating Profit & OPM
        op_val = format_currency_value(latest_period.operating_income, currency)
        opm_val = time_series_data[-1].get("opm_pct")
        kpi_cards.append({
            "label": "Operating Profit (EBIT)",
            "value": op_val,
            "raw_value": latest_period.operating_income,
            "change": f"{opm_val}% OPM" if opm_val is not None else None,
            "is_positive": True,
            "subtext": "Core Operational Earning Power"
        })

        # KPI 3: Net Profit
        net_val = format_currency_value(latest_period.net_income, currency)
        net_m = time_series_data[-1].get("net_margin_pct")
        kpi_cards.append({
            "label": "Net Profit",
            "value": net_val,
            "raw_value": latest_period.net_income,
            "change": f"{net_m}% Margin" if net_m is not None else None,
            "is_positive": (latest_period.net_income or 0) >= 0,
            "subtext": "Bottom-Line GAAP Earnings"
        })

        # KPI 4: Valuation or Capital Return (P/E or ROE / FCF)
        if latest_period.pe_ratio is not None:
            eps_str = f"EPS: {format_per_share(latest_period.eps, currency)}" if latest_period.eps is not None else None
            kpi_cards.append({
                "label": "Price-to-Earnings (P/E)",
                "value": f"{latest_period.pe_ratio:.1f}x",
                "raw_value": latest_period.pe_ratio,
                "change": eps_str,
                "is_positive": True,
                "subtext": "Institutional Valuation Multiple"
            })
        elif latest_period.free_cash_flow is not None:
            kpi_cards.append({
                "label": "Free Cash Flow (FCF)",
                "value": format_currency_value(latest_period.free_cash_flow, currency),
                "raw_value": latest_period.free_cash_flow,
                "change": f"{time_series_data[-1].get('fcf_margin_pct')}% FCF Margin" if time_series_data else None,
                "is_positive": latest_period.free_cash_flow >= 0,
                "subtext": "Operating Cash Flow - CapEx"
            })
        elif latest_period.total_equity is not None and time_series_data[-1].get("roe_pct") is not None:
            kpi_cards.append({
                "label": "Return on Equity (ROE)",
                "value": f"{time_series_data[-1]['roe_pct']:.1f}%",
                "raw_value": time_series_data[-1]['roe_pct'],
                "change": f"Equity: {format_currency_value(latest_period.total_equity, currency)}",
                "is_positive": True,
                "subtext": "Shareholder Equity Return"
            })

    # 5. Deterministic Summary Narrative
    narrative_paragraphs = []
    if annual_periods:
        first_p = annual_periods[0]
        last_p = annual_periods[-1]
        years_span = (last_p.fiscal_year or 0) - (first_p.fiscal_year or 0)
        cagr_span = calculate_cagr(first_p.revenue, last_p.revenue, years_span) if years_span > 0 else None

        if last_p.revenue is not None and first_p.revenue is not None:
            rev_overview = (
                f"{dataset.company_name} reported revenue of {format_currency_value(last_p.revenue, currency)} in {last_p.fiscal_year}, "
                f"compared to {format_currency_value(first_p.revenue, currency)} in {first_p.fiscal_year}"
            )
            if cagr_span is not None:
                rev_overview += f", compounding at a {years_span}-year CAGR of {cagr_span}%."
            else:
                rev_overview += "."
            narrative_paragraphs.append(rev_overview)
        elif last_p.revenue is not None:
            narrative_paragraphs.append(
                f"{dataset.company_name} reported revenue of {format_currency_value(last_p.revenue, currency)} in {last_p.fiscal_year}."
            )

        latest_opm = time_series_data[-1].get("opm_pct") if time_series_data else None
        latest_net_m = time_series_data[-1].get("net_margin_pct") if time_series_data else None
        if latest_opm is not None:
            margin_text = f"Operating profit margin (OPM) stands at {latest_opm}%"
            if latest_net_m is not None:
                margin_text += f" with a net margin of {latest_net_m}%."
            else:
                margin_text += "."
            narrative_paragraphs.append(margin_text)

    if scenario_insights:
        trailing_px = scenario_insights.get("trailing_price") or 0.0
        trailing_pe_val = scenario_insights.get("trailing_pe") or "N/A"
        best_px = scenario_insights.get("best_case_price") or 0.0
        upside = scenario_insights.get("upside_best_pct") or 0.0
        worst_px = scenario_insights.get("worst_case_price") or 0.0
        downside = scenario_insights.get("downside_worst_pct") or 0.0
        scen_text = (
            f"Valuation Scenario Model: Trailing price is {format_per_share(trailing_px, currency)} "
            f"(P/E: {trailing_pe_val}x). "
            f"Best Case target is {format_per_share(best_px, currency)} ({upside:+}% implied upside), "
            f"while Worst Case floor is {format_per_share(worst_px, currency)} ({downside:+}% implied downside)."
        )
        narrative_paragraphs.append(scen_text)

    return {
        "currency": currency,
        "kpis": kpi_cards,
        "kpi_cards": kpi_cards,
        "time_series": time_series_data,
        "charts": {
            "revenue_profit": [
                {"period": d["period"], "revenue": d["revenue"], "net_income": d["net_income"], "operating_income": d["operating_income"]}
                for d in time_series_data
            ],
            "opm_trend": [
                {"period": d["period"], "opm_pct": d["opm_pct"]}
                for d in time_series_data if d.get("opm_pct") is not None
            ]
        },
        "trends": trends,
        "scenarios": scenario_insights,
        "scenario_insights": scenario_insights,
        "summary_narrative": " ".join(narrative_paragraphs)
    }
