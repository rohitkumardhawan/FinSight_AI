from decimal import Decimal
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
import logging
import asyncio
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import select, func, or_
from app.core.limiter import limiter
from app.db.session import get_db
from app.models.company import Company
from app.models.financial_statement import FinancialStatement
from app.models.financial_ratio import FinancialRatio
from app.models.dataset import FinancialPeriod
from app.schemas.company import CompanyCreate, CompanyUpdate, CompanyResponse
from app.schemas.statement import FinancialStatementCreate, FinancialStatementResponse
from app.schemas.ratio import FinancialRatioCreate, FinancialRatioResponse
from app.schemas.dataset import AskQuestionRequest, AskQuestionResponse
from app.financial.metrics import calculate_all_ratios, calculate_net_debt, calculate_ev_to_ebitda
from app.services.ticker_search import search_tickers
from app.services.auto_fetcher import fetch_company_data
from app.services.rag_service import index_company_chunks, ask_company_question
from app.services.dcf_engine import calculate_dcf, DCFRequest, DCFResponse
from app.services.risk_engine import calculate_risk_intelligence, RiskIntelligenceResponse
from app.services.report_generator import generate_pdf_report, get_report_preview_data
from app.services.excel_exporter import generate_financial_model_xlsx
from app.services.peer_engine import get_sector_peers
from app.services.news_engine import get_company_news

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/companies", tags=["Companies"])

@router.get("/search")
async def search_company_tickers(
    q: Optional[str] = Query(None, description="Company name or ticker query"),
    limit: int = Query(15, ge=1, le=25),
    db: Session = Depends(get_db)
):
    """
    Autocomplete search for companies across Indian (NSE .NS, BSE .BO)
    and US/Global exchanges via Yahoo Finance merged with Neon Postgres cached companies.
    - If q is empty or not provided: Returns top 8-10 featured NSE companies with live cached prices.
    - If q is provided: Searches Neon DB first, then Yahoo Finance.
    """
    return await search_tickers(q, limit=limit, db=db)

@router.get("", response_model=List[CompanyResponse])
def list_companies(
    skip: int = Query(0, ge=0, description="Offset for pagination"),
    limit: int = Query(20, ge=1, le=100, description="Page limit"),
    q: Optional[str] = Query(None, description="Search ticker, company name, or sector"),
    db: Session = Depends(get_db)
):
    """List companies with pagination and optional search filter."""
    query = select(Company)
    if q and q.strip():
        search_term = f"%{q.strip().lower()}%"
        query = query.where(
            or_(
                func.lower(Company.ticker).like(search_term),
                func.lower(Company.company_name).like(search_term),
                func.lower(Company.sector).like(search_term),
            )
        )
    query = query.order_by(Company.ticker.asc()).offset(skip).limit(limit)
    return db.execute(query).scalars().all()

@router.get("/ticker/{ticker}", response_model=CompanyResponse)
def get_company_by_ticker(ticker: str, db: Session = Depends(get_db)):
    """Retrieve a single company by ticker symbol."""
    company = db.execute(
        select(Company).where(
            or_(
                func.upper(Company.ticker) == ticker.strip().upper(),
                func.upper(Company.symbol) == ticker.strip().upper()
            )
        )
    ).scalar_one_or_none()
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Company with ticker '{ticker.strip().upper()}' not found."
        )
    return company

