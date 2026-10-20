"""Automated tests for Authentication and Authorization Gateway."""

from __future__ import annotations

import datetime
from unittest.mock import AsyncMock, patch
import pytest
from fastapi.testclient import TestClient

from app.auth.jwt import create_access_token, decode_access_token
from app.main import app
from app.schemas.auth import UserSchema
from app.storage import default_storage_factory, default_user_store


@pytest.fixture(autouse=True)
def setup_memory_store():
    default_storage_factory.configure(backend="memory")
    default_user_store.reset()
    yield
    default_user_store.reset()


@pytest.fixture
def client():
    return TestClient(app)


def test_jwt_token_creation_and_decoding():
    """Verify JWT token generation, claims preservation, and decoding."""
    payload = {"sub": "usr_test123", "email": "test@example.com", "name": "Test User"}
    token = create_access_token(payload, expires_delta=datetime.timedelta(minutes=5))
    assert isinstance(token, str)
    assert len(token) > 20

    decoded = decode_access_token(token)
    assert decoded["sub"] == "usr_test123"
    assert decoded["email"] == "test@example.com"
    assert decoded["name"] == "Test User"
    assert "exp" in decoded


def test_auth_status_endpoint(client):
    """Verify public /api/auth/status endpoint returns configuration and session state."""
    resp = client.get("/api/auth/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "auth_enabled" in data
    assert "google_client_id" in data
    assert "authenticated" in data


def test_dev_login_and_me_endpoint(client, monkeypatch):
    """Verify 1-click developer login produces a working JWT for /api/auth/me."""
    monkeypatch.setattr("app.auth.dependencies.AUTH_ENABLED", True)

    resp = client.post(
        "/api/auth/dev-login",
        json={"email": "organizer@test.local", "name": "Organizer Alice"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["email"] == "organizer@test.local"
    assert data["user"]["name"] == "Organizer Alice"

    token = data["access_token"]

    # Call /api/auth/me with Bearer token
    me_resp = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert me_resp.status_code == 200
    me_data = me_resp.json()
    assert me_data["email"] == "organizer@test.local"
    assert me_data["name"] == "Organizer Alice"


def test_gateway_enforcement_when_auth_enabled(client, monkeypatch):
    """Verify protected endpoints return 401 when AUTH_ENABLED=True and token is missing or invalid."""
    monkeypatch.setattr("app.auth.dependencies.AUTH_ENABLED", True)

    # 1. Unauthenticated request to protected route
    resp = client.get("/api/ingestion/datasets")
    assert resp.status_code == 401
    assert "Authentication required" in resp.json()["detail"]

    # 2. Request with malformed token
    resp = client.get(
        "/api/ingestion/datasets",
        headers={"Authorization": "Bearer malformed.invalid.token"},
    )
    assert resp.status_code == 401
    assert "Invalid authentication token" in resp.json()["detail"]

    # 3. Request with valid token succeeds
    dev_resp = client.post("/api/auth/dev-login")
    valid_token = dev_resp.json()["access_token"]

    resp = client.get(
        "/api/ingestion/datasets",
        headers={"Authorization": f"Bearer {valid_token}"},
    )
    assert resp.status_code == 200


def test_gateway_bypass_when_auth_disabled(client, monkeypatch):
    """Verify endpoints automatically succeed without auth headers when AUTH_ENABLED=False."""
    monkeypatch.setattr("app.auth.dependencies.AUTH_ENABLED", False)

    resp = client.get("/api/ingestion/datasets")
    assert resp.status_code == 200


def test_google_auth_endpoint_success(client):
    """Verify /api/auth/google endpoint verifies credential and creates user."""
    mock_claims = {
        "google_sub": "google_123456789",
        "email": "candidate.lead@gmail.com",
        "name": "Jane Google",
        "picture_url": "https://lh3.googleusercontent.com/photo.jpg",
    }

    with patch("app.api.endpoints.auth.verify_google_id_token", new_callable=AsyncMock) as mock_verify:
        mock_verify.return_value = mock_claims

        resp = client.post(
            "/api/auth/google",
            json={"credential": "mock_valid_google_jwt_credential"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "access_token" in body
        assert body["user"]["email"] == "candidate.lead@gmail.com"
        assert body["user"]["name"] == "Jane Google"
        assert body["user"]["picture_url"] == "https://lh3.googleusercontent.com/photo.jpg"

        # Verify user is saved in user store
        saved = default_user_store.get_by_email("candidate.lead@gmail.com")
        assert saved is not None
        assert saved.google_sub == "google_123456789"


def test_google_auth_email_whitelist_rejection(client, monkeypatch):
    """Verify access is rejected if user email is not in ALLOWED_EMAILS."""
    import httpx
    monkeypatch.setattr("app.auth.google.ALLOWED_EMAILS", ["organizer@allowed.com"])

    class MockResponse:
        status_code = 200
        def json(self):
            return {
                "sub": "g_999",
                "email": "intruder@other.com",
                "email_verified": "true",
                "name": "Intruder",
            }

    with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = MockResponse()

        resp = client.post(
            "/api/auth/google",
            json={"credential": "token_for_unauthorized_email"},
        )
        assert resp.status_code == 403
        assert "not authorized" in resp.json()["detail"].lower()


def test_logout_endpoint(client, monkeypatch):
    """Verify /api/auth/logout endpoint."""
    monkeypatch.setattr("app.auth.dependencies.AUTH_ENABLED", True)
    dev_resp = client.post("/api/auth/dev-login")
    token = dev_resp.json()["access_token"]

    resp = client.post(
        "/api/auth/logout",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert "signed out successfully" in resp.json()["message"].lower()
