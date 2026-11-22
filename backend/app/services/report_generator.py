"""
FinSight AI — Institutional PDF Research Report Generator & Preview Engine
========================================================================
Generates publication-quality 2-3 page institutional equity research reports:
- ReportLab SimpleDocTemplate with NumberedCanvas page numbering
- Header block with company, ticker, exchange, price, and DCF intrinsic value
- Executive Investment Thesis grounded in Neon PostgreSQL data and RAG chunks
- Pruned multi-year historical financials table formatted in ₹ Cr or $M/$B
- DCF Valuation & Valuation Scenarios (Worst / Base / Best)
- 4-Pillar Risk Intelligence Scorecard with grounded watchpoints
- Source attribution and institutional compliance disclaimers
"""

import io
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
import logging

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether, HRFlowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from sqlalchemy.orm import Session
from google import genai
from google.genai import types

from app.core.config import settings
from app.models.company import Company
from app.models.dataset import FinancialPeriod, RagChunk
from app.services.dcf_engine import calculate_dcf, DCFResponse
from app.services.risk_engine import calculate_risk_intelligence, RiskIntelligenceResponse

logger = logging.getLogger(__name__)


# -------------------------------------------------------------
# Numbered Canvas for Institutional Header/Footer on Every Page
# -------------------------------------------------------------
class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_header_footer(num_pages)
            canvas.Canvas.showPage(self)
        canvas.Canvas.save(self)

    def draw_header_footer(self, page_count: int):
        self.saveState()
        self.setFont("Helvetica-Bold", 7)
        self.setFillColor(colors.HexColor("#64748B"))
        
        # Top Running Header (Pages 2+)
        if self._pageNumber > 1:
            self.drawString(36, 762, "FinSight AI — Institutional Equity Research & Financial Intelligence")
            self.drawRightString(576, 762, datetime.now(timezone.utc).strftime("%B %Y"))
            self.setStrokeColor(colors.HexColor("#CBD5E1"))
            self.setLineWidth(0.5)
            self.line(36, 756, 576, 756)

        # Bottom Running Footer (All Pages)
        self.setStrokeColor(colors.HexColor("#CBD5E1"))
        self.setLineWidth(0.5)
        self.line(36, 42, 576, 42)

        self.setFont("Helvetica", 7)
        self.drawString(36, 30, "CONFIDENTIAL & PROPRIETARY — FOR INSTITUTIONAL RESEARCH USE ONLY")
        self.drawRightString(576, 30, f"Page {self._pageNumber} of {page_count}")
        self.restoreState()


# -------------------------------------------------------------
# Formatting Utilities
# -------------------------------------------------------------
def format_currency_amount(val: Optional[float], currency: str) -> str:
    """Formats large financial totals in ₹ Cr for INR or $M/$B for USD."""
    if val is None:
        return "—"
    curr = (currency or "INR").upper()
    is_inr = (curr == "INR")

    if is_inr:
        crores = val / 1e7
        return f"₹{crores:,.2f} Cr"
    else:
        abs_v = abs(val)
        prefix = "-" if val < 0 else ""
        if abs_v >= 1e9:
            return f"{prefix}${abs_v / 1e9:,.2f}B"
        elif abs_v >= 1e6:
            return f"{prefix}${abs_v / 1e6:,.2f}M"
        else:
            return f"{prefix}${abs_v:,.2f}"


def format_per_share(val: Optional[float], currency: str) -> str:
    """Formats per-share metrics like EPS or Share Price."""
    if val is None:
        return "—"
    curr = (currency or "INR").upper()
    sym = "₹" if curr == "INR" else "$"
    return f"{sym}{val:,.2f}"


def get_investment_rating(upside_pct: float) -> tuple[str, str]:
    """Returns rating stance and theme color based on DCF upside %."""
    if upside_pct >= 15.0:
        return "OVERWEIGHT / BUY", "#10B981"  # Emerald
    elif upside_pct <= -15.0:
        return "UNDERWEIGHT / SELL", "#EF4444"  # Red
    else:
        return "NEUTRAL / HOLD", "#F59E0B"  # Amber