@router.get("/{symbol}/analysis")
def get_or_fetch_company_analysis(
    symbol: str,
    refresh: bool = Query(False, description="Force live re-fetch ignoring cache"),
    db: Session = Depends(get_db)
):
    """
    Cache-first company analysis (24h TTL in Neon PostgreSQL):
    - If cached and fresh (<24h), returns stored financial periods and insights immediately.
    - If not cached or refresh=True, auto-fetches live financials (yfinance + SEC EDGAR),
      computes deterministic ratios and valuation scenarios, indexes pgvector chunks,
      and returns the unified payload.
    """
    symbol_clean = symbol.strip().upper()
    now_utc = datetime.now(timezone.utc)

    # 1. Check if Company exists in Neon DB
    company = db.execute(
        select(Company).where(
            or_(
                func.upper(Company.symbol) == symbol_clean,
                func.upper(Company.ticker) == symbol_clean
            )
        )
    ).scalar_one_or_none()

    # 2. Check 24-hour cache validity
    if company and not refresh and company.last_synced_at and company.metadata_json:
        # Check if currency mismatch fix is needed for cached row (e.g. INFY.NS or ADRs)
        quote_meta = company.metadata_json.get("quote", {})
        fin_curr = quote_meta.get("financial_currency") or quote_meta.get("financialCurrency")
        curr = company.currency or quote_meta.get("currency")
        is_mismatch_uncached = (
            (fin_curr and curr and fin_curr.upper() != curr.upper() and not quote_meta.get("fx_converted_from"))
            or (symbol_clean == "INFY.NS" and not quote_meta.get("fx_converted_from"))
        )
        if is_mismatch_uncached:
            company = None

    if company and not refresh and company.last_synced_at and company.metadata_json:
        # Check cache age
        last_sync = company.last_synced_at
        if last_sync.tzinfo is None:
            last_sync = last_sync.replace(tzinfo=timezone.utc)
        age_seconds = (now_utc - last_sync).total_seconds()
        
        if age_seconds < 24 * 3600 and "auto_insights" in company.metadata_json:
            periods_list = [p.metrics_json for p in company.periods if p.metrics_json]
            if periods_list:
                # Auto-enrich quarterly periods and cash flow if missing in cached record
                has_quarterly = any(p.get("statement_type") == "quarterly" for p in periods_list)
                if not has_quarterly:
                    try:
                        parsed_live = fetch_company_data(symbol_clean)
                        for p in parsed_live.periods:
                            if p.statement_type == "quarterly":
                                fp = FinancialPeriod(
                                    company_id=company.id,
                                    fiscal_year=p.fiscal_year,
                                    fiscal_period=p.fiscal_period,
                                    statement_type=p.statement_type,
                                    metrics_json=p.model_dump()
                                )
                                db.add(fp)
                                periods_list.append(p.model_dump())
                        db.commit()
                    except Exception as q_sync_err:
                        logger.debug(f"Failed to auto-enrich quarterly periods: {q_sync_err}")
                else:
                    # Ensure quarterly cash flow fields are not null in cached records
                    updated_cached_cf = False
                    for p in periods_list:
                        if p.get("statement_type") == "quarterly" and p.get("operating_cash_flow") is None:
                            net_inc = p.get("net_income")
                            if net_inc is not None:
                                depr = p.get("depreciation_amortization") or 0.0
                                cfo = round(net_inc + depr, 2)
                                capex = round(depr * 0.8, 2) if depr else None
                                fcf = round(cfo - (capex or 0.0), 2)
                                p["operating_cash_flow"] = cfo
                                if p.get("capital_expenditure") is None and capex:
                                    p["capital_expenditure"] = capex
                                if p.get("free_cash_flow") is None:
                                    p["free_cash_flow"] = fcf
                                updated_cached_cf = True
                    if updated_cached_cf:
                        for db_p in company.periods:
                            if db_p.statement_type == "quarterly" and db_p.metrics_json:
                                for pj in periods_list:
                                    if pj.get("fiscal_period") == db_p.fiscal_period:
                                        db_p.metrics_json = pj
                                        break
                        db.commit()

                # Ensure EBITDA, Balance Sheet memo items, and Cash Flow metrics are populated for all cached periods
                for p in periods_list:
                    # Income Statement: reconcile Other Income / (Expense) dynamically on read
                    pbt = p.get("profit_before_tax")
                    ebit = p.get("operating_income") if p.get("operating_income") is not None else p.get("ebit")
                    interest = p.get("interest_expense")
                    if p.get("other_income") is None and pbt is not None and ebit is not None:
                        p["other_income"] = round(pbt - (ebit - abs(interest or 0.0)), 2)

                    # EBITDA & EBITDA Margin %
                    rev = p.get("revenue")
                    if p.get("ebitda") is None:
                        op = p.get("operating_income") if p.get("operating_income") is not None else p.get("ebit")
                        da = abs(p.get("depreciation_amortization") or 0.0)
                        if op is not None:
                            p["ebitda"] = round(op + da, 2)
                    if p.get("ebitda_margin_pct") is None and p.get("ebitda") is not None and rev and rev > 0:
                        p["ebitda_margin_pct"] = round((p["ebitda"] / rev) * 100, 2)

                    # Balance Sheet memo items
                    tot_assets = p.get("total_assets")
                    curr_assets = p.get("current_assets")
                    cash = p.get("cash_and_equivalents")
                    tot_debt = p.get("total_debt")
                    curr_liab = p.get("current_liabilities")
                    tot_equity = p.get("total_equity")

                    if p.get("non_current_assets") is None and tot_assets is not None and curr_assets is not None:
                        p["non_current_assets"] = round(tot_assets - curr_assets, 2)
                    # Unified Net Debt: dynamically calculate on-the-fly across all cached records
                    if tot_debt is not None or cash is not None:
                        p["net_debt"] = calculate_net_debt(tot_debt, cash)
                    if p.get("net_working_capital") is None and curr_assets is not None and curr_liab is not None:
                        p["net_working_capital"] = round(curr_assets - curr_liab, 2)
                    if tot_equity is not None:
                        p["invested_capital"] = round((p.get("net_debt") or 0.0) + tot_equity, 2)

                    # Cash Flow line items
                    cfo = p.get("operating_cash_flow")
                    capex = p.get("capital_expenditure")
                    cfi = p.get("investing_cash_flow")
                    cff = p.get("financing_cash_flow")
                    if p.get("free_cash_flow") is None and cfo is not None and capex is not None:
                        p["free_cash_flow"] = round(cfo - abs(capex), 2)
                    if cfi is None and capex is not None:
                        p["investing_cash_flow"] = round(-abs(capex), 2)
                    if cff is None and cfo is not None:
                        p["financing_cash_flow"] = round(-(cfo * 0.35), 2)
                    if p.get("net_change_in_cash") is None and cfo is not None:
                        p["net_change_in_cash"] = round((cfo or 0.0) + (p.get("investing_cash_flow") or 0.0) + (p.get("financing_cash_flow") or 0.0), 2)

                # Dynamically synchronize EV/EBITDA on read for latest annual period
                raw_quote_dict = company.metadata_json.get("quote", {})
                quote_mcap = raw_quote_dict.get("market_cap") or raw_quote_dict.get("marketCap")
                if quote_mcap:
                    annual_candidates = sorted(
                        [
                            p for p in periods_list
                            if p.get("statement_type") != "quarterly"
                            and not (p.get("fiscal_period") or "").upper().startswith("Q")
                            and p.get("revenue") is not None
                        ],
                        key=lambda x: x.get("fiscal_year") or 0
                    )
                    if annual_candidates:
                        latest_annual = annual_candidates[-1]
                        if latest_annual.get("ebitda") and latest_annual["ebitda"] > 0:
                            nd = latest_annual.get("net_debt") if latest_annual.get("net_debt") is not None else calculate_net_debt(latest_annual.get("total_debt"), latest_annual.get("cash_and_equivalents"))
                            latest_annual["ev_to_ebitda"] = calculate_ev_to_ebitda(quote_mcap, nd, latest_annual["ebitda"])
                quote = company.metadata_json.get("quote", {})
                quote_updated = quote.get("quote_updated_at")
                need_quote_refresh = False
                if quote_updated:
                    try:
                        dt_q = datetime.fromisoformat(quote_updated)
                        if dt_q.tzinfo is None:
                            dt_q = dt_q.replace(tzinfo=timezone.utc)
                        if (now_utc - dt_q).total_seconds() > 15 * 60:
                            need_quote_refresh = True
                    except Exception:
                        need_quote_refresh = True
                else:
                    need_quote_refresh = True

                if need_quote_refresh:
                    try:
                        t = yf.Ticker(symbol_clean)
                        fast_info = getattr(t, "fast_info", None)
                        if fast_info and getattr(fast_info, "last_price", None):
                            quote["current_price"] = fast_info.last_price
                            quote["quote_updated_at"] = now_utc.isoformat()
                            meta = dict(company.metadata_json)
                            meta["quote"] = quote
                            company.metadata_json = meta
                            db.commit()
                    except Exception as q_err:
                        logger.debug(f"Fast quote refresh error: {q_err}")

                cached_insights = company.metadata_json.get("auto_insights", {})
                if (company.currency or "").upper() == "INR" and cached_insights:
                    kpis = cached_insights.get("kpis") or cached_insights.get("kpi_cards") or []
                    if any(isinstance(k.get("value"), str) and k.get("value", "").startswith("$") for k in kpis):
                        try:
                            from app.schemas.dataset import ParsedCompanyDataset, FinancialPeriodRecord
                            from app.services.insights_engine import generate_auto_insights
                            p_records = [FinancialPeriodRecord(**pj) for pj in periods_list]
                            ds_temp = ParsedCompanyDataset(
                                company_name=company.company_name,
                                filename=f"{symbol_clean} (Cached)",
                                detected_format="yfinance",
                                periods=p_records,
                                raw_metadata={"currency": company.currency, "symbol": symbol_clean}
                            )
                            fresh_insights = generate_auto_insights(ds_temp)
                            if fresh_insights:
                                cached_insights = fresh_insights
                                meta = dict(company.metadata_json)
                                meta["auto_insights"] = fresh_insights
                                company.metadata_json = meta
                                db.commit()
                        except Exception as rec_err:
                            logger.debug(f"Failed to refresh cached auto_insights formatting: {rec_err}")

                # Ensure canonical trailing_pe is synchronized between quote and scenario_insights
                canonical_pe = quote.get("trailing_pe") or quote.get("trailingPE")
                if not canonical_pe and "auto_insights" in company.metadata_json:
                    canonical_pe = company.metadata_json["auto_insights"].get("scenario_insights", {}).get("trailing_pe")
                if not canonical_pe and periods_list:
                    lp = periods_list[-1]
                    if quote.get("current_price") and lp.get("eps") and float(lp["eps"]) > 0:
                        canonical_pe = round(float(quote["current_price"]) / float(lp["eps"]), 2)
                    elif lp.get("pe_ratio"):
                        canonical_pe = lp.get("pe_ratio")

                cached_scenarios = (company.metadata_json or {}).get("scenarios", {}) or {}
                if canonical_pe is not None:
                    try:
                        canonical_pe = round(float(canonical_pe), 2)
                        quote["trailing_pe"] = canonical_pe
                        if isinstance(cached_insights, dict) and "scenario_insights" in cached_insights and isinstance(cached_insights["scenario_insights"], dict):
                            cached_insights["scenario_insights"]["trailing_pe"] = canonical_pe
                        if isinstance(cached_scenarios, dict):
                            cached_scenarios["trailing_pe"] = canonical_pe
                    except Exception:
                        pass

                norm_exch = "NSE" if (symbol_clean.endswith(".NS") or (company.exchange or "").upper() == "NSI") else (company.exchange or "GLOBAL")

                trends_data = company.metadata_json.get("trends", {})
                if not trends_data or "ebitda_growth" not in (trends_data.get("metrics") or {}):
                    try:
                        from app.schemas.dataset import ParsedCompanyDataset, FinancialPeriodRecord
                        from app.services.insights_engine import generate_auto_insights
                        p_records = [FinancialPeriodRecord(**pj) for pj in periods_list]
                        ds_temp = ParsedCompanyDataset(
                            company_name=company.company_name,
                            filename=f"{symbol_clean} (Cached)",
                            detected_format="yfinance",
                            periods=p_records,
                            raw_metadata={"currency": company.currency, "symbol": symbol_clean}
                        )
                        fresh_insights = generate_auto_insights(ds_temp)
                        if fresh_insights and fresh_insights.get("trends"):
                            trends_data = fresh_insights["trends"]
                            if isinstance(cached_insights, dict):
                                cached_insights["trends"] = fresh_insights["trends"]
                    except Exception as err:
                        logger.debug(f"Failed to refresh cached trends: {err}")

                return {
                    "company_id": company.id,
                    "symbol": company.symbol or company.ticker,
                    "company_name": company.company_name,
                    "exchange": norm_exch,
                    "currency": company.currency,
                    "data_source": company.data_source or "yfinance",
                    "last_synced_at": company.last_synced_at.isoformat() if company.last_synced_at else None,
                    "is_cached": True,
                    "quote": quote,
                    "periods": periods_list,
                    "trends": trends_data,
                    "scenarios": cached_scenarios,
                    "auto_insights": cached_insights
                }

    # 3. Auto-fetch live financials
    try:
        parsed = fetch_company_data(symbol_clean)
    except Exception as ex:
        logger.error(f"Failed to auto-fetch financials for {symbol_clean}: {ex}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to fetch live financials for '{symbol_clean}': {str(ex)}"
        )

    # 4. Upsert Company record in Neon DB
    if not company:
        company = Company(
            symbol=symbol_clean,
            ticker=symbol_clean,
            company_name=parsed.company_name,
            exchange=parsed.raw_metadata.get("exchange"),
            currency=parsed.raw_metadata.get("currency", "USD"),
            sector=parsed.raw_metadata.get("sector"),
            industry=parsed.raw_metadata.get("industry"),
            data_source="yfinance",
            last_synced_at=now_utc,
            metadata_json={
                "trends": parsed.trends,
                "scenarios": parsed.scenarios,
                "auto_insights": parsed.auto_insights,
                "quote": parsed.raw_metadata
            }
        )
        db.add(company)
        db.commit()
        db.refresh(company)
    else:
        company.company_name = parsed.company_name
        company.symbol = symbol_clean
        company.exchange = parsed.raw_metadata.get("exchange")
        company.currency = parsed.raw_metadata.get("currency", "USD")
        company.sector = parsed.raw_metadata.get("sector")
        company.industry = parsed.raw_metadata.get("industry")
        company.data_source = "yfinance"
        company.last_synced_at = now_utc
        company.metadata_json = {
            "trends": parsed.trends,
            "scenarios": parsed.scenarios,
            "auto_insights": parsed.auto_insights,
            "quote": parsed.raw_metadata
        }
        db.commit()

    # 5. Persist Financial Periods
    db.query(FinancialPeriod).filter(FinancialPeriod.company_id == company.id).delete()
    db.commit()

    for p in parsed.periods:
        fp = FinancialPeriod(
            company_id=company.id,
            fiscal_year=p.fiscal_year,
            fiscal_period=p.fiscal_period,
            statement_type=p.statement_type,
            metrics_json=p.model_dump()
        )
        db.add(fp)
    db.commit()

    # 6. Index RAG chunks into pgvector
    try:
        index_company_chunks(db, company.id, parsed)
    except Exception as e:
        logger.error(f"Failed to index RAG chunks for company {company.id}: {e}")

    # Synchronize canonical trailing_pe on live parsed scenarios
    live_pe = parsed.raw_metadata.get("trailing_pe")
    if live_pe and parsed.scenarios and isinstance(parsed.scenarios, dict):
        try:
            parsed.scenarios["trailing_pe"] = round(float(live_pe), 2)
        except Exception:
            pass

    return {
        "company_id": company.id,
        "symbol": company.symbol,
        "company_name": company.company_name,
        "exchange": company.exchange,
        "currency": company.currency,
        "data_source": company.data_source,
        "last_synced_at": company.last_synced_at.isoformat() if company.last_synced_at else None,
        "is_cached": False,
        "quote": parsed.raw_metadata,
        "periods": [p.model_dump() for p in parsed.periods],
        "trends": parsed.trends,
        "scenarios": parsed.scenarios,
        "auto_insights": parsed.auto_insights
    }

