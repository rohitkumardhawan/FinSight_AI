"""
FinSight AI — Sector Peer Comparison Engine
============================================
Calculates sector-relative valuation multiples, operating margins, returns on equity,
and YoY growth rates for a target company against its top sector peers in Neon Postgres,
including the official Sector Median benchmark row.
"""

from typing import Dict, Any, List, Optional, Tuple
import statistics
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import yfinance as yf
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from app.models.company import Company
from app.models.dataset import FinancialPeriod
from app.financial.metrics import calculate_net_debt, calculate_ev_to_ebitda

logger = logging.getLogger(__name__)

# Fast memory cache for peer comparison payloads (TTL 15 minutes)
_PEER_PAYLOAD_CACHE: Dict[str, Dict[str, Any]] = {}


def _calculate_median(values: List[Optional[float]]) -> Optional[float]:
    """Calculates median for non-null floats."""
    clean = [v for v in values if v is not None and isinstance(v, (int, float))]
    if not clean:
        return None
    return round(float(statistics.median(clean)), 2)


def _fetch_yfinance_peer_info(symbol: str) -> Dict[str, Any]:
    """Pure network fetch for peer info (thread-safe, does not touch DB)."""
    try:
        t = yf.Ticker(symbol)
        info = t.info or {}
        price = info.get("currentPrice") or info.get("regularMarketPrice") or info.get("previousClose")
        market_cap = info.get("marketCap")
        pe_ratio = info.get("trailingPE") or info.get("forwardPE")
        opm = info.get("operatingMargins")
        pm = info.get("profitMargins")
        roe = info.get("returnOnEquity")
        rev_growth = info.get("revenueGrowth")
        ev_to_ebitda = info.get("enterpriseToEbitda")
        ebitda_m = info.get("ebitdaMargins")
        pb = info.get("priceToBook")

        tot_debt_yf = info.get("totalDebt")
        tot_cash_yf = info.get("totalCash")
        yf_ebitda = info.get("ebitda")

        if (price is None or market_cap is None) and hasattr(t, "fast_info"):
            try:
                fi = t.fast_info
                if price is None:
                    price = getattr(fi, "last_price", None) or getattr(fi, "previous_close", None)
                if market_cap is None:
                    market_cap = getattr(fi, "market_cap", None)
            except Exception:
                pass

        if market_cap and yf_ebitda and yf_ebitda > 0:
            nd_yf = calculate_net_debt(tot_debt_yf, tot_cash_yf)
            calc_ev_eb = calculate_ev_to_ebitda(market_cap, nd_yf, yf_ebitda)
            if calc_ev_eb is not None:
                ev_to_ebitda = calc_ev_eb

        return {
            "price": round(float(price), 2) if price is not None else None,
            "market_cap": round(float(market_cap), 2) if market_cap is not None else None,
            "pe_ratio": round(float(pe_ratio), 2) if pe_ratio is not None else None,
            "opm_pct": round(float(opm) * 100, 2) if opm is not None else None,
            "net_margin_pct": round(float(pm) * 100, 2) if pm is not None else None,
            "roe_pct": round(float(roe) * 100, 2) if roe is not None else None,
            "revenue_growth_pct": round(float(rev_growth) * 100, 2) if rev_growth is not None else None,
            "ev_to_ebitda": round(float(ev_to_ebitda), 2) if ev_to_ebitda is not None else None,
            "ebitda_margin_pct": round(float(ebitda_m) * 100, 2) if ebitda_m is not None else None,
            "price_to_book": round(float(pb), 2) if pb is not None else None,
        }
    except Exception as e:
        logger.debug(f"yfinance fetch error for {symbol}: {e}")
        return {}


