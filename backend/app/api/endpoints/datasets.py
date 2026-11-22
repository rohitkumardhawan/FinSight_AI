"""
FinSight AI — Dataset & CSV Upload Endpoints
============================================
Handles dual-format financial CSV uploads (Screener.in transposed export &
FinSight Combined template), parses and normalizes them, stores structured
records in Neon PostgreSQL, computes deterministic insights, and indexes
pgvector chunks for Gemini RAG.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
import logging
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status, Query, Request
from sqlalchemy.orm import Session
from sqlalchemy import select, desc
from app.core.limiter import limiter

from app.db.session import get_db
from app.models.dataset import UploadedDataset, FinancialPeriod
from app.models.company import Company
from app.schemas.dataset import (
    DatasetSummaryResponse,
    DatasetDetailResponse,
    AskQuestionRequest,
    AskQuestionResponse
)
from app.services.csv_parser import parse_financial_csv
from app.services.insights_engine import generate_auto_insights
from app.services.rag_service import index_company_chunks, ask_company_question

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/datasets", tags=["Datasets & CSV Import"])

MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB strict guard for Render 512MB RAM tier


@router.post("/upload")
@limiter.limit("10/minute")
async def upload_financial_csv(
    request: Request,
    file: UploadFile = File(..., description="Financial statement CSV (Screener.in or FinSight Combined)"),
    company_name_override: Optional[str] = Form(None, description="Optional manual company name override"),
    db: Session = Depends(get_db)
):
    """
    Upload and process a financial statement CSV:
    - Auto-detects format: 'screener_csv' or 'finsight_combined_csv'
    - Normalizes into unified financial periods
    - Computes deterministic ratios, CAGRs, and valuation scenarios
    - Persists company, periods, and 3072-dim pgvector chunks in Neon PostgreSQL
    - Returns hydrated dashboard payload
    """
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file format. Only .csv files are supported."
        )

    # 1. Read and validate file size safely
    file_bytes = await file.read()
    if len(file_bytes) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds maximum allowed size of 10 MB ({len(file_bytes) / 1024 / 1024:.2f} MB received)."
        )

    if len(file_bytes) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The uploaded CSV file is empty."
        )

    # 2. Parse and normalize CSV
    try:
        parsed = parse_financial_csv(file_bytes, file.filename)
    except Exception as e:
        logger.error(f"Failed to parse CSV {file.filename}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Failed to parse CSV: {str(e)}"
        )

    if company_name_override and company_name_override.strip():
        parsed.company_name = company_name_override.strip()

    # 3. Deterministic calculations (Pure Python math)
    auto_insights = generate_auto_insights(parsed)
    parsed.auto_insights = auto_insights
    parsed.trends = auto_insights.get("trends")
    parsed.scenarios = auto_insights.get("scenario_insights")

    # 4. Upsert unified Company record
    now_utc = datetime.now(timezone.utc)
    clean_sym = "".join(c for c in parsed.company_name.upper() if c.isalnum())[:10] or "CUSTOM"
    company = db.execute(
        select(Company).where(Company.company_name == parsed.company_name)
    ).scalar_one_or_none()

    if not company:
        company = Company(
            company_name=parsed.company_name,
            symbol=clean_sym,
            ticker=clean_sym,
            exchange="NSE" if parsed.detected_format == "screener_csv" else "GLOBAL",
            currency="INR" if parsed.detected_format == "screener_csv" else "USD",
            data_source=parsed.detected_format,
            last_synced_at=now_utc,
            metadata_json={
                "trends": parsed.trends,
                "scenarios": parsed.scenarios,
                "auto_insights": parsed.auto_insights,
                "raw_metadata": parsed.raw_metadata
            }
        )
        db.add(company)
        db.commit()
        db.refresh(company)
    else:
        company.data_source = parsed.detected_format
        company.last_synced_at = now_utc
        company.metadata_json = {
            "trends": parsed.trends,
            "scenarios": parsed.scenarios,
            "auto_insights": parsed.auto_insights,
            "raw_metadata": parsed.raw_metadata
        }
        db.commit()

    # 5. Persist Financial Periods
    # Delete old periods for this company
    db.query(FinancialPeriod).filter(FinancialPeriod.company_id == company.id).delete()
    db.commit()

    for p in parsed.periods:
        fp = FinancialPeriod(
            company_id=company.id,
            fiscal_year=p.fiscal_year,
            fiscal_period=p.fiscal_period,
            statement_type=p.statement_type,
            metrics_json=p.model_dump()
        )
        db.add(fp)

    # Also persist UploadedDataset record for history
    uploaded_ds = UploadedDataset(
        company_name=parsed.company_name,
        filename=file.filename,
        detected_format=parsed.detected_format,
        source=f"CSV Upload ({parsed.detected_format})",
        period_count=len(parsed.periods),
        metadata_json={
            "company_id": company.id,
            "trends": parsed.trends,
            "scenarios": parsed.scenarios,
            "auto_insights": parsed.auto_insights
        }
    )
    db.add(uploaded_ds)
    db.commit()
    db.refresh(uploaded_ds)

    # 6. Index RAG chunks in pgvector
    try:
        index_company_chunks(db, company.id, parsed)
    except Exception as ex:
        logger.error(f"Failed to index RAG chunks for company {company.id}: {ex}")

    return {
        "success": True,
        "message": f"Successfully processed {len(parsed.periods)} periods from {file.filename}.",
        "company_id": company.id,
        "dataset_id": uploaded_ds.id,
        "company_name": company.company_name,
        "symbol": company.symbol,
        "exchange": company.exchange,
        "currency": company.currency,
        "detected_format": parsed.detected_format,
        "period_count": len(parsed.periods),
        "periods": [p.model_dump() for p in parsed.periods],
        "trends": parsed.trends,
        "scenarios": parsed.scenarios,
        "auto_insights": parsed.auto_insights
    }


@router.get("", response_model=List[DatasetSummaryResponse])
def list_datasets(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """List all uploaded datasets with detected format badges and period counts."""
    return (
        db.query(UploadedDataset)
        .order_by(desc(UploadedDataset.created_at))
        .offset(skip)
        .limit(limit)
        .all()
    )


@router.get("/{dataset_id}", response_model=DatasetDetailResponse)
def get_dataset_detail(dataset_id: int, db: Session = Depends(get_db)):
    """Retrieve full details of an uploaded dataset, including periods and deterministic insights."""
    ds = db.get(UploadedDataset, dataset_id)
    if not ds:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dataset with ID {dataset_id} not found."
        )

    periods_data = [p.metrics_json for p in ds.periods if p.metrics_json]
    auto_insights = (ds.metadata_json or {}).get("auto_insights")

    return DatasetDetailResponse(
        id=ds.id,
        company_name=ds.company_name,
        filename=ds.filename,
        detected_format=ds.detected_format,
        source=ds.source,
        period_count=ds.period_count,
        created_at=ds.created_at,
        metadata_json=ds.metadata_json,
        periods=periods_data,
        auto_insights=auto_insights
    )


@router.post("/ask", response_model=AskQuestionResponse)
async def ask_dataset_question(
    req: AskQuestionRequest,
    db: Session = Depends(get_db)
):
    """
    RAG Question-Answering endpoint scoped to an uploaded dataset or company.
    Retrieves top-5 cosine similarity vector chunks + exact SQL facts.
    """
    # Check if dataset_id corresponds to a Company or UploadedDataset
    company = db.get(Company, req.dataset_id)
    company_id = company.id if company else None

    if not company_id:
        ds = db.get(UploadedDataset, req.dataset_id)
        if ds and ds.metadata_json and "company_id" in ds.metadata_json:
            company_id = ds.metadata_json["company_id"]

    if not company_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dataset or Company with ID {req.dataset_id} not found."
        )

    return await ask_company_question(db, company_id, req.question)
