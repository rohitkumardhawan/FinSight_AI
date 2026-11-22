"""
FinSight AI — Live Company Market News Engine
=============================================
Fetches, normalizes, and caches real-time financial market news and headlines
for a company via Yahoo Finance with a 30-minute in-memory cache and graceful fallback.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
import logging
import yfinance as yf

logger = logging.getLogger(__name__)

# Fast in-memory cache for news: { symbol: { "data": [...], "cached_at": float } }
_NEWS_CACHE: Dict[str, Dict[str, Any]] = {}
CACHE_TTL_SECONDS = 30 * 60  # 30 minutes


def _format_timestamp(raw_date: Any) -> str:
    """Safely normalizes various timestamp formats into a clean ISO-8601 string."""
    if not raw_date:
        return datetime.now(timezone.utc).isoformat()
    if isinstance(raw_date, (int, float)):
        try:
            return datetime.fromtimestamp(raw_date, tz=timezone.utc).isoformat()
        except Exception:
            return str(raw_date)
    return str(raw_date)


def get_company_news(symbol: str, limit: int = 6) -> Dict[str, Any]:
    """
    Fetches the latest financial headlines for a company symbol.
    Returns:
    {
        "symbol": "ASIANPAINT.NS",
        "news": [
            {
                "id": "...",
                "title": "...",
                "publisher": "Reuters",
                "link": "https://...",
                "published_at": "2026-07-29T14:31:25Z",
                "summary": "...",
                "thumbnail": "https://..."
            },
            ...
        ],
        "count": 6,
        "is_cached": bool
    }
    """
    clean_sym = symbol.strip().upper()
    now_ts = datetime.now(timezone.utc).timestamp()

    # 1. Check in-memory cache
    if clean_sym in _NEWS_CACHE:
        cache_entry = _NEWS_CACHE[clean_sym]
        if (now_ts - cache_entry.get("cached_at", 0)) < CACHE_TTL_SECONDS:
            return {
                "symbol": clean_sym,
                "news": cache_entry["data"][:limit],
                "count": len(cache_entry["data"][:limit]),
                "is_cached": True
            }

    # 2. Fetch live headlines via yfinance
    normalized_news: List[Dict[str, Any]] = []
    try:
        ticker = yf.Ticker(clean_sym)
        raw_news = getattr(ticker, "news", []) or []

        for item in raw_news:
            if not isinstance(item, dict):
                continue

            # Support modern yfinance content dict structure
            content = item.get("content") if isinstance(item.get("content"), dict) else item

            title = content.get("title")
            if not title:
                continue

            # Publisher resolution
            provider = content.get("provider")
            if isinstance(provider, dict):
                publisher = provider.get("displayName") or provider.get("name") or "Market News"
            else:
                publisher = content.get("publisher") or item.get("publisher") or "Financial Wire"

            # URL resolution
            click_url = content.get("clickThroughUrl")
            canonical_url = content.get("canonicalUrl")
            link = ""
            if isinstance(click_url, dict) and click_url.get("url"):
                link = click_url["url"]
            elif isinstance(canonical_url, dict) and canonical_url.get("url"):
                link = canonical_url["url"]
            else:
                link = content.get("link") or item.get("link") or f"https://finance.yahoo.com/quote/{clean_sym}"

            # Published timestamp
            pub_date = (
                content.get("pubDate")
                or content.get("displayTime")
                or content.get("providerPublishTime")
                or item.get("providerPublishTime")
            )
            published_at = _format_timestamp(pub_date)

            # Summary snippet
            summary = content.get("summary") or content.get("description")

            # Thumbnail image if present
            thumb_obj = content.get("thumbnail")
            thumbnail_url = None
            if isinstance(thumb_obj, dict):
                thumbnail_url = thumb_obj.get("originalUrl")
                if not thumbnail_url and isinstance(thumb_obj.get("resolutions"), list) and thumb_obj["resolutions"]:
                    thumbnail_url = thumb_obj["resolutions"][0].get("url")

            news_id = content.get("id") or item.get("id") or f"{clean_sym}-{len(normalized_news)}"

            normalized_news.append({
                "id": str(news_id),
                "title": title.strip(),
                "publisher": publisher.strip(),
                "link": link.strip(),
                "published_at": published_at,
                "summary": summary.strip() if summary else None,
                "thumbnail": thumbnail_url
            })

            if len(normalized_news) >= limit:
                break

    except Exception as ex:
        logger.warning(f"Failed to fetch market news for {clean_sym}: {ex}")

    # 3. Store in cache (even if empty, to avoid spamming external services on cold symbols)
    _NEWS_CACHE[clean_sym] = {
        "data": normalized_news,
        "cached_at": now_ts
    }

    return {
        "symbol": clean_sym,
        "news": normalized_news[:limit],
        "count": len(normalized_news[:limit]),
        "is_cached": False
    }