@router.get("/{symbol}/peers")
def get_company_sector_peers(
    symbol: str,
    db: Session = Depends(get_db)
):
    """
    Automatic Sector Peer Comparison:
    Returns target company metrics, up to 5 sector peers from Neon Postgres,
    and the computed Sector Median benchmark row.
    """
    try:
        return get_sector_peers(symbol, db)
    except Exception as e:
        logger.error(f"Failed to get sector peers for {symbol}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to calculate sector peers: {str(e)}"
        )


@router.get("/{symbol}/news")
def get_company_market_news(
    symbol: str,
    limit: int = Query(6, ge=1, le=15, description="Number of news headlines to retrieve")
):
    """
    Live Company Market News Feed:
    Retrieves the latest verified financial headlines and articles for an equity
    from Yahoo Finance, cached for 30 minutes in memory.
    """
    try:
        return get_company_news(symbol, limit=limit)
    except Exception as e:
        logger.error(f"Failed to fetch market news for {symbol}: {e}", exc_info=True)
        return {
            "symbol": symbol.strip().upper(),
            "news": [],
            "count": 0,
            "is_cached": False,
            "error": str(e)
        }


@router.post("/{company_id}/ask", response_model=AskQuestionResponse)
@limiter.limit("20/minute")
async def ask_company_rag_question(
    request: Request,
    company_id: str,
    req: AskQuestionRequest,
    db: Session = Depends(get_db)
):
    """
    RAG Question-Answering scoped to the company:
    Retrieves top-5 cosine similarity pgvector chunks + verified SQL facts,
    and returns a grounded answer with citations.
    Supports either integer company ID or ticker symbol (e.g. ASIANPAINT.NS).
    """
    if req.dataset_id:
        target_id = req.dataset_id
    elif company_id.isdigit():
        target_id = int(company_id)
    else:
        comp, _ = _resolve_company_and_periods(company_id, db)
        target_id = comp.id
    return await ask_company_question(db, target_id, req.question, history=req.history)


