import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.core.config import settings
from app.core.limiter import limiter
from app.db.session import SessionLocal
from app.api.v1.router import api_router
from app.api.endpoints import (
    health as api_health,
    companies as api_companies,
    statements as api_statements,
    datasets as api_datasets,
    admin as api_admin
)

logger = logging.getLogger("finsight.main")

def create_app() -> FastAPI:
    """
    Application factory configuring security hardening, Sentry observability,
    CORS policies, rate limiting, and database routes.
    """
    is_prod = settings.ENVIRONMENT.lower() == "production"

    # 1. Optional Sentry Error Tracking in Production
    if settings.SENTRY_DSN and settings.SENTRY_DSN.strip():
        try:
            import sentry_sdk
            sentry_sdk.init(
                dsn=settings.SENTRY_DSN.strip(),
                traces_sample_rate=0.1
            )
            logger.info("Sentry SDK initialized successfully.")
        except Exception as e:
            logger.warning(f"Failed to initialize Sentry: {e}")

    # 2. Production Documentation Hardening
    application = FastAPI(
        title=settings.PROJECT_NAME,
        version=settings.VERSION,
        description="Institutional AI-Powered Equity Research & Financial Intelligence Platform API",
        docs_url=None if is_prod else "/docs",
        redoc_url=None if is_prod else "/redoc",
        openapi_url=None if is_prod else "/openapi.json"
    )

    # 3. Rate Limiter Registration
    application.state.limiter = limiter
    application.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    application.add_middleware(SlowAPIMiddleware)

    # 4. Strict CORS Configuration (Never wildcard with credentials)
    allowed_origins = [o.strip() for o in settings.FRONTEND_ORIGIN.split(",") if o.strip()]
    if not is_prod:
        for local_origin in ["http://localhost:3000", "http://127.0.0.1:3000"]:
            if local_origin not in allowed_origins:
                allowed_origins.append(local_origin)

    application.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 5. Lightweight /health endpoint with Neon DB SELECT 1 verification
    @application.get("/health")
    def health_check():
        db_status = "connected"
        if SessionLocal is None:
            db_status = "unconfigured"
        else:
            try:
                with SessionLocal() as db:
                    db.execute(text("SELECT 1"))
            except Exception as e:
                db_status = f"unreachable: {str(e)}"
        return {
            "status": "ok",
            "db": db_status,
            "environment": settings.ENVIRONMENT
        }

    # 6. Mount API Routers
    application.include_router(api_health.router, prefix="/api")
    application.include_router(api_companies.router, prefix="/api")
    application.include_router(api_statements.router, prefix="/api")
    application.include_router(api_datasets.router, prefix="/api")
    application.include_router(api_admin.router, prefix="/api")
    application.include_router(api_router, prefix=settings.API_V1_STR)

    @application.get("/")
    async def root():
        return {
            "brand": "FinSight AI",
            "tagline": "AI-Powered Equity Research & Financial Intelligence",
            "docs": "/docs" if not is_prod else None,
            "health": "/health",
            "api_health": "/api/health",
            "db_health": "/api/db/health",
            "companies": "/api/companies",
            "company_search": "/api/companies/search",
            "datasets_upload": "/api/datasets/upload",
            "v1_health": f"{settings.API_V1_STR}/health"
        }

    return application

app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=settings.PORT, reload=(settings.ENVIRONMENT.lower() != "production"))
