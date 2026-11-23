"""
FinSight AI — Dataset & Financial Period Pydantic Schemas
=========================================================
Unified canonical schema for parsed financial datasets, period records,
deterministic automated insights, and Gemini RAG payloads.
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from datetime import datetime


class FinancialPeriodRecord(BaseModel):
    """Canonical model for a single financial reporting period."""
    fiscal_year: Optional[int] = None
    fiscal_period: str = "FY"  # 'FY', 'TTM', 'Best Case', 'Worst Case', 'Q1', etc.
    statement_type: str = "annual_combined"
    
    # Income Statement metrics
    revenue: Optional[float] = None
    cost_of_revenue: Optional[float] = None
    gross_profit: Optional[float] = None
    operating_expenses: Optional[float] = None
    operating_income: Optional[float] = None
    other_income: Optional[float] = None
    ebit: Optional[float] = None
    depreciation_amortization: Optional[float] = None
    ebitda: Optional[float] = None
    ebitda_margin_pct: Optional[float] = None
    interest_expense: Optional[float] = None
    profit_before_tax: Optional[float] = None
    tax_expense: Optional[float] = None
    tax_rate_pct: Optional[float] = None
    net_income: Optional[float] = None
    eps: Optional[float] = None
    
    # Market & Valuation metrics
    pe_ratio: Optional[float] = None
    share_price: Optional[float] = None
    dividend_payout_pct: Optional[float] = None
    opm_pct: Optional[float] = None
    ev_to_ebitda: Optional[float] = None
    price_to_book: Optional[float] = None
    debt_to_ebitda: Optional[float] = None
    roce_pct: Optional[float] = None
    fcf_yield_pct: Optional[float] = None
    
    # Balance Sheet metrics
    total_assets: Optional[float] = None
    current_assets: Optional[float] = None
    cash_and_equivalents: Optional[float] = None
    receivables: Optional[float] = None
    inventory: Optional[float] = None
    other_current_assets: Optional[float] = None
    net_ppe: Optional[float] = None
    investments: Optional[float] = None
    other_non_current_assets: Optional[float] = None
    non_current_assets: Optional[float] = None
    total_liabilities: Optional[float] = None
    current_liabilities: Optional[float] = None
    trade_payables: Optional[float] = None
    total_debt: Optional[float] = None
    other_liabilities: Optional[float] = None
    total_equity: Optional[float] = None
    net_debt: Optional[float] = None
    net_working_capital: Optional[float] = None
    invested_capital: Optional[float] = None
    
    # Cash Flow metrics
    operating_cash_flow: Optional[float] = None
    capital_expenditure: Optional[float] = None
    investing_cash_flow: Optional[float] = None
    financing_cash_flow: Optional[float] = None
    net_change_in_cash: Optional[float] = None
    free_cash_flow: Optional[float] = None
    
    # Metadata
    source: Optional[str] = None
    custom_metrics: Dict[str, Any] = Field(default_factory=dict)


class ParsedCompanyDataset(BaseModel):
    """Unified dataset parsed from Screener.in or FinSight Combined formats."""
    company_name: str
    filename: str
    detected_format: str  # 'screener_csv' or 'finsight_combined_csv'
    periods: List[FinancialPeriodRecord] = Field(default_factory=list)
    trends: Optional[Dict[str, Any]] = None
    scenarios: Optional[Dict[str, Any]] = None
    raw_metadata: Dict[str, Any] = Field(default_factory=dict)
    auto_insights: Optional[Dict[str, Any]] = None


class DatasetSummaryResponse(BaseModel):
    """Brief dataset summary for dataset list views."""
    id: int
    company_name: str
    filename: str
    detected_format: str
    source: str
    period_count: int
    created_at: datetime

    class Config:
        from_attributes = True


class DatasetDetailResponse(BaseModel):
    """Full dataset payload for dashboard hydration."""
    id: int
    company_name: str
    filename: str
    detected_format: str
    source: str
    period_count: int
    created_at: datetime
    metadata_json: Optional[Dict[str, Any]] = None
    periods: List[Dict[str, Any]] = Field(default_factory=list)
    auto_insights: Optional[Dict[str, Any]] = None

    class Config:
        from_attributes = True


class AskQuestionRequest(BaseModel):
    """Payload for RAG question answering."""
    dataset_id: Optional[int] = None
    question: str
    history: Optional[List[Dict[str, Any]]] = Field(default_factory=list)


class CitationItem(BaseModel):
    """Citation chip linking grounded answer to source section or period."""
    source_ref: str
    chunk_type: str
    snippet: str


class AskQuestionResponse(BaseModel):
    """Grounded AI answer with citations."""
    answer: str
    dataset_id: int
    company_name: str
    model: str
    citations: List[CitationItem] = Field(default_factory=list)
    ai_mode: str = "live"  # "live" or "fallback"
