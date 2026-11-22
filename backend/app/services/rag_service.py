"""
FinSight AI — Institutional RAG Intelligence Service
===================================================
Generates grounded semantic chunks, computes 3072-dimensional vector embeddings
via Google GenAI (`gemini-embedding-001`), indexes chunks into Neon PostgreSQL
(`pgvector` HNSW index), and performs grounded Q&A with `gemini-3.8-flash`.
"""

from typing import List, Dict, Any, Optional
import logging
from sqlalchemy.orm import Session
from sqlalchemy import select, text
from google import genai

from app.core.config import settings
from app.models.dataset import RagChunk, FinancialPeriod
from app.models.company import Company
from app.schemas.dataset import ParsedCompanyDataset, CitationItem, AskQuestionResponse
from app.services.risk_engine import calculate_risk_intelligence

logger = logging.getLogger(__name__)


def format_currency_amount(val: Optional[float], currency: str) -> str:
    """Formats large financial totals in ₹ Cr for INR or $M/$B for USD."""
    if val is None:
        return "N/A"
    curr = (currency or "INR").upper()
    is_inr = (curr == "INR")
    abs_v = abs(val)
    prefix = "-" if val < 0 else ""
    if is_inr:
        crores = abs_v / 1e7
        return f"{prefix}₹{crores:,.2f} Cr"
    else:
        if abs_v >= 1e9:
            return f"{prefix}${abs_v / 1e9:,.2f}B"
        elif abs_v >= 1e6:
            return f"{prefix}${abs_v / 1e6:,.2f}M"
        else:
            return f"{prefix}${abs_v:,.2f}"


def format_per_share(val: Optional[float], currency: str) -> str:
    """Formats per-share metrics like EPS or Share Price."""
    if val is None:
        return "N/A"
    curr = (currency or "INR").upper()
    sym = "₹" if curr == "INR" else "$"
    return f"{sym}{val:,.2f}"


def _build_deterministic_executive_summary(
    company: Company,
    periods: List[FinancialPeriod],
    currency: str,
    risk_summary_text: str = ""
) -> str:
    """Builds a formatted, publication-ready executive summary when LLM is unavailable."""
    symbol = company.symbol or company.ticker or ""
    company_name = company.company_name or symbol

    annual_periods = [
        p for p in periods
        if getattr(p, "statement_type", "") != "quarterly"
        and (not getattr(p, "fiscal_period", "") or not getattr(p, "fiscal_period", "").startswith("Q"))
    ]
    latest_p = annual_periods[-1] if annual_periods else (periods[-1] if periods else None)
    prev_p = annual_periods[-2] if len(annual_periods) >= 2 else None

    m_latest = latest_p.metrics_json or {} if latest_p else {}
    m_prev = prev_p.metrics_json or {} if prev_p else {}

    rev_now = m_latest.get("revenue")
    rev_prev = m_prev.get("revenue")
    rev_growth_str = "N/A"
    if rev_now is not None and rev_prev and rev_prev > 0:
        g = ((rev_now - rev_prev) / rev_prev) * 100.0
        rev_growth_str = f"{'+' if g >= 0 else ''}{g:.2f}%"

    op_income = m_latest.get("operating_income")
    opm = m_latest.get("opm_pct")
    net_inc = m_latest.get("net_income")
    eps = m_latest.get("eps")
    ocf = m_latest.get("operating_cash_flow")
    capex = m_latest.get("capital_expenditure")
    fcf = m_latest.get("free_cash_flow")
    tot_debt = m_latest.get("total_debt")
    tot_equity = m_latest.get("total_equity")
    net_debt = m_latest.get("net_debt")
    curr_assets = m_latest.get("current_assets")
    curr_liab = m_latest.get("current_liabilities")

    fcf_ni_ratio_str = "N/A"
    if fcf is not None and net_inc and net_inc != 0:
        fcf_ni_ratio_str = f"{fcf / net_inc:.2f}x"

    de_ratio_str = "N/A"
    if tot_debt is not None and tot_equity and tot_equity > 0:
        de_ratio_str = f"{tot_debt / tot_equity:.2f}x"

    curr_ratio_str = "N/A"
    if curr_assets is not None and curr_liab and curr_liab > 0:
        curr_ratio_str = f"{curr_assets / curr_liab:.2f}x"

    quote = (company.metadata_json or {}).get("quote") or {}
    trailing_pe = quote.get("trailing_pe") or quote.get("trailingPE") or m_latest.get("pe_ratio")
    pe_str = f"{float(trailing_pe):.2f}x" if trailing_pe else "N/A"

    period_lbl = latest_p.fiscal_period if latest_p else "Latest Period"

    lines = [
        f"### Executive Financial Summary: {company_name} ({symbol})",
        f"**Reporting Period:** {period_lbl} | **Reporting Currency:** {currency}",
        "",
        "#### 1. Profitability & Operational Performance",
        f"- **Annual Revenue:** {format_currency_amount(rev_now, currency)} (YoY Growth: {rev_growth_str})",
        f"- **Operating Profit (EBIT):** {format_currency_amount(op_income, currency)} (OPM: {f'{opm:.2f}%' if opm is not None else 'N/A'})",
        f"- **Net Profit:** {format_currency_amount(net_inc, currency)} (Diluted EPS: {format_per_share(eps, currency)})",
        "",
        "#### 2. Cash Generation & Capital Allocation",
        f"- **Operating Cash Flow (OCF):** {format_currency_amount(ocf, currency)}",
        f"- **Capital Expenditures (CapEx):** {format_currency_amount(capex, currency)}",
        f"- **Free Cash Flow (FCF):** {format_currency_amount(fcf, currency)}",
        f"- **Cash Conversion (FCF / Net Income):** {fcf_ni_ratio_str}",
        "",
        "#### 3. Balance Sheet Health & Leverage",
        f"- **Total Debt:** {format_currency_amount(tot_debt, currency)} | **Net Debt:** {format_currency_amount(net_debt, currency)}",
        f"- **Debt-to-Equity (D/E):** {de_ratio_str}",
        f"- **Current Ratio:** {curr_ratio_str}",
        "",
        "#### 4. Valuation Multiples",
        f"- **Trailing P/E Multiple:** {pe_str}"
    ]

    if risk_summary_text:
        lines.extend(["", "#### 5. Institutional Risk Scorecard", risk_summary_text])

    return "\n".join(lines)