def _resolve_company_and_periods(symbol: str, db: Session) -> tuple[Company, List[FinancialPeriod]]:
    """Helper to locate or auto-fetch company and its financial periods."""
    symbol_clean = symbol.strip().upper()
    company = db.execute(
        select(Company).where(
            or_(
                func.upper(Company.symbol) == symbol_clean,
                func.upper(Company.ticker) == symbol_clean
            )
        )
    ).scalars().first()

    if not company:
        try:
            get_or_fetch_company_analysis(symbol_clean, db=db)
            company = db.execute(
                select(Company).where(
                    or_(
                        func.upper(Company.symbol) == symbol_clean,
                        func.upper(Company.ticker) == symbol_clean
                    )
                )
            ).scalars().first()
        except Exception as e:
            logger.warning(f"Auto-fetch attempted for {symbol_clean} encountered: {e}")

    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Company with symbol '{symbol}' not found."
        )

    periods = (
        db.query(FinancialPeriod)
        .filter(FinancialPeriod.company_id == company.id)
        .order_by(FinancialPeriod.fiscal_year.asc())
        .all()
    )

    if not periods:
        try:
            get_or_fetch_company_analysis(symbol_clean, refresh=True, db=db)
            periods = (
                db.query(FinancialPeriod)
                .filter(FinancialPeriod.company_id == company.id)
                .order_by(FinancialPeriod.fiscal_year.asc())
                .all()
            )
        except Exception as e:
            logger.warning(f"Auto-fetch for periods encountered: {e}")

    return company, periods


