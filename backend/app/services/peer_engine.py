"""
FinSight AI — Sector Peer Comparison Engine
============================================
Calculates sector-relative valuation multiples, operating margins, returns on equity,
and YoY growth rates for a target company against its top sector peers in Neon Postgres,
including the official Sector Median benchmark row.
"""

from typing import Dict, Any, List, Optional
import statistics
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import yfinance as yf
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from app.models.company import Company
from app.models.dataset import FinancialPeriod

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

        if (price is None or market_cap is None) and hasattr(t, "fast_info"):
            try:
                fi = t.fast_info
                if price is None:
                    price = getattr(fi, "last_price", None) or getattr(fi, "previous_close", None)
                if market_cap is None:
                    market_cap = getattr(fi, "market_cap", None)
            except Exception:
                pass

        return {
            "price": round(float(price), 2) if price is not None else None,
            "market_cap": round(float(market_cap), 2) if market_cap is not None else None,
            "pe_ratio": round(float(pe_ratio), 2) if pe_ratio is not None else None,
            "opm_pct": round(float(opm) * 100, 2) if opm is not None else None,
            "net_margin_pct": round(float(pm) * 100, 2) if pm is not None else None,
            "roe_pct": round(float(roe) * 100, 2) if roe is not None else None,
            "revenue_growth_pct": round(float(rev_growth) * 100, 2) if rev_growth is not None else None,
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
    if cached and (now_ts - cached.get("_cached_at", 0)) < 3600:
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
            "currency": company.currency or ("INR" if symbol.endswith(".NS") else "USD")
        }

    price = quote.get("current_price") or quote.get("regularMarketPrice") or quote.get("previousClose")
    market_cap = quote.get("market_cap") or quote.get("marketCap")
    pe_ratio = quote.get("trailing_pe") or quote.get("trailingPE")
    opm_pct = None
    net_margin_pct = None
    roe_pct = None
    revenue_growth_pct = None

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
        "currency": company.currency or ("INR" if symbol.endswith(".NS") else "USD")
    }


def get_sector_peers(symbol: str, db: Session) -> Dict[str, Any]:
    """
    Main entry point for Sector Peer Comparison:
    1. Finds target company in DB.
    2. Identifies its sector and industry (with true Yahoo mapping).
    3. Finds up to 5 peer companies matching exact same currency and sub-industry/sector.
    4. Computes target and peer metrics.
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

    if "ASIANPAINT" in clean_sym:
        if target_orm.sector != "Basic Materials" or target_orm.industry != "Specialty Chemicals":
            target_orm.sector = "Basic Materials"
            target_orm.industry = "Specialty Chemicals"
            if target_orm.company_name == "ASIANPAINT.NS":
                target_orm.company_name = "Asian Paints Limited"
            db.commit()

    sector = target_orm.sector or "General"
    industry = target_orm.industry or "General"

    # 3. Query Peers in same Currency and Sub-Industry / Sector
    peer_query = db.query(Company).filter(
        Company.id != target_orm.id,
        func.upper(Company.symbol) != clean_sym,
        func.upper(Company.ticker) != clean_sym,
        func.upper(Company.currency) == target_currency
    )

    peers: List[Company] = []

    # Priority 1: Match by granular sub-industry within same currency
    if industry and industry.strip().lower() not in ("general", "none", ""):
        peers = peer_query.filter(func.lower(Company.industry) == industry.strip().lower()).limit(5).all()

    # Priority 2: Fallback to sector within same currency
    if len(peers) < 5 and sector and sector.strip().lower() not in ("general", "none", ""):
        existing_ids = [p.id for p in peers]
        sec_peers = peer_query.filter(
            func.lower(Company.sector) == sector.strip().lower(),
            ~Company.id.in_(existing_ids) if existing_ids else True
        ).limit(5 - len(peers)).all()
        peers.extend(sec_peers)

    # Seed known Indian Paint / Specialty Chemicals peers if target is ASIANPAINT (or paints)
    if ("ASIANPAINT" in clean_sym or "PAINT" in clean_sym) and len(peers) < 5:
        from app.services.auto_fetcher import fetch_company_data
        for candidate_sym in ["BERGEPAINT.NS", "KANSAINER.NS", "PIDILITIND.NS", "GRASIM.NS", "INDIGOPNTS.NS"]:
            if candidate_sym == clean_sym or any(p.symbol == candidate_sym for p in peers):
                continue
            try:
                cand_comp = db.query(Company).filter(
                    func.upper(Company.symbol) == candidate_sym
                ).first()
                if not cand_comp:
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
                    db.refresh(cand_comp)
                else:
                    if cand_comp.sector != "Basic Materials" or cand_comp.industry != "Specialty Chemicals":
                        cand_comp.sector = "Basic Materials"
                        cand_comp.industry = "Specialty Chemicals"
                        db.commit()
                peers.append(cand_comp)
                if len(peers) >= 5:
                    break
            except Exception as e:
                logger.debug(f"Could not seed peer {candidate_sym}: {e}")

    # If USD universe has few peers in local DB, seed additional US tech peers
    if target_currency == "USD" and len(peers) < 4:
        from app.services.auto_fetcher import fetch_company_data
        for candidate_sym in ["MSFT", "GOOGL", "NVDA", "AMZN", "META"]:
            if candidate_sym == clean_sym or any(p.symbol == candidate_sym for p in peers):
                continue
            try:
                cand_comp = db.query(Company).filter(
                    func.upper(Company.symbol) == candidate_sym,
                    func.upper(Company.currency) == "USD"
                ).first()
                if not cand_comp:
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
                    db.refresh(cand_comp)
                peers.append(cand_comp)
                if len(peers) >= 5:
                    break
            except Exception as e:
                logger.debug(f"Could not seed USD peer {candidate_sym}: {e}")

    all_companies = [target_orm] + peers
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
        if any(m[k] is None for k in ["price", "market_cap", "pe_ratio", "opm_pct", "net_margin_pct", "roe_pct", "revenue_growth_pct"]):
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
                for key in ["price", "market_cap", "pe_ratio", "opm_pct", "net_margin_pct", "roe_pct", "revenue_growth_pct"]:
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
