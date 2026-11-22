from datetime import datetime
from decimal import Decimal
from typing import Optional
from sqlalchemy import String, Integer, Numeric, DateTime, ForeignKey, Index, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base

class FinancialRatio(Base):
    __tablename__ = "financial_ratios"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True, nullable=False
    )
    fiscal_year: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    fiscal_period: Mapped[str] = mapped_column(String(10), nullable=False, index=True)

    # Key institutional ratios
    gross_margin: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4), nullable=True)
    operating_margin: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4), nullable=True)
    net_profit_margin: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4), nullable=True)
    current_ratio: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4), nullable=True)
    quick_ratio: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4), nullable=True)
    debt_to_equity: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4), nullable=True)
    return_on_equity: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4), nullable=True)
    return_on_assets: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4), nullable=True)

    source: Mapped[str] = mapped_column(String(100), default="FinSight Analytics Engine", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    company: Mapped["Company"] = relationship("Company", back_populates="financial_ratios")

    __table_args__ = (
        Index("ix_fin_ratio_comp_period", "company_id", "fiscal_year", "fiscal_period"),
    )

    def __repr__(self) -> str:
        return f"<FinancialRatio(company_id={self.company_id}, period='{self.fiscal_year} {self.fiscal_period}')>"