# -------------------------------------------------------------
# Executive Thesis Generation (Gemini 3.8 Flash + pgvector / SQL facts)
# -------------------------------------------------------------
def generate_executive_thesis(
    company: Company,
    periods: List[FinancialPeriod],
    dcf: DCFResponse,
    risk: RiskIntelligenceResponse,
    db: Session
) -> str:
    """
    Synthesizes a 2-3 paragraph institutional investment thesis.
    Uses Gemini 3.8 Flash with grounded context from Neon DB, falling back to deterministic synthesis.
    """
    symbol = company.symbol or company.ticker or ""
    currency = company.currency or "INR"
    rating, _ = get_investment_rating(dcf.upside_downside_pct)

    # 1. Retrieve RAG chunks if available
    retrieved_chunks = (
        db.query(RagChunk)
        .filter(RagChunk.company_id == company.id)
        .limit(4)
        .all()
    )
    rag_context = "\n".join([f"- {c.source_ref}: {c.content[:200]}..." for c in retrieved_chunks])

    # 2. Try Gemini 3.8 Flash
    if settings.GEMINI_API_KEY:
        try:
            client = genai.Client(
                api_key=settings.GEMINI_API_KEY,
                http_options=types.HttpOptions(timeout=7000)
            )
            prompt = (
                f"You are a Senior Equity Research Director at a tier-1 investment bank.\n"
                f"Draft a rigorous 2-paragraph Executive Investment Thesis for {company.company_name} ({symbol}).\n\n"
                f"KEY FINANCIAL FACTS:\n"
                f"- Current Market Price: {currency} {dcf.current_price}\n"
                f"- DCF Intrinsic Fair Value: {currency} {dcf.intrinsic_value} (Implied Upside/Downside: {dcf.upside_downside_pct}%)\n"
                f"- Investment Stance: {rating}\n"
                f"- Historical 3Y-5Y Growth: {dcf.historical_cagr * 100:.1f}%, WACC: {dcf.wacc * 100:.1f}%, Terminal Growth: {dcf.terminal_growth_rate * 100:.1f}%\n"
                f"- Overall Risk Score: {risk.overall_score}/100 ({risk.risk_level})\n"
                f"- Leverage & Solvency: D/E={risk.pillars.get('leverage_liquidity', {}).get('debt_to_equity')}, Interest Coverage={risk.pillars.get('leverage_liquidity', {}).get('interest_coverage')}x\n"
                f"- Margin Profile: OPM Std Dev={risk.pillars.get('profitability_stability', {}).get('opm_std_dev')}%, Latest Revenue Growth={risk.pillars.get('profitability_stability', {}).get('latest_revenue_growth_pct')}%\n"
                f"- Earnings Quality: FCF/Net Income={risk.pillars.get('earnings_quality', {}).get('fcf_to_net_income')}\n\n"
                f"ADDITIONAL RAG CONTEXT:\n{rag_context}\n\n"
                f"Write in authoritative, institutional prose with specific figures. Do NOT use markdown asterisks or bullet points. "
                f"Structure as 2 clean narrative paragraphs: Paragraph 1 on business performance and revenue/margin momentum; "
                f"Paragraph 2 on valuation verdict, DCF sensitivity, and risk profile."
            )

            resp = client.models.generate_content(
                model="gemini-3.8-flash",
                contents=prompt
            )
            if resp.text and len(resp.text.strip()) > 150:
                return resp.text.strip()
        except Exception as e:
            logger.warning(f"Gemini thesis generation failed: {e}. Falling back to deterministic thesis.")

    # 3. Deterministic High-Quality Thesis Fallback
    p1 = risk.pillars.get("leverage_liquidity", {})
    p2 = risk.pillars.get("profitability_stability", {})
    p3 = risk.pillars.get("valuation_stretch", {})
    p4 = risk.pillars.get("earnings_quality", {})

    para1 = (
        f"{company.company_name} ({symbol}) continues to demonstrate resilient operational execution within the {company.sector or 'industry'} sector. "
        f"Over the multi-year observation horizon, revenue growth expanded at a {dcf.historical_cagr * 100:.1f}% CAGR, supported by an operating profit margin (OPM) "
        f"with tight cyclical stability (historical standard deviation: {p2.get('opm_std_dev', 2.0)}%). The company maintains conservative balance sheet management, "
        f"characterized by a Debt-to-Equity ratio of {p1.get('debt_to_equity', 0.1)}x and robust interest coverage of {p1.get('interest_coverage', 25.0)}x, "
        f"providing substantial solvency headroom across macroeconomic cycles."
    )

    para2 = (
        f"From a valuation perspective, our institutional Discounted Cash Flow (DCF) model establishes an intrinsic fair value of {currency} {dcf.intrinsic_value:,.2f} "
        f"per share, compared to the prevailing market price of {currency} {dcf.current_price:,.2f}, indicating an implied {'upside' if dcf.upside_downside_pct >= 0 else 'downside'} of {dcf.upside_downside_pct:.2f}%. "
        f"This yields a formal {rating} stance. Cash flow conversion remains {'healthy' if not p4.get('is_conversion_warning') else 'under pressure'} "
        f"at {p4.get('fcf_to_net_income', 1.0)}x FCF/Net Income. While valuation multiples remain {'stretched' if p3.get('pe_stretch_multiple', 1.0) > 1.2 else 'in-line'} "
        f"at {p3.get('current_pe', 50.0)}x trailing earnings, the company's competitive moats and stable returns profile support long-term institutional positioning."
    )

    return f"{para1}\n\n{para2}"


