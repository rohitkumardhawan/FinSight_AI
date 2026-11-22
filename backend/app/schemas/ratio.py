from datetime import datetime
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field

class FinancialRatioBase(BaseModel):
    fiscal_year: int = Field(..., ge=1900, le=2100)
    fiscal_period: str = Field(..., max_length=10)
    gross_margin: Optional[Decimal] = None
    operating_margin: Optional[Decimal] = None
    net_profit_margin: Optional[Decimal] = None
    current_ratio: Optional[Decimal] = None
    quick_ratio: Optional[Decimal] = None
    debt_to_equity: Optional[Decimal] = None
    return_on_equity: Optional[Decimal] = None
    return_on_assets: Optional[Decimal] = None
    source: str = Field("FinSight Analytics Engine", max_length=100)

class FinancialRatioCreate(FinancialRatioBase):
    pass

class FinancialRatioResponse(FinancialRatioBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int
    created_at: datetime