def _get_genai_client() -> Optional[genai.Client]:
    """Returns an authenticated Google GenAI Client if API key is present."""
    if not settings.GEMINI_API_KEY:
        return None
    try:
        return genai.Client(api_key=settings.GEMINI_API_KEY)
    except Exception as e:
        logger.error(f"Failed to initialize Google GenAI Client: {e}")
        return None


def build_company_chunks(company_id: int, parsed: ParsedCompanyDataset) -> List[Dict[str, Any]]:
    """
    Constructs high-density, semantically grounded narrative chunks from the normalized dataset:
    - Profile chunk
    - Financial Period chunks (one per annual/TTM reporting period)
    - Multi-year Trends chunk
    - Valuation & Scenario Analysis chunk
    """
    chunks: List[Dict[str, Any]] = []
    symbol = parsed.raw_metadata.get("symbol") or parsed.company_name
    currency = parsed.raw_metadata.get("currency") or "INR"
    auto_insights = parsed.auto_insights or {}

    # 1. Profile / Executive Summary Chunk
    overview_text = (
        f"COMPANY PROFILE & SUMMARY:\n"
        f"Company Name: {parsed.company_name}\n"
        f"Symbol/Ticker: {symbol}\n"
        f"Data Source / Format: {parsed.detected_format}\n"
        f"Reporting Currency: {currency}\n"
        f"Total Financial Periods Analyzed: {len(parsed.periods)}\n"
        f"Market Cap: {parsed.raw_metadata.get('market_cap', 'N/A')}\n"
        f"Current Price: {currency} {parsed.raw_metadata.get('current_price', 'N/A')}\n"
        f"Trailing P/E: {parsed.raw_metadata.get('trailing_pe', 'N/A')}\n"
        f"Executive Narrative: {auto_insights.get('summary_narrative', 'N/A')}\n"
    )
    chunks.append({
        "chunk_type": "profile",
        "source_ref": f"{symbol} | Profile Overview",
        "content": overview_text
    })

    # 2. Individual Financial Period Chunks
    for p in parsed.periods:
        period_label = p.fiscal_period or f"FY{p.fiscal_year}"
        lines = [
            f"FINANCIAL STATEMENT METRICS FOR {parsed.company_name} ({symbol}) — {period_label} (Fiscal Year: {p.fiscal_year}):",
            f"- Revenue / Sales: {currency} {p.revenue:,.2f}" if p.revenue is not None else "- Revenue / Sales: N/A",
            f"- Operating Profit / Income: {currency} {p.operating_income:,.2f}" if p.operating_income is not None else "- Operating Profit / Income: N/A",
            f"- Operating Margin (OPM): {p.opm_pct:.2f}%" if p.opm_pct is not None else "- Operating Margin (OPM): N/A",
            f"- Net Profit / Income: {currency} {p.net_income:,.2f}" if p.net_income is not None else "- Net Profit / Income: N/A",
            f"- Earnings Per Share (EPS): {currency} {p.eps:.2f}" if p.eps is not None else "- Earnings Per Share (EPS): N/A",
            f"- Price to Earnings (P/E): {p.pe_ratio:.2f}" if p.pe_ratio is not None else "- Price to Earnings (P/E): N/A",
            f"- Share Price: {currency} {p.share_price:.2f}" if p.share_price is not None else "- Share Price: N/A",
        ]
        if p.cost_of_revenue is not None:
            lines.append(f"- Cost of Revenue: {currency} {p.cost_of_revenue:,.2f}")
        if p.gross_profit is not None:
            lines.append(f"- Gross Profit: {currency} {p.gross_profit:,.2f}")
        if p.depreciation_amortization is not None:
            lines.append(f"- Depreciation & Amortization: {currency} {p.depreciation_amortization:,.2f}")
        if p.interest_expense is not None:
            lines.append(f"- Interest Expense: {currency} {p.interest_expense:,.2f}")
        if p.profit_before_tax is not None:
            lines.append(f"- Profit Before Tax: {currency} {p.profit_before_tax:,.2f}")
        if p.tax_expense is not None:
            lines.append(f"- Tax Expense: {currency} {p.tax_expense:,.2f}")
        if p.operating_cash_flow is not None:
            lines.append(f"- Operating Cash Flow: {currency} {p.operating_cash_flow:,.2f}")
        if p.free_cash_flow is not None:
            lines.append(f"- Free Cash Flow: {currency} {p.free_cash_flow:,.2f}")
        if p.total_assets is not None:
            lines.append(f"- Total Assets: {currency} {p.total_assets:,.2f}")
        if p.total_equity is not None:
            lines.append(f"- Total Equity / Net Worth: {currency} {p.total_equity:,.2f}")
        if p.total_debt is not None:
            lines.append(f"- Total Debt: {currency} {p.total_debt:,.2f}")

        chunks.append({
            "chunk_type": "period",
            "source_ref": f"{symbol} | {period_label} | {p.source or parsed.detected_format}",
            "content": "\n".join(lines)
        })

    # 3. Multi-Year Trends Chunk
    trends = auto_insights.get("trends") or parsed.trends
    if trends:
        metrics = trends.get("metrics", {})
        headers = trends.get("headers", [])
        trends_lines = [
            f"MULTI-YEAR COMPOUNDED ANNUAL GROWTH (CAGR) & MARGIN TRENDS FOR {parsed.company_name} ({symbol}):",
            f"Observed Horizon Windows: {', '.join(headers) if headers else 'Historical multi-year'}"
        ]
        for metric_name, span_values in metrics.items():
            formatted_spans = [f"{span}: {val}%" for span, val in span_values.items() if val is not None]
            if formatted_spans:
                trends_lines.append(f"- {metric_name.replace('_', ' ').title()}: {', '.join(formatted_spans)}")
        
        chunks.append({
            "chunk_type": "trends",
            "source_ref": f"{symbol} | Historical Trends Matrix",
            "content": "\n".join(trends_lines)
        })

    # 4. Valuation & Scenario Projections Chunk
    scenarios = auto_insights.get("scenario_insights") or parsed.scenarios
    if scenarios:
        scen_lines = [
            f"VALUATION BENCHMARK & SCENARIO ANALYSIS FOR {parsed.company_name} ({symbol}):",
            f"- Trailing Share Price: {currency} {scenarios.get('trailing_price', 'N/A')}",
            f"- Trailing P/E Multiple: {scenarios.get('trailing_pe', 'N/A')}x",
            f"- Historical Average P/E: {scenarios.get('historical_avg_pe', 'N/A')}x",
            f"- Historical Median P/E: {scenarios.get('historical_median_pe', 'N/A')}x",
        ]
        if scenarios.get("base_case_price"):
            scen_lines.append(f"- Base Case Target Price: {currency} {scenarios.get('base_case_price')}")
        if scenarios.get("best_case_price"):
            scen_lines.append(f"- Best Case Target Price: {currency} {scenarios.get('best_case_price')} (Implied Upside: {scenarios.get('upside_best_pct', 'N/A')}%)")
        if scenarios.get("worst_case_price"):
            scen_lines.append(f"- Worst Case Target Price: {currency} {scenarios.get('worst_case_price')} (Implied Downside: {scenarios.get('downside_worst_pct', 'N/A')}%)")

        chunks.append({
            "chunk_type": "scenarios",
            "source_ref": f"{symbol} | Valuation & Scenarios",
            "content": "\n".join(scen_lines)
        })

    return chunks


