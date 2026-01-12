from __future__ import annotations

import secrets
from typing import Annotated, Optional

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.orm import Session

from v011.api.db import get_db_session
from v011.api.entra_auth import (
    EntraAuthConfig,
    EntraAuthError,
    build_entra_config_from_env,
    ensure_local_user_for_entra,
    validate_entra_access_token,
)
from v011.api.models import User


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
bearer_scheme = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)


def new_token() -> str:
    return secrets.token_hex(24)


def get_db():
    with get_db_session() as db:
        yield db


def _get_user_by_token(db: Session, token: str) -> Optional[User]:
    stmt = select(User).where(User.api_token == token)
    return db.execute(stmt).scalars().first()


def _require_user(db: Session, token: str) -> User:
    user = _get_user_by_token(db, token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or missing token")
    return user


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    if not credentials or not credentials.credentials:
        raise HTTPException(status_code=401, detail="Missing Authorization: Bearer token")
    token = credentials.credentials

    # If it's a JWT (Entra access token), validate against Entra.
    if token.count(".") == 2:
        cfg: EntraAuthConfig = build_entra_config_from_env()
        try:
            claims = validate_entra_access_token(token, cfg)
        except EntraAuthError as exc:
            raise HTTPException(status_code=401, detail=str(exc))
        return ensure_local_user_for_entra(db, claims)

    # Fallback: legacy local API token
    return _require_user(db, token)

