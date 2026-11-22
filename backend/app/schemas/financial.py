from typing import List, Optional
from pydantic import BaseModel, Field

class MetricCard(BaseModel):
    label: str
    value: str
    change: str
    is_positive: bool
    subtext: str
    is_demo_data: bool = True

class ChartDataPoint(BaseModel):
    period: str
    revenue: float
    gross_profit: float
    net_income: float
    is_demo_data: bool = True

class CompanyOverview(BaseModel):
    ticker: str
    name: str
    sector: str
    industry: str
    price: float
    change_percent: float
    market_cap: str
    pe_ratio: Optional[float] = None
    ev_ebitda: Optional[float] = None
    fcf_yield: Optional[str] = None
    roe: Optional[str] = None
    summary: str
    is_demo_data: bool = True

class ResearchNote(BaseModel):
    id: str
    title: str
    ticker: str
    analyst: str
    date: str
    sentiment: str  # Bullish, Neutral, Bearish
    target_price: str
    summary: str
    is_demo_data: bool = True

class DashboardData(BaseModel):
    company: CompanyOverview
    kpis: List[MetricCard]
    revenue_trend: List[ChartDataPoint]
    recent_research: List[ResearchNote]
    data_disclaimer: str = "DEMONSTRATION DATA ONLY — Not financial advice"