def _extract_metrics_for_company(company: Company, periods: List[FinancialPeriod]) -> Dict[str, Any]:
    """Extracts comparison metrics from already-queried DB company and its periods."""
    symbol = (company.symbol or company.ticker or "").strip().upper()
    meta = company.metadata_json or {}
    quote = meta.get("quote", {})
    cached = meta.get("peer_metrics")

    now_ts = datetime.now(timezone.utc).timestamp()
    if cached and (now_ts - cached.get("_cached_at", 0)) < 3600 and cached.get("ev_to_ebitda") is not None:
        return {
            "symbol": symbol,
            "name": company.company_name or symbol,
            "price": cached.get("price"),
            "market_cap": cached.get("market_cap"),
            "pe_ratio": cached.get("pe_ratio"),
            "opm_pct": cached.get("opm_pct"),
            "net_margin_pct": cached.get("net_margin_pct"),
            "roe_pct": cached.get("roe_pct"),
            "revenue_growth_pct": cached.get("revenue_growth_pct"),
            "ev_to_ebitda": cached.get("ev_to_ebitda"),
            "ebitda_margin_pct": cached.get("ebitda_margin_pct"),
            "price_to_book": cached.get("price_to_book"),
            "currency": company.currency or ("INR" if symbol.endswith(".NS") else "USD")
        }

    price = quote.get("current_price") or quote.get("regularMarketPrice") or quote.get("previousClose")
    market_cap = quote.get("market_cap") or quote.get("marketCap")
    pe_ratio = quote.get("trailing_pe") or quote.get("trailingPE")
    opm_pct = None
    net_margin_pct = None
    roe_pct = None
    revenue_growth_pct = None
    ev_to_ebitda = quote.get("enterpriseToEbitda")
    ebitda_margin_pct = (quote.get("ebitdaMargins") * 100) if quote.get("ebitdaMargins") is not None else None
    price_to_book = quote.get("priceToBook")

    if periods:
        latest = periods[-1]
        lp = latest.metrics_json or {}
        if not price and lp.get("share_price"):
            price = lp.get("share_price")
        if not pe_ratio and price and lp.get("eps") and float(lp["eps"]) > 0:
            try:
                pe_ratio = round(float(price) / float(lp["eps"]), 2)
            except Exception:
                pass
        if not pe_ratio and lp.get("pe_ratio"):
            pe_ratio = lp.get("pe_ratio")
        if lp.get("opm_pct") is not None:
            opm_pct = lp.get("opm_pct")
        elif lp.get("revenue") and lp.get("operating_income"):
            try:
                opm_pct = round((lp["operating_income"] / lp["revenue"]) * 100, 2)
            except Exception:
                pass

        if lp.get("revenue") and lp.get("net_income"):
            try:
                net_margin_pct = round((lp["net_income"] / lp["revenue"]) * 100, 2)
            except Exception:
                pass

        if lp.get("total_equity") and lp.get("net_income") and lp["total_equity"] > 0:
            try:
                roe_pct = round((lp["net_income"] / lp["total_equity"]) * 100, 2)
            except Exception:
                pass

        # EBITDA and Valuation Multiples from period
        ebitda_val = lp.get("ebitda")
        if ebitda_val is None and (lp.get("operating_income") is not None or lp.get("ebit") is not None):
            op = lp.get("operating_income") if lp.get("operating_income") is not None else lp.get("ebit")
            da = abs(lp.get("depreciation_amortization") or 0.0)
            ebitda_val = op + da

        if ebitda_margin_pct is None and ebitda_val and lp.get("revenue") and lp["revenue"] > 0:
            ebitda_margin_pct = round((ebitda_val / lp["revenue"]) * 100, 2)
        elif lp.get("ebitda_margin_pct") is not None:
            ebitda_margin_pct = lp.get("ebitda_margin_pct")

        # Compute unified Net Debt and EV/EBITDA via shared helper
        nd_calc = calculate_net_debt(lp.get("total_debt"), lp.get("cash_and_equivalents"))
        computed_ev_to_ebitda = calculate_ev_to_ebitda(market_cap, nd_calc, ebitda_val)
        if computed_ev_to_ebitda is not None:
            ev_to_ebitda = computed_ev_to_ebitda
        elif lp.get("ev_to_ebitda") is not None:
            ev_to_ebitda = lp.get("ev_to_ebitda")

        if price_to_book is None and lp.get("price_to_book") is not None:
            price_to_book = lp.get("price_to_book")
        elif price_to_book is None and market_cap and lp.get("total_equity") and lp["total_equity"] > 0:
            price_to_book = round(float(market_cap) / float(lp["total_equity"]), 2)

        if len(periods) >= 2:
            prev = periods[-2]
            pp = prev.metrics_json or {}
            if lp.get("revenue") and pp.get("revenue") and pp["revenue"] > 0:
                try:
                    revenue_growth_pct = round(((lp["revenue"] - pp["revenue"]) / abs(pp["revenue"])) * 100, 2)
                except Exception:
                    pass

    return {
        "symbol": symbol,
        "name": company.company_name or symbol,
        "price": round(float(price), 2) if price is not None else None,
        "market_cap": round(float(market_cap), 2) if market_cap is not None else None,
        "pe_ratio": round(float(pe_ratio), 2) if pe_ratio is not None else None,
        "opm_pct": round(float(opm_pct), 2) if opm_pct is not None else None,
        "net_margin_pct": round(float(net_margin_pct), 2) if net_margin_pct is not None else None,
        "roe_pct": round(float(roe_pct), 2) if roe_pct is not None else None,
        "revenue_growth_pct": round(float(revenue_growth_pct), 2) if revenue_growth_pct is not None else None,
        "ev_to_ebitda": round(float(ev_to_ebitda), 2) if ev_to_ebitda is not None else None,
        "ebitda_margin_pct": round(float(ebitda_margin_pct), 2) if ebitda_margin_pct is not None else None,
        "price_to_book": round(float(price_to_book), 2) if price_to_book is not None else None,
        "currency": company.currency or ("INR" if symbol.endswith(".NS") else "USD")
    }


