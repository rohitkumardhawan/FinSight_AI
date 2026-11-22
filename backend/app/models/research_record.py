from datetime import datetime
from sqlalchemy import String, Text, DateTime, ForeignKey, Index, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base

class ResearchRecord(Base):
    __tablename__ = "research_records"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True, nullable=False
    )
    research_title: Mapped[str] = mapped_column(String(255), nullable=False)
    research_type: Mapped[str] = mapped_column(String(50), nullable=False)  # 'analyst_note', 'consensus_brief', 'earnings_preview'
    research_content: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(String(100), default="FinSight Institutional Desk", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    company: Mapped["Company"] = relationship("Company", back_populates="research_records")

    __table_args__ = (
        Index("ix_research_comp_created", "company_id", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<ResearchRecord(id={self.id}, title='{self.research_title}')>"