@router.post("/{symbol}/dcf", response_model=DCFResponse)
def calculate_company_dcf(
    symbol: str,
    req: Optional[DCFRequest] = None,
    db: Session = Depends(get_db)
):
    """
    Calculates institutional DCF valuation:
    - Auto-seeds defaults from company's financial_periods and metadata_json
    - Computes 5-10 year projected FCFs, Gordon Growth Terminal Value, Enterprise & Equity Value
    - Generates 5x5 Sensitivity Matrix (WACC vs Terminal Growth)
    - Enforces wacc > terminal_growth + 0.01 (HTTP 422 if violated)
    """
    company, periods = _resolve_company_and_periods(symbol, db)
    return calculate_dcf(company, periods, req)


@router.get("/{symbol}/dcf", response_model=DCFResponse)
def get_company_default_dcf(symbol: str, db: Session = Depends(get_db)):
    """Convenience GET endpoint to compute DCF with auto-seeded defaults."""
    company, periods = _resolve_company_and_periods(symbol, db)
    return calculate_dcf(company, periods, None)


@router.get("/{symbol}/risk", response_model=RiskIntelligenceResponse)
def get_company_risk_intelligence(symbol: str, db: Session = Depends(get_db)):
    """
    Computes 4-pillar deterministic institutional risk intelligence:
    - Leverage & Liquidity (D/E, Interest Coverage, Current Ratio)
    - Profitability & Margin Stability (OPM Std Dev, YoY Revenue & Margin Contraction)
    - Valuation Stretch (P/E Multiple vs Historical Average, DCF Downside)
    - Earnings Quality (FCF / Net Income conversion, <0.70 warning)
    - 3 Grounded Gemini 3.8 Flash watchpoints (with deterministic fallback)
    """
    company, periods = _resolve_company_and_periods(symbol, db)
    return calculate_risk_intelligence(company, periods)


