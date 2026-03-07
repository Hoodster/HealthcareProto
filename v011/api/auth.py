from __future__ import annotations

from cProfile import Profile
import os
import secrets
from typing import Annotated

from fastapi import Depends, Header
import passlib.context
from sqlalchemy import select
from sqlalchemy.orm import Session

from v011.api.db import get_db_session
from v011.api.models import User


pwd_context = passlib.context.CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def new_token() -> str:
    return secrets.token_hex(24)


def get_db():
    with get_db_session() as db:
        yield db


def _get_or_create_dev_user(db: Session, *, email: str, password: str, full_name: str | None, role: str | None) -> User:
    existing = db.execute(select(User).where(User.email == email)).scalars().first()
    if existing:
        db.commit()
        db.refresh(existing)
        return existing

    user = User(email=email, password_hash=hash_password(password), api_token=new_token())
    db.add(user)
    db.flush()
    db.commit()
    db.refresh(user)
    return user


def _dev_user_from_role(db: Session, role_key: str | None) -> User:
    key = (role_key or os.getenv("V011_DEV_ROLE") or "clinician").strip().lower()

    if key in {"admin", "administrator"}:
        return _get_or_create_dev_user(
            db,
            email=os.getenv("V011_DEV_ADMIN_EMAIL") or "admin@local",
            password=os.getenv("V011_DEV_ADMIN_PASSWORD") or "admin",
            full_name=os.getenv("V011_DEV_ADMIN_NAME") or "Admin",
            role="admin",
        )

    return _get_or_create_dev_user(
        db,
        email=os.getenv("V011_DEV_CLINICIAN_EMAIL") or "clinician@local",
        password=os.getenv("V011_DEV_CLINICIAN_PASSWORD") or "clinician",
        full_name=os.getenv("V011_DEV_CLINICIAN_NAME") or "Clinician",
        role="clinician",
    )


def get_current_user(
    db: Annotated[Session, Depends(get_db)],
    dev_role: Annotated[str | None, Header(alias="X-Dev-Role")] = None,
) -> User:
    return _dev_user_from_role(db, dev_role)

