"""
FinSight AI — Phase 5 Security Hardening & Production Deployment Test Suite
============================================================================
Tests for:
1. Lightweight GET /health endpoint (SELECT 1 on Neon Postgres, status: ok)
2. Admin endpoint auth on POST /api/admin/sync-nse300 (X-Admin-Key header, 401/503 behavior)
3. Production app factory hardening (disabling /docs, /redoc, /openapi.json when ENVIRONMENT="production")
4. Strict CORS configuration (no wildcard with credentials)
5. Rate limiter registration
"""

import sys
import os
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.config import settings
from app.main import app, create_app


client = TestClient(app)


# ============================================================================
# 1. LIGHTWEIGHT HEALTH CHECK (/health)
# ============================================================================

def test_health_check_endpoint():
    """Verify GET /health returns HTTP 200 with ok status, db connection, and environment."""
    response = client.get("/health")
    assert response.status_code == 200, f"Expected 200 from /health, got {response.status_code}"
    data = response.json()
    assert data.get("status") == "ok"
    assert "db" in data
    assert data["db"] in ["connected", "unconfigured"] or "unreachable" in data["db"]
    assert "environment" in data


# ============================================================================
# 2. ADMIN ENDPOINT AUTHENTICATION (POST /api/admin/sync-nse300)
# ============================================================================

def test_admin_sync_without_key_returns_401(monkeypatch):
    """Verify POST /api/admin/sync-nse300 returns HTTP 401 when X-Admin-Key header is missing."""
    monkeypatch.setattr(settings, "ADMIN_API_KEY", "super_secret_test_key_123")
    response = client.post("/api/admin/sync-nse300")
    assert response.status_code == 401
    assert "X-Admin-Key" in response.json().get("detail", "")


def test_admin_sync_with_invalid_key_returns_401(monkeypatch):
    """Verify POST /api/admin/sync-nse300 returns HTTP 401 when X-Admin-Key is incorrect."""
    monkeypatch.setattr(settings, "ADMIN_API_KEY", "super_secret_test_key_123")
    response = client.post(
        "/api/admin/sync-nse300",
        headers={"X-Admin-Key": "wrong_key_xyz"}
    )
    assert response.status_code == 401
    assert "Invalid admin" in response.json().get("detail", "")


def test_admin_sync_unset_in_production_returns_503(monkeypatch):
    """Verify POST /api/admin/sync-nse300 returns HTTP 503 when in production and ADMIN_API_KEY is unset."""
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    monkeypatch.setattr(settings, "ADMIN_API_KEY", "")
    response = client.post(
        "/api/admin/sync-nse300",
        headers={"X-Admin-Key": "any_key"}
    )
    assert response.status_code == 503
    assert "ADMIN_API_KEY is not configured" in response.json().get("detail", "")


def test_admin_sync_with_valid_key_accepts_auth(monkeypatch):
    """Verify POST /api/admin/sync-nse300 passes authentication when valid key is provided."""
    test_key = "secure_production_key_456"
    monkeypatch.setattr(settings, "ADMIN_API_KEY", test_key)
    monkeypatch.setattr(settings, "ENVIRONMENT", "development")

    # Pass batch_size=1 so execution finishes immediately if DB is connected
    response = client.post(
        "/api/admin/sync-nse300?batch_size=1&refresh_quotes=false",
        headers={"X-Admin-Key": test_key}
    )
    # Status should NOT be 401 or 503 (auth succeeded)
    assert response.status_code not in [401, 403, 503]


# ============================================================================
# 3. PRODUCTION APP FACTORY HARDENING (Docs & OpenAPI Disabled in Production)
# ============================================================================

def test_production_app_disables_docs(monkeypatch):
    """Verify create_app disables /docs, /redoc, and /openapi.json when ENVIRONMENT='production'."""
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    prod_app = create_app()

    assert prod_app.docs_url is None
    assert prod_app.redoc_url is None
    assert prod_app.openapi_url is None

    prod_client = TestClient(prod_app)
    docs_resp = prod_client.get("/docs")
    assert docs_resp.status_code == 404

    redoc_resp = prod_client.get("/redoc")
    assert redoc_resp.status_code == 404

    openapi_resp = prod_client.get("/openapi.json")
    assert openapi_resp.status_code == 404


def test_development_app_enables_docs(monkeypatch):
    """Verify create_app enables /docs when ENVIRONMENT='development'."""
    monkeypatch.setattr(settings, "ENVIRONMENT", "development")
    dev_app = create_app()

    assert dev_app.docs_url == "/docs"
    dev_client = TestClient(dev_app)
    docs_resp = dev_client.get("/docs")
    assert docs_resp.status_code == 200


# ============================================================================
# 4. CORS CONFIGURATION HARDENING
# ============================================================================

def test_cors_production_no_wildcard(monkeypatch):
    """Verify production CORS origins do not include wildcard '*' when credentials allowed."""
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    monkeypatch.setattr(settings, "FRONTEND_ORIGIN", "https://finsight.ai,https://app.finsight.ai")

    origins = settings.allowed_origins_list
    assert "*" not in origins
    assert "https://finsight.ai" in origins
    assert "https://app.finsight.ai" in origins
    assert "http://localhost:3000" not in origins  # Only allowed in dev


def test_cors_dev_includes_localhost(monkeypatch):
    """Verify development CORS automatically includes local Next.js origins."""
    monkeypatch.setattr(settings, "ENVIRONMENT", "development")
    monkeypatch.setattr(settings, "FRONTEND_ORIGIN", "http://localhost:3000")

    origins = settings.allowed_origins_list
    assert "http://localhost:3000" in origins
    assert "http://127.0.0.1:3000" in origins


# ============================================================================
# 5. RATE LIMITER CONFIGURATION
# ============================================================================

def test_rate_limiter_is_configured():
    """Verify slowapi rate limiter is registered on app.state."""
    assert hasattr(app.state, "limiter")
    assert app.state.limiter is not None
