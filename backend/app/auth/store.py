"""User storage implementations for authentication (Memory and PostgreSQL)."""

from __future__ import annotations

import datetime
from typing import Optional
import sqlalchemy as sa
from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import UserModel
from app.db.session import get_session_factory
from app.schemas.auth import UserSchema


class InMemoryUserStore:
    """In-memory user store for development and unit testing."""

    def __init__(self) -> None:
        self._users_by_id: dict[str, UserSchema] = {}
        self._users_by_email: dict[str, str] = {}
        self._users_by_sub: dict[str, str] = {}

    def get(self, user_id: str) -> Optional[UserSchema]:
        user = self._users_by_id.get(user_id)
        return user.model_copy() if user else None

    def get_by_email(self, email: str) -> Optional[UserSchema]:
        user_id = self._users_by_email.get(email.strip().lower())
        if user_id:
            return self.get(user_id)
        return None

    def get_by_google_sub(self, google_sub: str) -> Optional[UserSchema]:
        user_id = self._users_by_sub.get(google_sub)
        if user_id:
            return self.get(user_id)
        return None

    def save(self, user: UserSchema) -> UserSchema:
        copy = user.model_copy()
        self._users_by_id[copy.user_id] = copy
        self._users_by_email[copy.email.strip().lower()] = copy.user_id
        if copy.google_sub:
            self._users_by_sub[copy.google_sub] = copy.user_id
        return copy.model_copy()

    def list_users(self) -> list[UserSchema]:
        return [u.model_copy() for u in self._users_by_id.values()]

    def reset(self) -> None:
        self._users_by_id.clear()
        self._users_by_email.clear()
        self._users_by_sub.clear()


class PostgresUserStore:
    """PostgreSQL user store with relational persistence."""

    def __init__(self, engine: Optional[Engine] = None) -> None:
        self._engine = engine
        self._session_factory: Optional[sessionmaker[Session]] = None

    def _get_session(self) -> Session:
        if self._session_factory is None:
            self._session_factory = get_session_factory(self._engine)
        return self._session_factory()

    def get(self, user_id: str) -> Optional[UserSchema]:
        with self._get_session() as s:
            row = s.execute(select(UserModel).where(UserModel.user_id == user_id)).scalars().first()
            if row:
                return UserSchema(
                    user_id=row.user_id,
                    email=row.email,
                    name=row.name,
                    picture_url=row.picture_url,
                    google_sub=row.google_sub,
                    is_active=row.is_active,
                    created_at=row.created_at.isoformat() if row.created_at else "",
                    last_login_at=row.last_login_at.isoformat() if row.last_login_at else "",
                )
            return None

    def get_by_email(self, email: str) -> Optional[UserSchema]:
        clean_email = email.strip().lower()
        with self._get_session() as s:
            row = s.execute(select(UserModel).where(UserModel.email == clean_email)).scalars().first()
            if row:
                return UserSchema(
                    user_id=row.user_id,
                    email=row.email,
                    name=row.name,
                    picture_url=row.picture_url,
                    google_sub=row.google_sub,
                    is_active=row.is_active,
                    created_at=row.created_at.isoformat() if row.created_at else "",
                    last_login_at=row.last_login_at.isoformat() if row.last_login_at else "",
                )
            return None

    def get_by_google_sub(self, google_sub: str) -> Optional[UserSchema]:
        with self._get_session() as s:
            row = s.execute(select(UserModel).where(UserModel.google_sub == google_sub)).scalars().first()
            if row:
                return UserSchema(
                    user_id=row.user_id,
                    email=row.email,
                    name=row.name,
                    picture_url=row.picture_url,
                    google_sub=row.google_sub,
                    is_active=row.is_active,
                    created_at=row.created_at.isoformat() if row.created_at else "",
                    last_login_at=row.last_login_at.isoformat() if row.last_login_at else "",
                )
            return None

    def save(self, user: UserSchema) -> UserSchema:
        clean_email = user.email.strip().lower()
        now = datetime.datetime.now(datetime.timezone.utc)
        with self._get_session() as s:
            row = s.execute(select(UserModel).where(UserModel.user_id == user.user_id)).scalars().first()
            if not row and user.google_sub:
                row = s.execute(select(UserModel).where(UserModel.google_sub == user.google_sub)).scalars().first()
            if not row:
                row = s.execute(select(UserModel).where(UserModel.email == clean_email)).scalars().first()

            if row:
                row.email = clean_email
                row.name = user.name
                if user.picture_url is not None:
                    row.picture_url = user.picture_url
                if user.google_sub is not None:
                    row.google_sub = user.google_sub
                row.is_active = user.is_active
                row.last_login_at = now
            else:
                row = UserModel(
                    user_id=user.user_id,
                    email=clean_email,
                    name=user.name,
                    picture_url=user.picture_url,
                    google_sub=user.google_sub,
                    is_active=user.is_active,
                    created_at=now,
                    last_login_at=now,
                )
                s.add(row)

            s.commit()
            s.refresh(row)
            return UserSchema(
                user_id=row.user_id,
                email=row.email,
                name=row.name,
                picture_url=row.picture_url,
                google_sub=row.google_sub,
                is_active=row.is_active,
                created_at=row.created_at.isoformat() if row.created_at else "",
                last_login_at=row.last_login_at.isoformat() if row.last_login_at else "",
            )

    def list_users(self) -> list[UserSchema]:
        with self._get_session() as s:
            rows = s.execute(select(UserModel).order_by(UserModel.created_at.desc())).scalars().all()
            return [
                UserSchema(
                    user_id=row.user_id,
                    email=row.email,
                    name=row.name,
                    picture_url=row.picture_url,
                    google_sub=row.google_sub,
                    is_active=row.is_active,
                    created_at=row.created_at.isoformat() if row.created_at else "",
                    last_login_at=row.last_login_at.isoformat() if row.last_login_at else "",
                )
                for row in rows
            ]

    def reset(self) -> None:
        with self._get_session() as s:
            s.execute(sa.text("DELETE FROM users;"))
            s.commit()
