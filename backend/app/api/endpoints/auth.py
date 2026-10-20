"""Authentication and session management API endpoints."""

from __future__ import annotations

import datetime
import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status

from app.auth.dependencies import get_current_user, get_optional_current_user
from app.auth.google import verify_google_id_token
from app.auth.jwt import create_access_token
from app.config import APP_ENV, AUTH_ENABLED, GOOGLE_CLIENT_ID
from app.schemas.auth import (
    AuthStatusResponse,
    AuthTokenResponse,
    DevLoginRequest,
    GoogleAuthRequest,
    UserSchema,
)
from app.storage import default_user_store

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


@router.get("/status", response_model=AuthStatusResponse)
async def get_auth_status(
    current_user: Optional[UserSchema] = Depends(get_optional_current_user),
) -> AuthStatusResponse:
    """Return public authentication configuration and current session status."""
    return AuthStatusResponse(
        auth_enabled=AUTH_ENABLED,
        google_client_id=GOOGLE_CLIENT_ID or "",
        authenticated=current_user is not None,
        user=current_user,
        dev_login_available=APP_ENV != "production",
    )


@router.post("/google", response_model=AuthTokenResponse)
async def authenticate_with_google(request: GoogleAuthRequest) -> AuthTokenResponse:
    """Authenticate using Google Identity Services ID token.

    Verifies the credential with Google, upserts the user record in persistent storage,
    and returns a signed JWT access token.
    """
    google_data = await verify_google_id_token(request.credential)
    email = google_data["email"]
    sub = google_data.get("google_sub")

    # Check if user already exists
    user = default_user_store.get_by_email(email)
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

    if user:
        user.name = google_data.get("name") or user.name
        user.picture_url = google_data.get("picture_url") or user.picture_url
        user.google_sub = sub or user.google_sub
        user.last_login_at = now_iso
        saved_user = default_user_store.save(user)
    else:
        new_user = UserSchema(
            user_id=f"usr_{uuid.uuid4().hex[:12]}",
            email=email,
            name=google_data.get("name") or email.split("@")[0],
            picture_url=google_data.get("picture_url"),
            google_sub=sub,
            is_active=True,
            created_at=now_iso,
            last_login_at=now_iso,
        )
        saved_user = default_user_store.save(new_user)

    token = create_access_token({
        "sub": saved_user.user_id,
        "email": saved_user.email,
        "name": saved_user.name,
    })

    return AuthTokenResponse(
        access_token=token,
        token_type="bearer",
        user=saved_user,
    )


@router.post("/dev-login", response_model=AuthTokenResponse)
async def dev_quick_login(request: Optional[DevLoginRequest] = None) -> AuthTokenResponse:
    """Developer 1-click login for local development without Google Cloud setup.

    Only enabled when APP_ENV != 'production'.
    """
    if APP_ENV.strip().lower() == "production":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Developer quick login is disabled in production environments.",
        )

    req_data = request or DevLoginRequest()
    clean_email = (req_data.email or "organizer@recruitment.local").strip().lower()
    clean_name = (req_data.name or "Recruitment Organizer").strip()

    user = default_user_store.get_by_email(clean_email)
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

    if not user:
        user = UserSchema(
            user_id=f"usr_dev_{uuid.uuid4().hex[:8]}",
            email=clean_email,
            name=clean_name,
            picture_url=None,
            google_sub="dev_sub_local",
            is_active=True,
            created_at=now_iso,
            last_login_at=now_iso,
        )
    else:
        user.name = clean_name
        user.last_login_at = now_iso

    saved_user = default_user_store.save(user)

    token = create_access_token({
        "sub": saved_user.user_id,
        "email": saved_user.email,
        "name": saved_user.name,
    })

    return AuthTokenResponse(
        access_token=token,
        token_type="bearer",
        user=saved_user,
    )


@router.get("/me", response_model=UserSchema)
async def get_current_user_profile(
    current_user: UserSchema = Depends(get_current_user),
) -> UserSchema:
    """Return the currently authenticated user profile."""
    return current_user


@router.post("/logout")
async def logout(
    current_user: UserSchema = Depends(get_current_user),
) -> dict[str, str]:
    """Sign out the current user session."""
    return {"message": f"User '{current_user.email}' signed out successfully."}