def _is_sub_industry_match(target_ind: str, cand_ind: str, target_sym: str, cand_sym: str, cand_name: str) -> bool:
    """Checks granular sub-industry match (e.g. Asset Management/Wealth or Paints/Specialty Chemicals)."""
    t_ind = (target_ind or "").lower()
    c_ind = (cand_ind or "").lower()
    c_name = (cand_name or "").lower()

    if t_ind and c_ind and t_ind == c_ind and t_ind != "general":
        return True

    # Asset Management / Wealth matching (e.g. 360ONE, HDFCAMC, ANANDRATHI, ABSLAMC)
    if any(k in t_ind for k in ["asset management", "wealth", "amc"]) or "360ONE" in target_sym:
        if any(k in c_ind for k in ["asset management", "wealth", "amc"]) or any(k in c_name for k in ["asset management", "wealth", "amc"]):
            return True
        if any(s in cand_sym for s in ["HDFCAMC", "ABSLAMC", "ANANDRATHI", "ICICIAMC", "NAM-INDIA", "MOTILALOFS", "UTIAMC"]):
            return True

    # Paints / Coatings / Specialty Chemicals matching (e.g. ASIANPAINT, BERGEPAINT, KANSAINER)
    if any(k in t_ind for k in ["paint", "coating", "specialty chemical"]) or "PAINT" in target_sym:
        if any(k in c_ind for k in ["paint", "coating", "specialty chemical"]) or any(k in c_name for k in ["paint", "coating"]):
            return True
        if any(s in cand_sym for s in ["BERGEPAINT", "KANSAINER", "AKZOINDIA", "INDIGOPNTS", "PIDILITIND", "GRASIM"]):
            return True

    return False