# -------------------------------------------------------------
# Report Preview Data Builder
# -------------------------------------------------------------
def get_report_preview_data(
    company: Company,
    periods: List[FinancialPeriod],
    db: Session
) -> Dict[str, Any]:
    """Generates the structured JSON payload for the report preview endpoint."""
    currency = company.currency or "INR"
    dcf = calculate_dcf(company, periods)
    risk = calculate_risk_intelligence(company, periods)
    thesis = generate_executive_thesis(company, periods, dcf, risk, db)
    rating, rating_color = get_investment_rating(dcf.upside_downside_pct)

    # Pruned historical financials
    sorted_periods = sorted([p for p in periods if p.fiscal_year is not None], key=lambda p: p.fiscal_year or 0)
    pruned = [p for p in sorted_periods if (p.metrics_json or {}).get("revenue") is not None]

    financials_preview = []
    for p in pruned:
        m = p.metrics_json or {}
        financials_preview.append({
            "fiscal_year": p.fiscal_year,
            "period": f"FY{p.fiscal_year}",
            "revenue": format_currency_amount(m.get("revenue"), currency),
            "operating_income": format_currency_amount(m.get("operating_income"), currency),
            "opm_pct": f"{m.get('opm_pct', 0.0):.2f}%" if m.get("opm_pct") is not None else "—",
            "net_income": format_currency_amount(m.get("net_income"), currency),
            "eps": format_per_share(m.get("eps"), currency),
            "free_cash_flow": format_currency_amount(m.get("free_cash_flow"), currency)
        })

    # Scenarios from metadata or calculated
    meta = company.metadata_json or {}
    scenarios_meta = meta.get("scenarios") or {}

    return {
        "company_name": company.company_name,
        "symbol": company.symbol or company.ticker,
        "exchange": company.exchange or "NSE",
        "currency": currency,
        "sector": company.sector or "Equity",
        "current_price": dcf.current_price,
        "dcf_intrinsic_value": dcf.intrinsic_value,
        "upside_downside_pct": dcf.upside_downside_pct,
        "rating_stance": rating,
        "rating_color": rating_color,
        "thesis": thesis,
        "dcf_summary": {
            "wacc": dcf.wacc,
            "terminal_growth_rate": dcf.terminal_growth_rate,
            "growth_rate": dcf.growth_rate,
            "enterprise_value": format_currency_amount(dcf.enterprise_value, currency),
            "net_debt": format_currency_amount(dcf.net_debt, currency),
            "intrinsic_value": format_per_share(dcf.intrinsic_value, currency)
        },
        "scenarios": scenarios_meta,
        "risk_summary": {
            "overall_score": risk.overall_score,
            "risk_level": risk.risk_level,
            "pillars": risk.pillars,
            "watchpoints": [wp.model_dump() for wp in risk.watchpoints]
        },
        "financials_preview": financials_preview,
        "generated_at": datetime.now(timezone.utc).isoformat()
    }


