from fastapi import APIRouter, Query
from typing import List, Dict

router = APIRouter()

COMPANIES = [
    {"ticker": "AAPL", "name": "Apple Inc.", "sector": "Technology", "industry": "Consumer Electronics", "market_cap": "$3.54T"},
    {"ticker": "NVDA", "name": "NVIDIA Corporation", "sector": "Technology", "industry": "Semiconductors", "market_cap": "$3.48T"},
    {"ticker": "MSFT", "name": "Microsoft Corporation", "sector": "Technology", "industry": "Software & Cloud", "market_cap": "$3.15T"},
    {"ticker": "GOOGL", "name": "Alphabet Inc.", "sector": "Communication Services", "industry": "Internet Media", "market_cap": "$2.12T"},
    {"ticker": "AMZN", "name": "Amazon.com, Inc.", "sector": "Consumer Cyclical", "industry": "E-Commerce & Cloud", "market_cap": "$2.10T"},
    {"ticker": "TSLA", "name": "Tesla, Inc.", "sector": "Consumer Cyclical", "industry": "Automotive & Energy", "market_cap": "$840B"},
    {"ticker": "JPM", "name": "JPMorgan Chase & Co.", "sector": "Financial Services", "industry": "Diversified Banking", "market_cap": "$670B"},
    {"ticker": "BRK.B", "name": "Berkshire Hathaway Inc.", "sector": "Financial Services", "industry": "Conglomerate", "market_cap": "$980B"}
]

@router.get("/companies")
async def search_companies(q: str = Query(default="", description="Search ticker or name")):
    query = q.strip().upper()
    if not query:
        return {"companies": COMPANIES, "is_demo_data": True}
    
    matches = [
        c for c in COMPANIES 
        if query in c["ticker"] or query in c["name"].upper() or query in c["sector"].upper()
    ]
    return {"companies": matches, "is_demo_data": True}
