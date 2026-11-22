from datetime import datetime
from sqlalchemy import String, DateTime, ForeignKey, Index, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base

class UploadedDocument(Base):
    __tablename__ = "uploaded_documents"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True, nullable=False
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    document_type: Mapped[str] = mapped_column(String(50), nullable=False)  # '10-K', '10-Q', '8-K', 'earnings_transcript'
    # Reference path / URI in cloud object storage (e.g. S3 / Neon Object Storage), never binary blobs
    storage_reference: Mapped[str] = mapped_column(String(500), nullable=False)
    processing_status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)  # 'pending', 'processed', 'indexed', 'failed'
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    company: Mapped["Company"] = relationship("Company", back_populates="uploaded_documents")

    __table_args__ = (
        Index("ix_doc_comp_status", "company_id", "processing_status"),
    )

    def __repr__(self) -> str:
        return f"<UploadedDocument(filename='{self.filename}', status='{self.processing_status}')>"