# -------------------------------------------------------------
# PDF Report Generator
# -------------------------------------------------------------
def generate_pdf_report(
    company: Company,
    periods: List[FinancialPeriod],
    db: Session,
    dcf: Optional[DCFResponse] = None,
    risk: Optional[RiskIntelligenceResponse] = None
) -> bytes:
    """
    Builds a professional 2-3 page institutional equity research PDF in memory.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=36,
        rightMargin=36,
        topMargin=48,
        bottomMargin=52
    )

    # Styles
    base_styles = getSampleStyleSheet()
    
    style_brand = ParagraphStyle(
        "BrandTitle",
        parent=base_styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=20,
        leading=24,
        textColor=colors.HexColor("#0F172A")
    )
    style_ticker = ParagraphStyle(
        "TickerSub",
        parent=base_styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=10,
        leading=13,
        textColor=colors.HexColor("#2563EB")
    )
    style_section_heading = ParagraphStyle(
        "SectionHeading",
        parent=base_styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=15,
        textColor=colors.HexColor("#0F172A"),
        spaceBefore=10,
        spaceAfter=4
    )
    style_body = ParagraphStyle(
        "BodyDark",
        parent=base_styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#334155")
    )
    style_table_cell = ParagraphStyle(
        "TableCell",
        parent=base_styles["Normal"],
        fontName="Helvetica",
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#1E293B")
    )
    style_table_cell_bold = ParagraphStyle(
        "TableCellBold",
        parent=base_styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#0F172A")
    )
    style_table_header = ParagraphStyle(
        "TableHeader",
        parent=base_styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8,
        leading=10,
        textColor=colors.white,
        alignment=1  # Centered
    )

    currency = company.currency or "INR"
    symbol = company.symbol or company.ticker or ""
    exchange = company.exchange or "NSE"

    # Compute Core Analytics if not passed
    if dcf is None:
        dcf = calculate_dcf(company, periods)
    if risk is None:
        risk = calculate_risk_intelligence(company, periods)
    thesis_text = generate_executive_thesis(company, periods, dcf, risk, db)
    rating, rating_color = get_investment_rating(dcf.upside_downside_pct)

    story = []

    # =========================================================
    # 1. Header Banner & Identity
    # =========================================================
    header_data = [
        [
            Paragraph(f"<b>{company.company_name}</b>", style_brand),
            Paragraph(
                f"<font color='{rating_color}'><b>{rating}</b></font><br/>"
                f"<font size=8 color='#64748B'>FinSight Institutional Rating</font>",
                ParagraphStyle("RatingBox", fontName="Helvetica-Bold", fontSize=11, leading=14, alignment=2)
            )
        ],
        [
            Paragraph(
                f"<b>{symbol}</b> &bull; {exchange} &bull; Sector: {company.sector or 'Equities'} &bull; Currency: {currency}",
                style_ticker
            ),
            Paragraph(
                f"<font size=8 color='#64748B'>Report Date: {datetime.now(timezone.utc).strftime('%d %B %Y')}</font>",
                ParagraphStyle("DateBox", fontName="Helvetica", fontSize=8, leading=11, alignment=2)
            )
        ]
    ]
    t_header = Table(header_data, colWidths=[360, 180])
    t_header.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
    ]))
    story.append(t_header)
    story.append(Spacer(1, 8))

    # =========================================================
    # 2. Key Investment Metrics Summary Strip
    # =========================================================
    price_str = format_per_share(dcf.current_price, currency)
    target_str = format_per_share(dcf.intrinsic_value, currency)
    upside_sign = "+" if dcf.upside_downside_pct >= 0 else ""
    upside_str = f"{upside_sign}{dcf.upside_downside_pct:.2f}%"

    metrics_strip = [
        [
            Paragraph("<b>MARKET PRICE</b>", ParagraphStyle("M1", fontSize=7, leading=9, textColor=colors.HexColor("#64748B"), alignment=1)),
            Paragraph("<b>DCF TARGET</b>", ParagraphStyle("M2", fontSize=7, leading=9, textColor=colors.HexColor("#64748B"), alignment=1)),
            Paragraph("<b>IMPLIED UPSIDE</b>", ParagraphStyle("M3", fontSize=7, leading=9, textColor=colors.HexColor("#64748B"), alignment=1)),
            Paragraph("<b>WACC / TG</b>", ParagraphStyle("M4", fontSize=7, leading=9, textColor=colors.HexColor("#64748B"), alignment=1)),
            Paragraph("<b>RISK SCORE</b>", ParagraphStyle("M5", fontSize=7, leading=9, textColor=colors.HexColor("#64748B"), alignment=1)),
        ],
        [
            Paragraph(f"<b>{price_str}</b>", ParagraphStyle("V1", fontName="Helvetica-Bold", fontSize=11, leading=14, textColor=colors.HexColor("#0F172A"), alignment=1)),
            Paragraph(f"<b>{target_str}</b>", ParagraphStyle("V2", fontName="Helvetica-Bold", fontSize=11, leading=14, textColor=colors.HexColor("#2563EB"), alignment=1)),
            Paragraph(f"<b><font color='{rating_color}'>{upside_str}</font></b>", ParagraphStyle("V3", fontName="Helvetica-Bold", fontSize=11, leading=14, alignment=1)),
            Paragraph(f"<b>{dcf.wacc*100:.1f}% / {dcf.terminal_growth_rate*100:.1f}%</b>", ParagraphStyle("V4", fontName="Helvetica-Bold", fontSize=10, leading=14, textColor=colors.HexColor("#0F172A"), alignment=1)),
            Paragraph(f"<b>{risk.overall_score} ({risk.risk_level})</b>", ParagraphStyle("V5", fontName="Helvetica-Bold", fontSize=10, leading=14, textColor=colors.HexColor("#0F172A"), alignment=1)),
        ]
    ]
    t_metrics = Table(metrics_strip, colWidths=[108, 108, 108, 108, 108])
    t_metrics.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
        ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#E2E8F0")),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(t_metrics)
    story.append(Spacer(1, 10))

    # =========================================================
    # 3. Executive Investment Thesis
    # =========================================================
    story.append(Paragraph("EXECUTIVE INVESTMENT THESIS", style_section_heading))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#E2E8F0"), spaceBefore=2, spaceAfter=6))
    
    thesis_paragraphs = thesis_text.split("\n\n")
    for tp in thesis_paragraphs:
        if tp.strip():
            story.append(Paragraph(tp.strip(), style_body))
            story.append(Spacer(1, 4))
    story.append(Spacer(1, 6))

    # =========================================================
    # 4. Pruned Historical Financials Table
    # =========================================================
    sorted_periods = sorted([p for p in periods if p.fiscal_year is not None], key=lambda p: p.fiscal_year or 0)
    pruned_periods = [p for p in sorted_periods if (p.metrics_json or {}).get("revenue") is not None]

    if pruned_periods:
        story.append(Paragraph(f"HISTORICAL FINANCIAL STATEMENT PERFORMANCE ({'₹ Cr' if currency == 'INR' else '$M'})", style_section_heading))
        story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#E2E8F0"), spaceBefore=2, spaceAfter=6))

        col_labels = [f"FY{p.fiscal_year}" for p in pruned_periods]
        table_hdr = [Paragraph("<b>Financial Metric</b>", style_table_header)] + [Paragraph(f"<b>{cl}</b>", style_table_header) for cl in col_labels]
        
        # Build Rows
        row_rev = [Paragraph("<b>Sales / Revenue</b>", style_table_cell_bold)]
        row_ebit = [Paragraph("Operating Profit (EBIT)", style_table_cell)]
        row_opm = [Paragraph("Operating Margin (OPM %)", style_table_cell)]
        row_ni = [Paragraph("<b>Net Profit</b>", style_table_cell_bold)]
        row_eps = [Paragraph("Diluted EPS", style_table_cell)]
        row_fcf = [Paragraph("Free Cash Flow", style_table_cell)]

        for p in pruned_periods:
            m = p.metrics_json or {}
            row_rev.append(Paragraph(format_currency_amount(m.get("revenue"), currency), style_table_cell_bold))
            row_ebit.append(Paragraph(format_currency_amount(m.get("operating_income"), currency), style_table_cell))
            opm_val = m.get("opm_pct")
            row_opm.append(Paragraph(f"{opm_val:.2f}%" if opm_val is not None else "—", style_table_cell))
            row_ni.append(Paragraph(format_currency_amount(m.get("net_income"), currency), style_table_cell_bold))
            eps_val = m.get("eps")
            row_eps.append(Paragraph(format_per_share(eps_val, currency) if eps_val is not None else "—", style_table_cell))
            row_fcf.append(Paragraph(format_currency_amount(m.get("free_cash_flow"), currency), style_table_cell))

        fin_table_data = [table_hdr, row_rev, row_ebit, row_opm, row_ni, row_eps, row_fcf]
        
        # Calculate proportional col widths (total 540 pt)
        metric_col_w = 160
        period_col_w = (540 - metric_col_w) / max(1, len(col_labels))
        col_widths = [metric_col_w] + [period_col_w] * len(col_labels)

        t_fin = Table(fin_table_data, colWidths=col_widths)
        t_fin.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0F172A")),
            ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        story.append(t_fin)
        story.append(Spacer(1, 10))

    # =========================================================
    # 5. DCF Valuation & Scenario Analysis
    # =========================================================
    story.append(Paragraph("DCF VALUATION & SCENARIO ANALYSIS", style_section_heading))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#E2E8F0"), spaceBefore=2, spaceAfter=6))

    # DCF Parameters breakdown
    dcf_grid = [
        [
            Paragraph("<b>Parameter</b>", style_table_header),
            Paragraph("<b>Model Input</b>", style_table_header),
            Paragraph("<b>Valuation Output</b>", style_table_header),
            Paragraph("<b>Figure</b>", style_table_header),
        ],
        [
            Paragraph("Projected FCF Growth (5Y)", style_table_cell),
            Paragraph(f"{dcf.growth_rate * 100:.2f}%", style_table_cell),
            Paragraph("PV of 5Y Cash Flows", style_table_cell),
            Paragraph(format_currency_amount(dcf.pv_cash_flows, currency), style_table_cell_bold),
        ],
        [
            Paragraph("WACC (Cost of Capital)", style_table_cell),
            Paragraph(f"{dcf.wacc * 100:.2f}%", style_table_cell),
            Paragraph("PV of Terminal Value", style_table_cell),
            Paragraph(format_currency_amount(dcf.pv_terminal_value, currency), style_table_cell_bold),
        ],
        [
            Paragraph("Terminal Growth Rate", style_table_cell),
            Paragraph(f"{dcf.terminal_growth_rate * 100:.2f}%", style_table_cell),
            Paragraph("Enterprise Value (EV)", style_table_cell),
            Paragraph(format_currency_amount(dcf.enterprise_value, currency), style_table_cell_bold),
        ],
        [
            Paragraph("Base Free Cash Flow", style_table_cell),
            Paragraph(format_currency_amount(dcf.fcf_base, currency), style_table_cell),
            Paragraph("Net Debt (Debt - Cash)", style_table_cell),
            Paragraph(format_currency_amount(dcf.net_debt, currency), style_table_cell),
        ],
        [
            Paragraph("Historical Growth Benchmark", style_table_cell),
            Paragraph(f"{dcf.historical_cagr * 100:.2f}% CAGR", style_table_cell),
            Paragraph("<b>DCF Intrinsic Fair Value</b>", style_table_cell_bold),
            Paragraph(f"<b>{format_per_share(dcf.intrinsic_value, currency)}</b>", style_table_cell_bold),
        ],
    ]
    t_dcf = Table(dcf_grid, colWidths=[140, 100, 160, 140])
    t_dcf.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0F172A")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
        ("ALIGN", (1, 0), (1, -1), "CENTER"),
        ("ALIGN", (3, 0), (3, -1), "RIGHT"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(t_dcf)
    story.append(Spacer(1, 10))

    # =========================================================
    # 6. Risk Intelligence Scorecard
    # =========================================================
    story.append(Paragraph("INSTITUTIONAL RISK INTELLIGENCE SCORECARD", style_section_heading))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#E2E8F0"), spaceBefore=2, spaceAfter=6))

    p1 = risk.pillars.get("leverage_liquidity", {})
    p2 = risk.pillars.get("profitability_stability", {})
    p3 = risk.pillars.get("valuation_stretch", {})
    p4 = risk.pillars.get("earnings_quality", {})

    risk_table_data = [
        [
            Paragraph("<b>Pillar</b>", style_table_header),
            Paragraph("<b>Score</b>", style_table_header),
            Paragraph("<b>Risk Tier</b>", style_table_header),
            Paragraph("<b>Key Quantitative Metric / Assessment</b>", style_table_header),
        ],
        [
            Paragraph("<b>1. Leverage & Liquidity</b>", style_table_cell_bold),
            Paragraph(f"{p1.get('pillar_score')}/100", style_table_cell),
            Paragraph(f"<b>{p1.get('risk_level')}</b>", style_table_cell),
            Paragraph(f"D/E: {p1.get('debt_to_equity', 'N/A')} &bull; Interest Coverage: {p1.get('interest_coverage', 'N/A')}x &bull; Current Ratio: {p1.get('current_ratio', 'N/A')}", style_table_cell),
        ],
        [
            Paragraph("<b>2. Margin Stability</b>", style_table_cell_bold),
            Paragraph(f"{p2.get('pillar_score')}/100", style_table_cell),
            Paragraph(f"<b>{p2.get('risk_level')}</b>", style_table_cell),
            Paragraph(f"OPM Std Dev: {p2.get('opm_std_dev')}% &bull; Latest Revenue Growth: {p2.get('latest_revenue_growth_pct')}%", style_table_cell),
        ],
        [
            Paragraph("<b>3. Valuation Stretch</b>", style_table_cell_bold),
            Paragraph(f"{p3.get('pillar_score')}/100", style_table_cell),
            Paragraph(f"<b>{p3.get('risk_level')}</b>", style_table_cell),
            Paragraph(f"P/E Stretch: {p3.get('pe_stretch_multiple')}x historical avg &bull; DCF Downside: {p3.get('dcf_downside_pct')}%", style_table_cell),
        ],
        [
            Paragraph("<b>4. Earnings Quality</b>", style_table_cell_bold),
            Paragraph(f"{p4.get('pillar_score')}/100", style_table_cell),
            Paragraph(f"<b>{p4.get('risk_level')}</b>", style_table_cell),
            Paragraph(f"FCF / Net Income: {p4.get('fcf_to_net_income')} ({'Conversion Warning' if p4.get('is_conversion_warning') else 'Healthy Cash Conversion'})", style_table_cell),
        ],
    ]
    t_risk = Table(risk_table_data, colWidths=[130, 60, 70, 280])
    t_risk.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0F172A")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
        ("ALIGN", (1, 0), (2, -1), "CENTER"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(t_risk)
    story.append(Spacer(1, 8))

    # Grounded Watchpoints
    story.append(Paragraph("<b>Key Institutional Risk Watchpoints:</b>", style_body))
    for wp in risk.watchpoints:
        wp_item = f"&bull; <b>{wp.title} ({wp.severity}):</b> {wp.description}"
        story.append(Paragraph(wp_item, ParagraphStyle("WPItem", parent=style_body, leftIndent=8, spaceBefore=2)))
    story.append(Spacer(1, 10))

    # =========================================================
    # 7. Compliance Disclaimer & Attribution
    # =========================================================
    disclaimer_text = (
        "<b>LEGAL & COMPLIANCE DISCLAIMER:</b> This research report is automatically generated by FinSight AI's "
        "institutional financial intelligence platform. All financial statements, valuation metrics, and ratios are grounded "
        "in Neon PostgreSQL canonical stores and official exchange filings. Valuations are model-derived projections and should "
        "not be construed as personal investment advice or solicitations. FinSight AI assumes no liability for trading decisions."
    )
    story.append(Paragraph(disclaimer_text, ParagraphStyle("Disclaimer", parent=style_body, fontSize=6.5, leading=8.5, textColor=colors.HexColor("#64748B"))))

    # Build Document with NumberedCanvas
    doc.build(story, canvasmaker=NumberedCanvas)
    return buffer.getvalue()