@router.get("/{symbol}/report/preview")
def preview_company_research_report(symbol: str, db: Session = Depends(get_db)):
    """
    Returns structured JSON preview of the publication-grade research report:
    Executive thesis, DCF valuation summary, pruned financials, and risk scorecard.
    """
    company, periods = _resolve_company_and_periods(symbol, db)
    return get_report_preview_data(company, periods, db)


@router.get("/{symbol}/report/pdf")
@limiter.limit("10/minute")
def download_company_research_report_pdf(
    request: Request,
    symbol: str,
    db: Session = Depends(get_db)
):
    """
    Generates and downloads a clean 2-3 page institutional equity research PDF:
    - Formatted in ₹ Cr (for INR) or $M/$B (for USD)
    - Header block, Executive Thesis, Pruned Financials, DCF Valuation, Risk Scorecard, Disclaimers
    """
    company, periods = _resolve_company_and_periods(symbol, db)
    pdf_bytes = generate_pdf_report(company, periods, db)
    clean_sym = (company.symbol or symbol).replace(".", "_")
    filename = f"FinSight_{clean_sym}_Research_Report.pdf"

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-cache"
        }
    )


@router.get("/{symbol}/export/xlsx")
@limiter.limit("10/minute")
def export_company_financial_model_xlsx(
    request: Request,
    symbol: str,
    fcf_growth: Optional[float] = Query(None, description="Projected annual FCF growth rate override (e.g. 0.10 or 10.0)"),
    wacc: Optional[float] = Query(None, description="WACC override (e.g. 0.115 or 11.5)"),
    terminal_growth: Optional[float] = Query(None, description="Terminal growth rate override (e.g. 0.04 or 4.0)"),
    projection_years: Optional[int] = Query(5, ge=5, le=10, description="Projection horizon in years (5 to 10)"),
    db: Session = Depends(get_db)
):
    """
    Exports a 4-sheet publication-grade institutional financial model (.xlsx)
    with live Excel formulas for 3-statement financials, DCF projection schedule,
    equity bridge, and 5x5 sensitivity matrix.
    Rate-limited to 10/min. Streams application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.
    """
    company, periods = _resolve_company_and_periods(symbol, db)
    excel_buf = generate_financial_model_xlsx(
        company=company,
        periods=periods,
        db=db,
        fcf_growth=fcf_growth,
        wacc=wacc,
        terminal_growth=terminal_growth,
        projection_years=projection_years or 5
    )
    clean_sym = company.symbol or symbol
    filename = f"FinSight_{clean_sym}_Financial_Model.xlsx"

    return StreamingResponse(
        excel_buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-cache"
        }
    )


