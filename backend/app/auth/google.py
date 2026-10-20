"""Google OAuth ID token verification utility."""

from __future__ import annotations

import logging
from typing import Any, Optional
import httpx
from fastapi import HTTPException, status

from app.config import ALLOWED_EMAIL_DOMAINS, ALLOWED_EMAILS, GOOGLE_CLIENT_ID

logger = logging.getLogger("app.auth.google")

GOOGLE_TOKENINFO_URL = "https://oauth2.googleapis.com/tokeninfo"


async def verify_google_id_token(credential: str) -> dict[str, Any]:
    """Verify Google Identity Services credential (ID token) against Google's servers.

    Returns the decoded claims dictionary containing email, name, sub, picture.
    Raises HTTPException on validation errors or authorization rejections.
    """
    if not credential or not credential.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing Google authentication credential.",
        )

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(GOOGLE_TOKENINFO_URL, params={"id_token": credential})
    except Exception as exc:
        logger.error(f"Failed to connect to Google OAuth service: {exc}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to verify credentials with Google authentication service.",
        ) from exc

    if resp.status_code != 200:
        error_detail = "Invalid Google authentication token."
        try:
            err_json = resp.json()
            if "error_description" in err_json:
                error_detail = f"Google verification error: {err_json['error_description']}"
        except Exception:
            pass
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=error_detail)

    claims = resp.json()

    # Validate Audience if GOOGLE_CLIENT_ID is configured
    if GOOGLE_CLIENT_ID and GOOGLE_CLIENT_ID.strip():
        aud = claims.get("aud")
        if aud != GOOGLE_CLIENT_ID.strip():
            logger.warning(f"Google token audience mismatch: expected '{GOOGLE_CLIENT_ID}', got '{aud}'")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Google credential was issued for a different client application.",
            )

    email = claims.get("email")
    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Google profile does not contain a verified email address.",
        )

    email_verified = claims.get("email_verified")
    if str(email_verified).lower() not in ("true", "1"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your Google email address is not verified.",
        )

    clean_email = email.strip().lower()

    # Check Email Whitelist if configured
    if ALLOWED_EMAILS:
        if clean_email not in ALLOWED_EMAILS:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied: '{clean_email}' is not authorized to access this recruitment tool.",
            )

    # Check Domain Whitelist if configured
    if ALLOWED_EMAIL_DOMAINS:
        domain = clean_email.split("@")[-1] if "@" in clean_email else ""
        if domain not in ALLOWED_EMAIL_DOMAINS:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied: Email domain '@{domain}' is not authorized to access this recruitment tool.",
            )

    return {
        "google_sub": claims.get("sub"),
        "email": clean_email,
        "name": claims.get("name") or clean_email.split("@")[0],
        "picture_url": claims.get("picture"),
    }