def index_company_chunks(db: Session, company_id: int, parsed: ParsedCompanyDataset) -> int:
    """
    Builds narrative chunks, computes 3072-dimensional embeddings using `gemini-embedding-001`,
    and inserts into Neon PostgreSQL `rag_chunks` table.
    """
    raw_chunks = build_company_chunks(company_id, parsed)
    if not raw_chunks:
        return 0

    # Delete any prior rag_chunks for this company to maintain freshness
    db.query(RagChunk).filter(RagChunk.company_id == company_id).delete()
    db.commit()

    client = _get_genai_client()
    contents = [c["content"] for c in raw_chunks]
    embeddings_list: List[Optional[List[float]]] = []

    if client:
        try:
            # Batch embedding call via google-genai SDK
            res = client.models.embed_content(
                model="gemini-embedding-001",
                contents=contents
            )
            raw_embeddings = getattr(res, "embeddings", [])
            for item in raw_embeddings:
                if hasattr(item, "values"):
                    embeddings_list.append(list(item.values))
                else:
                    embeddings_list.append(None)
        except Exception as e:
            logger.error(f"Gemini embed_content failed: {e}. Falling back to un-embedded text chunks.")
            embeddings_list = [None] * len(raw_chunks)
    else:
        embeddings_list = [None] * len(raw_chunks)

    # Insert into Neon PostgreSQL
    inserted_count = 0
    for idx, chunk in enumerate(raw_chunks):
        vec = embeddings_list[idx] if idx < len(embeddings_list) else None
        rc = RagChunk(
            company_id=company_id,
            chunk_type=chunk["chunk_type"],
            source_ref=chunk["source_ref"],
            content=chunk["content"],
            embedding=vec
        )
        db.add(rc)
        inserted_count += 1

    db.commit()
    logger.info(f"Indexed {inserted_count} RAG chunks for company ID {company_id}")
    return inserted_count


