from __future__ import annotations

import datetime
import os
import secrets
from typing import Annotated
import random

from fastapi import Depends, Header
import passlib.context
from sqlalchemy import select
from sqlalchemy.orm import Session

from api import db
from api.db import get_db_session
from api.models import User

from jwt import JWT, jwk_from_dict

EXAMPLE_SECRET = "aaa2137bbb"

def create_jwt_token(user_id: int):
    now = datetime.datetime.now(datetime.UTC)
    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + datetime.timedelta(hours=1000)
    }
    
    key = jwk_from_dict({"kty": "oct", "k": EXAMPLE_SECRET})
    return JWT().encode(payload, key, alg="HS256")



def __get_or_create_dev_user__(
    db: Session, 
    *, 
    email: str, 
    full_name: str | None, 
    role: str | None
    sex: str) -> User:
    existing = db.execute(select(User).where(User.email == email)).scalars().first()
    if existing:
        db.commit()
        db.refresh(existing)
        return existing

    user = User(email=email, api_token=new_token(), sex=sex, full_name=full_name, role=role)
    db.add(user)
    db.flush()
    db.commit()
    db.refresh(user)
    return user


def seed_users(db: Session, seed: int = 42, patient_count: int = 1):

    _get_or_create_dev_user(
        db,
        email=os.getenv("DEV_ADMIN_EMAIL", 'admin@local'),
        full_name=os.getenv("DEV_ADMIN_NAME", "Admin"),
        role="admin",
    )
    _get_or_create_dev_user(
        db,
        email=os.getenv("DEV_CLINICIAN_EMAIL", "doctor@local"),
        full_name=os.getenv("DEV_CLINICIAN_NAME", "doctor"),
        role="doctor",
    )
    
def _dev_user_from_role(db: Session, role_key: str | None) -> User:
    key = (role_key or os.getenv("DEV_ROLE") or "clinician").strip().lower()

    if key in {"admin", "administrator"}:
        return _get_or_create_dev_user(
            db,
            email=os.getenv("DEV_ADMIN_EMAIL", 'admin@local'),
            password=os.getenv("DEV_ADMIN_PASSWORD", "admin"),
            full_name=os.getenv("DEV_ADMIN_NAME", "Admin"),
            role="admin",
        )

    return _get_or_create_dev_user(
        db,
        email=os.getenv("DEV_CLINICIAN_EMAIL", "clinician@local"),
        password=os.getenv("DEV_CLINICIAN_PASSWORD", "clinician"),
        full_name=os.getenv("DEV_CLINICIAN_NAME", "Clinician"),
        role="clinician",
    )


def get_current_user(
    db: Annotated[Session, Depends(get_db_session)],
) -> User:
    return _dev_user_from_role(db, dev_role)

