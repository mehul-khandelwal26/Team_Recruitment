"""JWT token generation and verification utility functions."""

from __future__ import annotations

import datetime
from typing import Any, Optional
import jwt

from app.config import JWT_ACCESS_TOKEN_EXPIRE_MINUTES, JWT_ALGORITHM, JWT_SECRET_KEY


def create_access_token(
    data: dict[str, Any],
    expires_delta: Optional[datetime.timedelta] = None,
) -> str:
    """Create a signed JWT access token containing arbitrary payload data."""
    to_encode = data.copy()
    now = datetime.datetime.now(datetime.timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + datetime.timedelta(minutes=JWT_ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"iat": now, "exp": expire})
    return jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any]:
    """Decode and validate a signed JWT access token.

    Raises:
        jwt.ExpiredSignatureError: If token has expired.
        jwt.PyJWTError: If token is invalid or signature check fails.
    """
    return jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