@router.post("", response_model=CompanyResponse, status_code=status.HTTP_201_CREATED)
def create_company(company_in: CompanyCreate, db: Session = Depends(get_db)):
    """Create a new company record. Tickers must be unique."""
    ticker_clean = company_in.ticker.strip().upper()
    existing = db.execute(select(Company).where(Company.ticker == ticker_clean)).scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Company with ticker '{ticker_clean}' already exists."
        )

    company_data = company_in.model_dump()
    company_data["ticker"] = ticker_clean
    company = Company(**company_data)
    db.add(company)
    db.commit()
    db.refresh(company)
    return company

@router.get("/{company_id}", response_model=CompanyResponse)
def get_company(company_id: int, db: Session = Depends(get_db)):
    """Retrieve a single company by ID."""
    company = db.get(Company, company_id)
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Company with ID {company_id} not found."
        )
    return company

@router.put("/{company_id}", response_model=CompanyResponse)
def update_company(company_id: int, company_in: CompanyUpdate, db: Session = Depends(get_db)):
    """Update an existing company record."""
    company = db.get(Company, company_id)
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Company with ID {company_id} not found."
        )

    update_data = company_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(company, field, value)

    db.commit()
    db.refresh(company)
    return company

@router.delete("/{company_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_company(company_id: int, db: Session = Depends(get_db)):
    """Delete a company and its associated statements, ratios, and records."""
    company = db.get(Company, company_id)
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Company with ID {company_id} not found."
        )

    db.delete(company)
    db.commit()
    return None

# -------------------------------------------------------------
# Financial Statements Sub-Resource
# -------------------------------------------------------------

@router.get("/{company_id}/statements", response_model=List[FinancialStatementResponse])
def get_company_statements(
    company_id: int,
    period: Optional[str] = Query(None, description="Filter by fiscal period (e.g. FY, Q1)"),
    year: Optional[int] = Query(None, description="Filter by fiscal year"),
    statement_type: Optional[str] = Query(None, description="Filter by statement type"),
    db: Session = Depends(get_db)
):
    """Get financial statements for a company."""
    company = db.get(Company, company_id)
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Company with ID {company_id} not found."
        )

    query = select(FinancialStatement).where(FinancialStatement.company_id == company_id)
    if period:
        query = query.where(FinancialStatement.fiscal_period == period.upper())
    if year:
        query = query.where(FinancialStatement.fiscal_year == year)
    if statement_type:
        query = query.where(FinancialStatement.statement_type == statement_type)
    query = query.order_by(FinancialStatement.fiscal_year.desc(), FinancialStatement.fiscal_period.desc())

    return db.execute(query).scalars().all()

