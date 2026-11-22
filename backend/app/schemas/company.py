from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, ConfigDict, Field

class CompanyBase(BaseModel):
    ticker: Optional[str] = Field(None, max_length=50, description="Stock ticker symbol")
    symbol: Optional[str] = Field(None, max_length=50, description="Canonical stock symbol")
    company_name: str = Field(..., min_length=1, max_length=255, description="Corporate name")
    exchange: Optional[str] = Field(None, max_length=50, description="Stock exchange, e.g. NSE, NASDAQ, NYSE")
    sector: Optional[str] = Field(None, max_length=100)
    industry: Optional[str] = Field(None, max_length=150)
    country: Optional[str] = Field(None, max_length=100)
    currency: str = Field("USD", max_length=10)
    data_source: Optional[str] = Field("yfinance", max_length=50)

class CompanyCreate(CompanyBase):
    pass

class CompanyUpdate(BaseModel):
    company_name: Optional[str] = Field(None, min_length=1, max_length=255)
    exchange: Optional[str] = Field(None, max_length=50)
    sector: Optional[str] = Field(None, max_length=100)
    industry: Optional[str] = Field(None, max_length=150)
    country: Optional[str] = Field(None, max_length=100)
    currency: Optional[str] = Field(None, max_length=10)
    data_source: Optional[str] = Field(None, max_length=50)

class CompanyResponse(CompanyBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    last_synced_at: Optional[datetime] = None
    metadata_json: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime
