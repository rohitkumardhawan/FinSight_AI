"""
FinSight AI — Admin Endpoints
==============================
Administrative tasks including NSE batch synchronization.
"""

import secrets
from typing import Optional
from fastapi import APIRouter, Depends, Query, Header, HTTPException, status
from sqlalchemy.orm import Session
from app.core.config import settings
from app.db.session import get_db
from app.services.nse_live_sync import sync_live_quotes, sync_nse_financials_batch

router = APIRouter(prefix="/admin", tags=["Admin"])

def verify_admin_api_key(
    x_admin_key: Optional[str] = Header(None, alias="X-Admin-Key")
) -> bool:
    """
    Validates X-Admin-Key header against settings.ADMIN_API_KEY using constant-time comparison.
    - If ADMIN_API_KEY is not set in production: returns HTTP 503 Service Unavailable.
    - If X-Admin-Key is missing or does not match: returns HTTP 401 Unauthorized.
    """
    admin_key = (settings.ADMIN_API_KEY or "").strip()
    is_prod = settings.ENVIRONMENT.lower() == "production"

    if is_prod and not admin_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Admin synchronization endpoint is unavailable: ADMIN_API_KEY is not configured in production."
        )

    if not x_admin_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing required authentication header: X-Admin-Key."
        )

    if not admin_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="ADMIN_API_KEY is not configured."
        )

    if not secrets.compare_digest(x_admin_key.strip(), admin_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid admin authentication key."
        )

    return True

@router.post("/sync-nse300", dependencies=[Depends(verify_admin_api_key)])
def trigger_sync_nse300(
    batch_size: int = Query(25, ge=1, le=100, description="Number of companies to sync financials for"),
    refresh_quotes: bool = Query(True, description="Whether to also refresh quotes"),
    db: Session = Depends(get_db)
):
    """
    Triggers rate-limited batch sync of quotes and multi-year financials
    for NSE companies in Neon Postgres.
    """
    quote_res = {}
    if refresh_quotes:
        quote_res = sync_live_quotes(db=db)

    fin_res = sync_nse_financials_batch(batch_size=batch_size, db=db)

    return {
        "status": "success",
        "quotes": quote_res,
        "financials": fin_res
    }
