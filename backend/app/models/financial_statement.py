from datetime import datetime
from decimal import Decimal
from typing import Optional
from sqlalchemy import String, Integer, Numeric, Boolean, DateTime, ForeignKey, Index, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base

class FinancialStatement(Base):
    __tablename__ = "financial_statements"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True, nullable=False
    )
    fiscal_year: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    fiscal_period: Mapped[str] = mapped_column(String(10), nullable=False, index=True)  # e.g., 'FY', 'Q1', 'Q2', 'Q3', 'Q4'
    statement_type: Mapped[str] = mapped_column(String(50), nullable=False)  # 'income_statement', 'balance_sheet', 'cash_flow', 'combined'

    # Financial line items (Nullable to reflect real-world non-standardized disclosures)
    revenue: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2), nullable=True)
    cost_of_revenue: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2), nullable=True)
    gross_profit: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2), nullable=True)
    operating_income: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2), nullable=True)
    ebit: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2), nullable=True)
    net_income: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2), nullable=True)
    total_assets: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2), nullable=True)
    current_assets: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2), nullable=True)
    total_liabilities: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2), nullable=True)
    current_liabilities: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2), nullable=True)
    total_equity: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2), nullable=True)
    cash_and_equivalents: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2), nullable=True)
    inventory: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2), nullable=True)
    total_debt: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2), nullable=True)
    operating_cash_flow: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2), nullable=True)
    capital_expenditure: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2), nullable=True)
    free_cash_flow: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2), nullable=True)
    depreciation_amortization: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2), nullable=True)

    source: Mapped[str] = mapped_column(String(100), default="SEC EDGAR", nullable=False)
    is_demo_data: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    company: Mapped["Company"] = relationship("Company", back_populates="financial_statements")

    # Composite Index for fast financial time-series queries
    __table_args__ = (
        Index("ix_fin_stmt_comp_period", "company_id", "fiscal_year", "fiscal_period", "statement_type"),
    )

    def __repr__(self) -> str:
        return f"<FinancialStatement(company_id={self.company_id}, period='{self.fiscal_year} {self.fiscal_period}')>"
