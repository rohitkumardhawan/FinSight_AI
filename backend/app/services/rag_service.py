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

logger = logging.getLogger(__name__)


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

    # 3. Pull exact relational SQL facts from financial_periods
    periods = (
        db.query(FinancialPeriod)
        .filter(FinancialPeriod.company_id == company_id)
        .order_by(FinancialPeriod.fiscal_year.asc())
        .all()
    )

    sql_facts_lines = [f"VERIFIED FINANCIAL METRICS FROM DATABASE ({company_name} | {symbol}):"]
    for p in periods:
        metrics = p.metrics_json or {}
        sql_facts_lines.append(
            f"- {p.fiscal_period} (FY{p.fiscal_year}): "
            f"Revenue={metrics.get('revenue', 'N/A')}, "
            f"Operating Income={metrics.get('operating_income', 'N/A')}, "
            f"OPM%={metrics.get('opm_pct', 'N/A')}%, "
            f"Net Profit={metrics.get('net_income', 'N/A')}, "
            f"EPS={metrics.get('eps', 'N/A')}, "
            f"P/E={metrics.get('pe_ratio', 'N/A')}"
        )
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

    # 5. Synthesize answer with Gemini 3.8 Flash
    system_instruction = (
        "You are an Institutional Equity Research Analyst for FinSight AI.\n"
        "Your task is to answer user questions about company performance, valuation, and financial statements.\n"
        "RULES:\n"
        "1. Ground your answer STRICTLY on the provided factual context and financial metrics.\n"
        "2. Never invent or hallucinate figures. If numbers are not in the context, explicitly say they are not reported.\n"
        "3. Explicitly cite the reporting periods or source references (e.g. '[ASIANPAINT.NS | FY2025 | Yahoo Finance]' or '[Mar-25]').\n"
        "4. Be direct, clear, and professional. Structure with concise bullet points where appropriate."
    )

    prompt = (
        f"{system_instruction}\n\n"
        f"FACTUAL CONTEXT:\n{combined_context}\n\n"
        f"USER QUESTION: {question}\n\n"
        f"ANALYST RESPONSE:"
    )

    model_name = "gemini-3.8-flash"
    answer_text = ""

    if client:
        try:
            gen_resp = client.models.generate_content(
                model=model_name,
                contents=prompt
            )
            answer_text = gen_resp.text.strip() if gen_resp.text else ""
        except Exception as ex:
            logger.error(f"Gemini generate_content failed: {ex}")
            answer_text = (
                f"Based on the verified database records for {company_name} ({symbol}):\n"
                f"{sql_facts_block}\n\n"
                f"(Note: Live AI generation encountered a temporary upstream error. The figures above are retrieved directly from the verified database records.)"
            )
    else:
        # Graceful fallback when GEMINI_API_KEY is not configured
        answer_text = (
            f"Based on verified database records for {company_name} ({symbol}):\n"
            f"{sql_facts_block}\n\n"
            f"To enable real-time conversational analysis, please ensure GEMINI_API_KEY is configured in .env."
        )

    return AskQuestionResponse(
        answer=answer_text,
        dataset_id=company_id,
        company_name=company_name,
        model=model_name,
        citations=citations
    )
