"""FastAPI authentication dependencies for request protection."""

from __future__ import annotations

import logging
from typing import Optional
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import jwt

from app.auth.jwt import decode_access_token
from app.config import AUTH_ENABLED
from app.schemas.auth import UserSchema
from app.storage import default_user_store

logger = logging.getLogger("app.auth")

# HTTPBearer security scheme (auto_error=False to customize response messages)
bearer_scheme = HTTPBearer(auto_error=False)

DEV_USER = UserSchema(
    user_id="dev_organizer",
    email="organizer@recruitment.local",
    name="Dev Organizer",
    is_active=True,
)


async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> UserSchema:
    """Retrieve and validate the currently authenticated user.

    If AUTH_ENABLED is False (e.g. during local offline dev or unit test suite),
    returns a mock authorized organizer user without requiring headers.
    """
    if not AUTH_ENABLED:
        return DEV_USER

    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please provide a valid Bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    try:
        payload = decode_access_token(token)
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired. Please sign in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.PyJWTError as exc:
        logger.warning(f"Invalid JWT token: {exc}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("sub") or payload.get("user_id")
    email = payload.get("email")

    user = None
    if user_id:
        user = default_user_store.get(str(user_id))
    if not user and email:
        user = default_user_store.get_by_email(str(email))

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account associated with this session no longer exists.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated.",
        )

    return user


async def get_optional_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> Optional[UserSchema]:
    """Retrieve the current user if authenticated, or None if unauthenticated."""
    try:
        return await get_current_user(request=request, credentials=credentials)
    except HTTPException:
        return None