async def ask_company_question(db: Session, company_id: int, question: str) -> AskQuestionResponse:
    """
    Performs hybrid SQL + pgvector cosine similarity search, retrieves grounded
    financial facts, and synthesizes an institutional research answer with citations.
    """
    # 1. Fetch Company details
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise ValueError(f"Company with ID {company_id} not found")

    company_name = company.company_name
    symbol = company.symbol or company.ticker or "STOCK"

    # 2. Vector search via pgvector cosine distance
    client = _get_genai_client()
    retrieved_chunks: List[RagChunk] = []

    if client:
        try:
            embed_res = client.models.embed_content(
                model="gemini-embedding-001",
                contents=[question]
            )
            q_embeddings = getattr(embed_res, "embeddings", [])
            if q_embeddings and hasattr(q_embeddings[0], "values"):
                query_vec = list(q_embeddings[0].values)
                if len(query_vec) == 3072:
                    # Perform cosine similarity search via pgvector
                    stmt = (
                        select(RagChunk)
                        .where(RagChunk.company_id == company_id)
                        .where(RagChunk.embedding.isnot(None))
                        .order_by(RagChunk.embedding.cosine_distance(query_vec))
                        .limit(5)
                    )
                    retrieved_chunks = list(db.scalars(stmt).all())
        except Exception as e:
            db.rollback()
            logger.warning(f"Vector search failed: {e}. Falling back to relational chunks.")

    # Fallback to top relational chunks if vector search didn't return 5
    if len(retrieved_chunks) < 5:
        existing_ids = {c.id for c in retrieved_chunks}
        fallback_chunks = (
            db.query(RagChunk)
            .filter(RagChunk.company_id == company_id)
            .filter(~RagChunk.id.in_(existing_ids) if existing_ids else True)
            .limit(5 - len(retrieved_chunks))
            .all()
        )
        retrieved_chunks.extend(fallback_chunks)

    # 3. Pull exact relational SQL facts from financial_periods and prune empty/all-null periods
    raw_periods = (
        db.query(FinancialPeriod)
        .filter(FinancialPeriod.company_id == company_id)
        .order_by(FinancialPeriod.fiscal_year.asc())
        .all()
    )

    currency = company.currency or "INR"

    # Prune periods where revenue, operating_income, and net_income are all None
    periods = []
    for p in raw_periods:
        m = p.metrics_json or {}
        if m.get("revenue") is None and m.get("operating_income") is None and m.get("net_income") is None:
            continue
        periods.append(p)

    # Compute grounded risk scorecard context
    risk_summary_text = ""
    try:
        risk_obj = calculate_risk_intelligence(company, periods)
        p1 = risk_obj.pillars.get("leverage_liquidity", {})
        p2 = risk_obj.pillars.get("profitability_stability", {})
        p3 = risk_obj.pillars.get("valuation_stretch", {})
        p4 = risk_obj.pillars.get("earnings_quality", {})
        risk_summary_text = (
            f"VERIFIED RISK INTELLIGENCE SCORECARD ({company_name} | {symbol}):\n"
            f"- Overall Score: {risk_obj.overall_score}/100 ({risk_obj.risk_level} Risk Tier)\n"
            f"- Leverage & Liquidity: Tier={p1.get('risk_level')}, D/E={p1.get('debt_to_equity') if p1.get('debt_to_equity') is not None else 'N/A'}, "
            f"Interest Coverage={p1.get('interest_coverage') if p1.get('interest_coverage') is not None else 'N/A'}x, "
            f"Current Ratio={p1.get('current_ratio') if p1.get('current_ratio') is not None else 'N/A'}\n"
            f"- Margin Stability: Tier={p2.get('risk_level')}, OPM Std Dev={p2.get('opm_std_dev')}%, "
            f"Latest Rev Growth={p2.get('latest_revenue_growth_pct') if p2.get('latest_revenue_growth_pct') is not None else 'N/A'}%\n"
            f"- Valuation Stretch: Tier={p3.get('risk_level')}, Trailing P/E={p3.get('current_pe') if p3.get('current_pe') is not None else 'N/A'}x, "
            f"Hist Avg P/E={p3.get('historical_avg_pe') if p3.get('historical_avg_pe') is not None else 'N/A'}x\n"
            f"- Earnings Quality: Tier={p4.get('risk_level')}, FCF/Net Income={p4.get('fcf_to_net_income') if p4.get('fcf_to_net_income') is not None else 'N/A'}x"
        )
    except Exception as risk_err:
        logger.warning(f"Could not compute risk intelligence for context: {risk_err}")

    sql_facts_lines = [f"VERIFIED FINANCIAL METRICS FROM DATABASE ({company_name} | {symbol}) [Currency: {currency}]:"]
    for p in periods:
        metrics = p.metrics_json or {}
        rev_s = format_currency_amount(metrics.get("revenue"), currency)
        op_s = format_currency_amount(metrics.get("operating_income"), currency)
        opm_s = f"{metrics.get('opm_pct'):.2f}%" if metrics.get("opm_pct") is not None else "N/A"
        ni_s = format_currency_amount(metrics.get("net_income"), currency)
        eps_s = format_per_share(metrics.get("eps"), currency) if metrics.get("eps") is not None else "N/A"
        pe_s = f"{metrics.get('pe_ratio'):.2f}x" if metrics.get("pe_ratio") is not None else "N/A"
        
        ocf_s = format_currency_amount(metrics.get("operating_cash_flow"), currency)
        capex_s = format_currency_amount(metrics.get("capital_expenditure"), currency)
        fcf_s = format_currency_amount(metrics.get("free_cash_flow"), currency)
        fcf_val = metrics.get("free_cash_flow")
        ni_val = metrics.get("net_income")
        fcf_ni_s = f"{fcf_val / ni_val:.2f}x" if (fcf_val is not None and ni_val and ni_val != 0) else "N/A"

        tot_debt_s = format_currency_amount(metrics.get("total_debt"), currency)
        net_debt_s = format_currency_amount(metrics.get("net_debt"), currency)
        tot_eq = metrics.get("total_equity")
        de_s = f"{metrics.get('total_debt') / tot_eq:.2f}x" if (metrics.get("total_debt") is not None and tot_eq and tot_eq > 0) else "N/A"
        ca = metrics.get("current_assets")
        cl = metrics.get("current_liabilities")
        cr_s = f"{ca / cl:.2f}x" if (ca is not None and cl and cl > 0) else "N/A"

        sql_facts_lines.append(
            f"- {p.fiscal_period} (FY{p.fiscal_year}): "
            f"Revenue={rev_s}, Operating Income={op_s}, OPM={opm_s}, Net Profit={ni_s}, EPS={eps_s}, P/E={pe_s} | "
            f"OCF={ocf_s}, CapEx={capex_s}, FCF={fcf_s}, FCF/Net Income={fcf_ni_s} | "
            f"Total Debt={tot_debt_s}, Net Debt={net_debt_s}, D/E={de_s}, Current Ratio={cr_s}"
        )

    if risk_summary_text:
        sql_facts_lines.append("")
        sql_facts_lines.append(risk_summary_text)

    sql_facts_block = "\n".join(sql_facts_lines)

    # 4. Assemble context and citations
    context_blocks = [sql_facts_block]
    citations: List[CitationItem] = []

    for rc in retrieved_chunks:
        context_blocks.append(f"SOURCE: [{rc.source_ref}]\n{rc.content}\n")
        snippet = rc.content[:160].replace("\n", " ").strip() + "..."
        citations.append(CitationItem(
            source_ref=rc.source_ref or f"{symbol} Fact",
            chunk_type=rc.chunk_type,
            snippet=snippet
        ))

    combined_context = "\n---\n".join(context_blocks)

    # 5. Synthesize answer with Gemini (gemini-3.8-flash with gemini-2.5-flash fallback)
    system_instruction = (
        "You are an Institutional Equity Research Analyst for FinSight AI.\n"
        "Your task is to answer user questions about company performance, valuation, cash flow, and risk.\n"
        "RULES:\n"
        "1. Ground your answer STRICTLY on the provided factual context and financial metrics.\n"
        "2. Never invent or hallucinate figures. If numbers are not in the context, explicitly say they are not reported.\n"
        "3. Always use the formatted currency figures (e.g. ₹ Cr for INR or $B/$M for USD) and metric ratios.\n"
        "4. Explicitly cite the reporting periods or source references (e.g. '[ASIANPAINT.NS | FY2025 | Yahoo Finance]' or '[FY2026]').\n"
        "5. Be direct, clear, and professional. Structure with concise bullet points where appropriate."
    )

    prompt = (
        f"{system_instruction}\n\n"
        f"FACTUAL CONTEXT:\n{combined_context}\n\n"
        f"USER QUESTION: {question}\n\n"
        f"ANALYST RESPONSE:"
    )

    CANDIDATE_MODELS = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-flash-latest"]
    answer_text = ""
    active_model = "deterministic-executive-summary"
    ai_mode = "fallback"

    if client:
        for model_candidate in CANDIDATE_MODELS:
            try:
                gen_resp = client.models.generate_content(
                    model=model_candidate,
                    contents=prompt
                )
                if gen_resp and gen_resp.text and gen_resp.text.strip():
                    answer_text = gen_resp.text.strip()
                    active_model = model_candidate
                    ai_mode = "live"
                    logger.info(f"Gemini live synthesis succeeded with model {model_candidate}.")
                    break
            except Exception as ex:
                safe_err = str(ex).replace(settings.GEMINI_API_KEY or "", "[REDACTED]")
                logger.warning(
                    f"Gemini live call failed with model '{model_candidate}': "
                    f"Exception class: {ex.__class__.__name__}, Message: {safe_err}"
                )

    if not answer_text:
        ai_mode = "fallback"
        active_model = "deterministic-executive-summary"
        logger.info("Using deterministic executive summary fallback.")
        answer_text = _build_deterministic_executive_summary(company, periods, currency, risk_summary_text)

    return AskQuestionResponse(
        answer=answer_text,
        dataset_id=company_id,
        company_name=company_name,
        model=active_model,
        citations=citations,
        ai_mode=ai_mode
    )
