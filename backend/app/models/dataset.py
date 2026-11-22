"""
FinSight AI — Uploaded Datasets, Financial Periods & RAG Vector Models
======================================================================
Stores normalized financial datasets, canonical financial periods, and
vector embeddings in Neon PostgreSQL (pgvector).
"""

from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Index
from sqlalchemy.types import JSON
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector
from app.db.base import Base


class UploadedDataset(Base):
    """Stores metadata and aggregate insights for uploaded financial files."""
    __tablename__ = "uploaded_datasets"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    company_name = Column(String(255), nullable=False, index=True)
    filename = Column(String(255), nullable=False)
    detected_format = Column(String(50), nullable=False)  # 'screener_csv' or 'finsight_combined_csv'
    source = Column(String(100), default="CSV Upload")
    period_count = Column(Integer, default=0)
    metadata_json = Column(JSON, nullable=True)  # stores trends, scenarios, auto_insights
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    periods = relationship(
        "FinancialPeriod",
        back_populates="dataset",
        cascade="all, delete-orphan",
        order_by="FinancialPeriod.fiscal_year.asc()"
    )
    rag_chunks = relationship(
        "RagChunk",
        back_populates="dataset",
        cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<UploadedDataset(id={self.id}, company='{self.company_name}', format='{self.detected_format}')>"


class FinancialPeriod(Base):
    """Stores normalized metrics for an individual reporting period."""
    __tablename__ = "financial_periods"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=True, index=True)
    dataset_id = Column(Integer, ForeignKey("uploaded_datasets.id", ondelete="CASCADE"), nullable=True, index=True)
    fiscal_year = Column(Integer, nullable=True, index=True)
    fiscal_period = Column(String(50), nullable=False, default="FY", index=True)  # 'FY', 'TTM', 'Best Case', 'Worst Case'
    statement_type = Column(String(50), default="annual_combined")
    metrics_json = Column(JSON, nullable=True)  # Canonical metrics: revenue, operating_income, net_income, etc.

    # Relationships
    company = relationship("Company", back_populates="periods")
    dataset = relationship("UploadedDataset", back_populates="periods")

    def __repr__(self) -> str:
        return f"<FinancialPeriod(id={self.id}, company_id={self.company_id}, year={self.fiscal_year}, period='{self.fiscal_period}')>"


class RagChunk(Base):
    """Stores grounded text chunks and 3072-dimensional vector embeddings for Gemini RAG."""
    __tablename__ = "rag_chunks"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=True, index=True)
    dataset_id = Column(Integer, ForeignKey("uploaded_datasets.id", ondelete="CASCADE"), nullable=True, index=True)
    chunk_type = Column(String(50), nullable=False, index=True)  # 'profile', 'period', 'trends', 'scenarios'
    source_ref = Column(String(255), nullable=True)  # e.g., 'ASIANPAINT.NS | FY2025 | Yahoo Finance'
    content = Column(Text, nullable=False)
    embedding = Column(Vector(3072), nullable=True)

    # Relationships
    company = relationship("Company", back_populates="rag_chunks")
    dataset = relationship("UploadedDataset", back_populates="rag_chunks")

    def __repr__(self) -> str:
        return f"<RagChunk(id={self.id}, company_id={self.company_id}, type='{self.chunk_type}', ref='{self.source_ref}')>"
