"""Pydantic schemas for authentication and user sessions."""

from __future__ import annotations

import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field, computed_field


class UserSchema(BaseModel):
    """User profile representation."""
    model_config = ConfigDict(from_attributes=True)

    user_id: str
    email: str
    name: str
    picture_url: Optional[str] = None
    google_sub: Optional[str] = None
    is_active: bool = True
    created_at: str = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat())
    last_login_at: str = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat())

    @computed_field
    @property
    def full_name(self) -> str:
        return self.name

    @computed_field
    @property
    def avatar_url(self) -> Optional[str]:
        return self.picture_url


class GoogleAuthRequest(BaseModel):
    """Request payload containing Google Identity Services credential."""
    credential: str = Field(..., description="Google ID Token issued by Google Identity Services")


class DevLoginRequest(BaseModel):
    """Request payload for fast development login without Google credentials."""
    email: Optional[str] = "organizer@recruitment.local"
    name: Optional[str] = "Recruitment Organizer"


class AuthTokenResponse(BaseModel):
    """Token response returned upon successful authentication."""
    access_token: str
    token_type: str = "bearer"
    user: UserSchema


class AuthStatusResponse(BaseModel):
    """Public authentication status and configuration."""
    auth_enabled: bool
    google_client_id: str
    authenticated: bool
    user: Optional[UserSchema] = None
    dev_login_available: bool = True
