from datetime import datetime
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field

class FinancialStatementBase(BaseModel):
    fiscal_year: int = Field(..., ge=1900, le=2100)
    fiscal_period: str = Field(..., max_length=10, description="e.g. FY, Q1, Q2, Q3, Q4")
    statement_type: str = Field(..., max_length=50, description="e.g. income_statement, balance_sheet, cash_flow, combined")
    revenue: Optional[Decimal] = None
    cost_of_revenue: Optional[Decimal] = None
    gross_profit: Optional[Decimal] = None
    operating_income: Optional[Decimal] = None
    ebit: Optional[Decimal] = None
    net_income: Optional[Decimal] = None
    total_assets: Optional[Decimal] = None
    current_assets: Optional[Decimal] = None
    total_liabilities: Optional[Decimal] = None
    current_liabilities: Optional[Decimal] = None
    total_equity: Optional[Decimal] = None
    cash_and_equivalents: Optional[Decimal] = None
    inventory: Optional[Decimal] = None
    total_debt: Optional[Decimal] = None
    operating_cash_flow: Optional[Decimal] = None
    capital_expenditure: Optional[Decimal] = None
    free_cash_flow: Optional[Decimal] = None
    depreciation_amortization: Optional[Decimal] = None
    source: str = Field("SEC EDGAR", max_length=100)
    is_demo_data: bool = True

class FinancialStatementCreate(FinancialStatementBase):
    pass

class FinancialStatementUpdate(BaseModel):
    fiscal_year: Optional[int] = Field(None, ge=1900, le=2100)
    fiscal_period: Optional[str] = Field(None, max_length=10)
    statement_type: Optional[str] = Field(None, max_length=50)
    revenue: Optional[Decimal] = None
    cost_of_revenue: Optional[Decimal] = None
    gross_profit: Optional[Decimal] = None
    operating_income: Optional[Decimal] = None
    ebit: Optional[Decimal] = None
    net_income: Optional[Decimal] = None
    total_assets: Optional[Decimal] = None
    current_assets: Optional[Decimal] = None
    total_liabilities: Optional[Decimal] = None
    current_liabilities: Optional[Decimal] = None
    total_equity: Optional[Decimal] = None
    cash_and_equivalents: Optional[Decimal] = None
    inventory: Optional[Decimal] = None
    total_debt: Optional[Decimal] = None
    operating_cash_flow: Optional[Decimal] = None
    capital_expenditure: Optional[Decimal] = None
    free_cash_flow: Optional[Decimal] = None
    depreciation_amortization: Optional[Decimal] = None
    source: Optional[str] = None
    is_demo_data: Optional[bool] = None

class FinancialStatementResponse(FinancialStatementBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int
    created_at: datetime
