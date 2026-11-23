from datetime import datetime
from typing import List, Optional
from sqlalchemy import String, DateTime, Boolean, func, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base

class Company(Base):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ticker: Mapped[Optional[str]] = mapped_column(String(50), index=True, nullable=True)
    symbol: Mapped[Optional[str]] = mapped_column(String(50), unique=True, index=True, nullable=True)
    company_name: Mapped[str] = mapped_column(String(255), nullable=False)
    exchange: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    sector: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    industry: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    country: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    currency: Mapped[str] = mapped_column(String(10), default="USD", nullable=False)
    data_source: Mapped[Optional[str]] = mapped_column(String(50), default="yfinance", nullable=True)
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    isin: Mapped[Optional[str]] = mapped_column(String(50), index=True, nullable=True)
    listing_date: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    is_featured: Mapped[Optional[bool]] = mapped_column(Boolean, default=False, nullable=True)
    metadata_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships with cascade delete
    financial_statements: Mapped[List["FinancialStatement"]] = relationship(
        "FinancialStatement", back_populates="company", cascade="all, delete-orphan", lazy="selectin"
    )
    financial_ratios: Mapped[List["FinancialRatio"]] = relationship(
        "FinancialRatio", back_populates="company", cascade="all, delete-orphan", lazy="selectin"
    )
    research_records: Mapped[List["ResearchRecord"]] = relationship(
        "ResearchRecord", back_populates="company", cascade="all, delete-orphan", lazy="selectin"
    )
    uploaded_documents: Mapped[List["UploadedDocument"]] = relationship(
        "UploadedDocument", back_populates="company", cascade="all, delete-orphan", lazy="selectin"
    )
    periods: Mapped[List["FinancialPeriod"]] = relationship(
        "FinancialPeriod", back_populates="company", cascade="all, delete-orphan", lazy="selectin"
    )
    rag_chunks: Mapped[List["RagChunk"]] = relationship(
        "RagChunk", back_populates="company", cascade="all, delete-orphan", lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<Company(id={self.id}, symbol='{self.symbol or self.ticker}', name='{self.company_name}')>"