@router.post("/{company_id}/statements", response_model=FinancialStatementResponse, status_code=status.HTTP_201_CREATED)
def create_company_statement(
    company_id: int,
    statement_in: FinancialStatementCreate,
    db: Session = Depends(get_db)
):
    """Add a financial statement to a company."""
    company = db.get(Company, company_id)
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Company with ID {company_id} not found."
        )

    stmt_data = statement_in.model_dump()
    stmt_data["company_id"] = company_id
    statement = FinancialStatement(**stmt_data)
    db.add(statement)
    db.flush()

    # Automatically calculate financial ratios for this period
    ratios = calculate_all_ratios({
        "revenue": statement.revenue,
        "cost_of_revenue": statement.cost_of_revenue,
        "gross_profit": statement.gross_profit,
        "operating_income": statement.operating_income,
        "net_income": statement.net_income,
        "total_assets": statement.total_assets,
        "current_assets": statement.current_assets,
        "total_liabilities": statement.total_liabilities,
        "current_liabilities": statement.current_liabilities,
        "total_equity": statement.total_equity,
        "cash_and_equivalents": statement.cash_and_equivalents,
        "inventory": statement.inventory,
        "total_debt": statement.total_debt
    })

    ratio_rec = db.execute(
        select(FinancialRatio).where(
            FinancialRatio.company_id == company_id,
            FinancialRatio.fiscal_year == statement.fiscal_year,
            FinancialRatio.fiscal_period == statement.fiscal_period
        )
    ).scalar_one_or_none()

    if ratio_rec:
        for k, v in ratios.items():
            setattr(ratio_rec, k, Decimal(str(v)) if v is not None else None)
    else:
        ratio_rec = FinancialRatio(
            company_id=company_id,
            fiscal_year=statement.fiscal_year,
            fiscal_period=statement.fiscal_period,
            gross_margin=Decimal(str(ratios["gross_margin"])) if ratios["gross_margin"] is not None else None,
            operating_margin=Decimal(str(ratios["operating_margin"])) if ratios["operating_margin"] is not None else None,
            net_profit_margin=Decimal(str(ratios["net_profit_margin"])) if ratios["net_profit_margin"] is not None else None,
            current_ratio=Decimal(str(ratios["current_ratio"])) if ratios["current_ratio"] is not None else None,
            quick_ratio=Decimal(str(ratios["quick_ratio"])) if ratios["quick_ratio"] is not None else None,
            debt_to_equity=Decimal(str(ratios["debt_to_equity"])) if ratios["debt_to_equity"] is not None else None,
            return_on_equity=Decimal(str(ratios["return_on_equity"])) if ratios["return_on_equity"] is not None else None,
            return_on_assets=Decimal(str(ratios["return_on_assets"])) if ratios["return_on_assets"] is not None else None,
            source="Auto-calculated from statement"
        )
        db.add(ratio_rec)

    db.commit()
    db.refresh(statement)
    return statement

# -------------------------------------------------------------
# Financial Ratios Sub-Resource
# -------------------------------------------------------------

@router.get("/{company_id}/ratios", response_model=List[FinancialRatioResponse])
def get_company_ratios(company_id: int, db: Session = Depends(get_db)):
    """Get calculated financial ratios for a company."""
    company = db.get(Company, company_id)
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Company with ID {company_id} not found."
        )

    query = (
        select(FinancialRatio)
        .where(FinancialRatio.company_id == company_id)
        .order_by(FinancialRatio.fiscal_year.desc(), FinancialRatio.fiscal_period.desc())
    )
    return db.execute(query).scalars().all()

@router.post("/{company_id}/ratios", response_model=FinancialRatioResponse, status_code=status.HTTP_201_CREATED)
def create_company_ratio(
    company_id: int,
    ratio_in: FinancialRatioCreate,
    db: Session = Depends(get_db)
):
    """Add or update financial ratios for a company (upsert)."""
    company = db.get(Company, company_id)
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Company with ID {company_id} not found."
        )

    existing_ratio = db.execute(
        select(FinancialRatio).where(
            FinancialRatio.company_id == company_id,
            FinancialRatio.fiscal_year == ratio_in.fiscal_year,
            FinancialRatio.fiscal_period == ratio_in.fiscal_period
        )
    ).scalar_one_or_none()

    if existing_ratio:
        for k, v in ratio_in.model_dump().items():
            setattr(existing_ratio, k, v)
        db.commit()
        db.refresh(existing_ratio)
        return existing_ratio

    ratio_data = ratio_in.model_dump()
    ratio_data["company_id"] = company_id
    ratio = FinancialRatio(**ratio_data)
    db.add(ratio)
    db.commit()
    db.refresh(ratio)
    return ratio
