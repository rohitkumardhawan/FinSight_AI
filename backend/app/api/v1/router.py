from fastapi import APIRouter
from app.api.v1.endpoints import health, overview, companies

api_router = APIRouter()

api_router.include_router(health.router, tags=["Health"])
api_router.include_router(overview.router, tags=["Dashboard & Overview"])
api_router.include_router(companies.router, tags=["Companies Directory"])