def get_sector_peers(symbol: str, db: Session) -> Dict[str, Any]:
    """
    Main entry point for Sector Peer Comparison:
    1. Finds target company in DB.
    2. Identifies its sector and granular sub-industry.
    3. Ranks candidates strictly within the same currency:
       Priority 1: Granular sub-industry match first, then same sector.
       Priority 2: Prefer peers with populated financials (non-null P/E, OPM, ROE).
       Priority 3: Closest Market Capitalization (ABS(peer.market_cap - active.market_cap) ASC).
       NEVER sorted alphabetically!
    4. Computes target and peer metrics including EV/EBITDA, EBITDA Margin %, and P/B.
    5. Calculates Sector Median row across all returned companies.
    """
    clean_sym = symbol.strip().upper()
    now_ts = datetime.now(timezone.utc).timestamp()

    # Fast in-memory cache check
    if clean_sym in _PEER_PAYLOAD_CACHE:
        cache_entry = _PEER_PAYLOAD_CACHE[clean_sym]
        if (now_ts - cache_entry.get("_cached_at", 0)) < 900:  # 15 minutes TTL
            return cache_entry["data"]

    # 1. Look up target company
    target_orm = db.query(Company).filter(
        or_(
            func.upper(Company.symbol) == clean_sym,
            func.upper(Company.ticker) == clean_sym
        )
    ).first()

    if not target_orm:
        from app.services.auto_fetcher import fetch_company_data
        try:
            ds = fetch_company_data(clean_sym)
            target_orm = Company(
                symbol=clean_sym,
                ticker=clean_sym,
                company_name=ds.company_name,
                exchange=ds.raw_metadata.get("exchange"),
                currency=ds.raw_metadata.get("currency", "INR" if clean_sym.endswith(".NS") else "USD"),
                sector=ds.raw_metadata.get("sector") or ("Basic Materials" if "ASIANPAINT" in clean_sym else "General"),
                industry=ds.raw_metadata.get("industry") or ("Specialty Chemicals" if "ASIANPAINT" in clean_sym else "General"),
                metadata_json={"quote": ds.raw_metadata}
            )
            db.add(target_orm)
            db.commit()
            db.refresh(target_orm)
        except Exception as e:
            logger.warning(f"Failed to auto-fetch company for peer lookup: {e}")
            target_orm = Company(
                symbol=clean_sym,
                ticker=clean_sym,
                company_name=clean_sym,
                currency="INR" if clean_sym.endswith(".NS") else "USD",
                sector="Basic Materials" if "ASIANPAINT" in clean_sym else "General",
                industry="Specialty Chemicals" if "ASIANPAINT" in clean_sym else "General"
            )

    # 2. Determine Sector, Industry and Currency
    target_currency = (target_orm.currency or ("INR" if clean_sym.endswith(".NS") else "USD")).strip().upper()
    target_meta = target_orm.metadata_json or {}
    target_quote = target_meta.get("quote", {})
    target_pm = target_meta.get("peer_metrics", {})

    if "ASIANPAINT" in clean_sym:
        if target_orm.sector != "Basic Materials" or target_orm.industry != "Specialty Chemicals":
            target_orm.sector = "Basic Materials"
            target_orm.industry = "Specialty Chemicals"
            if target_orm.company_name == "ASIANPAINT.NS":
                target_orm.company_name = "Asian Paints Limited"
            db.commit()
    elif "360ONE" in clean_sym:
        if target_orm.sector != "Financial Services" or target_orm.industry != "Asset Management":
            target_orm.sector = "Financial Services"
            target_orm.industry = "Asset Management"
            db.commit()

    sector = target_quote.get("sector") or target_orm.sector or "General"
    industry = target_quote.get("industry") or target_orm.industry or "General"

    target_mcap = target_pm.get("market_cap") or target_quote.get("market_cap") or target_quote.get("marketCap")
    if not target_mcap:
        try:
            t_obj = yf.Ticker(clean_sym)
            if hasattr(t_obj, "fast_info") and getattr(t_obj.fast_info, "market_cap", None):
                target_mcap = float(t_obj.fast_info.market_cap)
        except Exception:
            pass

    # 3. Seed domain-specific flagship peers if missing from DB
    if ("ASIANPAINT" in clean_sym or "PAINT" in clean_sym):
        for candidate_sym in ["BERGEPAINT.NS", "KANSAINER.NS", "PIDILITIND.NS", "GRASIM.NS", "INDIGOPNTS.NS"]:
            if candidate_sym == clean_sym:
                continue
            cand_comp = db.query(Company).filter(func.upper(Company.symbol) == candidate_sym).first()
            if not cand_comp:
                try:
                    from app.services.auto_fetcher import fetch_company_data
                    ds = fetch_company_data(candidate_sym)
                    cand_comp = Company(
                        symbol=candidate_sym,
                        ticker=candidate_sym,
                        company_name=ds.company_name,
                        exchange="NSE",
                        currency="INR",
                        sector="Basic Materials",
                        industry="Specialty Chemicals",
                        metadata_json={"quote": ds.raw_metadata}
                    )
                    db.add(cand_comp)
                    db.commit()
                except Exception as e:
                    logger.debug(f"Could not seed peer {candidate_sym}: {e}")
            elif cand_comp.sector != "Basic Materials" or cand_comp.industry != "Specialty Chemicals":
                cand_comp.sector = "Basic Materials"
                cand_comp.industry = "Specialty Chemicals"
                db.commit()

    if ("360ONE" in clean_sym or "WEALTH" in clean_sym or "AMC" in clean_sym or industry == "Asset Management"):
        for candidate_sym in ["HDFCAMC.NS", "ANANDRATHI.NS", "ABSLAMC.NS", "NAM-INDIA.NS", "MOTILALOFS.NS", "ICICIAMC.NS"]:
            if candidate_sym == clean_sym:
                continue
            cand_comp = db.query(Company).filter(func.upper(Company.symbol) == candidate_sym).first()
            if not cand_comp:
                try:
                    from app.services.auto_fetcher import fetch_company_data
                    ds = fetch_company_data(candidate_sym)
                    cand_comp = Company(
                        symbol=candidate_sym,
                        ticker=candidate_sym,
                        company_name=ds.company_name,
                        exchange="NSE",
                        currency="INR",
                        sector="Financial Services",
                        industry="Asset Management",
                        metadata_json={"quote": ds.raw_metadata}
                    )
                    db.add(cand_comp)
                    db.commit()
                except Exception as e:
                    logger.debug(f"Could not seed peer {candidate_sym}: {e}")

    if target_currency == "USD":
        for candidate_sym in ["MSFT", "GOOGL", "NVDA", "AMZN", "META"]:
            if candidate_sym == clean_sym:
                continue
            cand_comp = db.query(Company).filter(
                func.upper(Company.symbol) == candidate_sym,
                func.upper(Company.currency) == "USD"
            ).first()
            if not cand_comp:
                try:
                    from app.services.auto_fetcher import fetch_company_data
                    ds = fetch_company_data(candidate_sym)
                    cand_comp = Company(
                        symbol=candidate_sym,
                        ticker=candidate_sym,
                        company_name=ds.company_name,
                        exchange=ds.raw_metadata.get("exchange", "NASDAQ"),
                        currency="USD",
                        sector=ds.raw_metadata.get("sector", "Technology"),
                        industry=ds.raw_metadata.get("industry", "Consumer Electronics"),
                        metadata_json={"quote": ds.raw_metadata}
                    )
                    db.add(cand_comp)
                    db.commit()
                except Exception as e:
                    logger.debug(f"Could not seed USD peer {candidate_sym}: {e}")

    # 4. Query all candidate peers within exact same currency
    all_candidates = db.query(Company).filter(
        Company.id != target_orm.id,
        func.upper(Company.symbol) != clean_sym,
        func.upper(Company.ticker) != clean_sym,
        func.upper(Company.currency) == target_currency
    ).all()

    # Priority Ranking Function
    def _rank_candidate(c: Company) -> Tuple[int, int, float]:
        sym = (c.symbol or c.ticker or "").upper()
        name = c.company_name or ""
        c_meta = c.metadata_json or {}
        c_quote = c_meta.get("quote", {})
        c_pm = c_meta.get("peer_metrics", {})

        c_ind = c_quote.get("industry") or c.industry or ""
        c_sec = c_quote.get("sector") or c.sector or ""

        # Priority 1: Sub-industry match (0) vs Sector match (1) vs Other (2)
        if _is_sub_industry_match(industry, c_ind, clean_sym, sym, name):
            ind_score = 0
        elif (sector and c_sec and sector.lower() in c_sec.lower()) or (sector and c_ind and sector.lower() in c_ind.lower()):
            ind_score = 1
        else:
            ind_score = 2

        # Priority 2: Populated financials (0 if has P/E and OPM, 1 otherwise)
        has_fin = bool(
            (c_pm.get("pe_ratio") is not None or c_quote.get("trailing_pe") is not None or c_quote.get("trailingPE") is not None) and
            (c_pm.get("opm_pct") is not None or c_quote.get("operatingMargins") is not None)
        )
        fin_score = 0 if has_fin else 1

        # Priority 3: Market Cap Proximity (closest to target market cap)
        cand_mcap = c_pm.get("market_cap") or c_quote.get("market_cap") or c_quote.get("marketCap")
        if cand_mcap and target_mcap:
            mcap_diff = abs(float(cand_mcap) - float(target_mcap))
        elif cand_mcap:
            mcap_diff = 1e16 - float(cand_mcap)
        else:
            mcap_diff = 1e18

        return (ind_score, fin_score, mcap_diff)

    ranked_candidates = sorted(all_candidates, key=_rank_candidate)
    selected_peers: List[Company] = ranked_candidates[:5]

    all_companies = [target_orm] + selected_peers
    comp_ids = [c.id for c in all_companies]

    # Pre-fetch periods for all selected companies
    all_periods = db.query(FinancialPeriod).filter(
        FinancialPeriod.company_id.in_(comp_ids),
        FinancialPeriod.statement_type.in_(["annual_combined", "annual"])
    ).order_by(FinancialPeriod.fiscal_year.asc()).all()

    periods_by_comp: Dict[int, List[FinancialPeriod]] = {}
    for p in all_periods:
        periods_by_comp.setdefault(p.company_id, []).append(p)

    # Extract metrics from DB first
    initial_metrics: List[Dict[str, Any]] = []
    need_yf_symbols: List[str] = []

    for comp in all_companies:
        m = _extract_metrics_for_company(comp, periods_by_comp.get(comp.id, []))
        initial_metrics.append(m)
        if any(m.get(k) is None for k in ["price", "market_cap", "pe_ratio", "opm_pct", "net_margin_pct", "roe_pct", "revenue_growth_pct", "ev_to_ebitda", "ebitda_margin_pct", "price_to_book"]):
            need_yf_symbols.append(m["symbol"])

    # Concurrent yfinance fetch only for missing metrics
    if need_yf_symbols:
        with ThreadPoolExecutor(max_workers=min(len(need_yf_symbols), 6)) as executor:
            yf_results = list(executor.map(_fetch_yfinance_peer_info, need_yf_symbols))

        yf_map = dict(zip(need_yf_symbols, yf_results))
        for m in initial_metrics:
            sym = m["symbol"]
            if sym in yf_map:
                yf_data = yf_map[sym]
                for key in ["price", "market_cap", "pe_ratio", "opm_pct", "net_margin_pct", "roe_pct", "revenue_growth_pct", "ev_to_ebitda", "ebitda_margin_pct", "price_to_book"]:
                    if m.get(key) is None and yf_data.get(key) is not None:
                        m[key] = yf_data[key]

    # Save to company metadata_json for fast reuse
    try:
        metrics_by_sym = {m["symbol"]: m for m in initial_metrics}
        for comp in all_companies:
            sym = (comp.symbol or comp.ticker or "").strip().upper()
            if sym in metrics_by_sym:
                m_data = metrics_by_sym[sym]
                meta_dict = dict(comp.metadata_json or {})
                meta_dict["peer_metrics"] = {**m_data, "_cached_at": now_ts}
                comp.metadata_json = meta_dict
        db.commit()
    except Exception as db_e:
        logger.debug(f"Failed saving peer metrics cache to DB: {db_e}")

    target_metrics = initial_metrics[0]
    peer_metrics_list = initial_metrics[1:]

    # 5. Compute Sector Median across target and all peers
    all_metrics = [target_metrics] + peer_metrics_list
    sector_median = {
        "symbol": "MEDIAN",
        "name": f"{sector} Sector Median",
        "price": _calculate_median([m.get("price") for m in all_metrics]),
        "market_cap": _calculate_median([m.get("market_cap") for m in all_metrics]),
        "pe_ratio": _calculate_median([m.get("pe_ratio") for m in all_metrics]),
        "opm_pct": _calculate_median([m.get("opm_pct") for m in all_metrics]),
        "net_margin_pct": _calculate_median([m.get("net_margin_pct") for m in all_metrics]),
        "roe_pct": _calculate_median([m.get("roe_pct") for m in all_metrics]),
        "revenue_growth_pct": _calculate_median([m.get("revenue_growth_pct") for m in all_metrics]),
        "ev_to_ebitda": _calculate_median([m.get("ev_to_ebitda") for m in all_metrics]),
        "ebitda_margin_pct": _calculate_median([m.get("ebitda_margin_pct") for m in all_metrics]),
        "price_to_book": _calculate_median([m.get("price_to_book") for m in all_metrics]),
        "currency": target_metrics.get("currency", "INR")
    }

    result = {
        "target": target_metrics,
        "peers": peer_metrics_list,
        "sector_median": sector_median,
        "sector": sector,
        "count": len(peer_metrics_list) + 1
    }

    _PEER_PAYLOAD_CACHE[clean_sym] = {"data": result, "_cached_at": now_ts}
    return result
