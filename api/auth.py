from __future__ import annotations

import datetime
import os
import secrets
import token
from typing import Annotated
import random

from dns.dnssecalgs import algorithms
from fastapi import Depends, Header
import passlib.context
from sqlalchemy import select
from sqlalchemy.orm import Session

from api import db
from api.db import get_db_session
from api.models import User

from jwt import JWT, jwk_from_dict

EXAMPLE_SECRET = "aaa2137bbb"

def create_jwt_token(user_id: str):
    now = datetime.datetime.now(datetime.UTC)
    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + datetime.timedelta(hours=1000)
    }
    
    key = jwk_from_dict({"kty": "oct", "k": EXAMPLE_SECRET})
    return JWT().encode(payload, key, alg="HS256")

def decode_jwt_token(token: str):
    if not token.startswith("Bearer "):
        raise RuntimeError("Invalid authorization header")
    
    token_code = token.split(" ")[1]
    key = jwk_from_dict({"kty": "oct", "k": EXAMPLE_SECRET})
    try:
        payload = JWT().decode(token_code, key, algorithms={'HS256'})
    except Exception as e:
        raise RuntimeError("Invalid token") from e
        
    user_id = payload.get("sub")
    if not user_id:
        raise RuntimeError("Could not retrieve userid")
    return user_id



def __get_or_create_dev_user__(
    db: Session, 
    *, 
    email: str, 
    full_name: str, 
    role: str,
    sex: str) -> User:
    existing = db.execute(select(User).where(User.email == email)).scalars().first()
    if existing:
        db.commit()
        db.refresh(existing)
        return existing

    user = User(email=email, sex=sex, full_name=full_name)
    db.add(user)
    db.flush()
    db.commit()
    db.refresh(user)
    return user


def seed_users(db: Session):

    __get_or_create_dev_user__(
        db,
        email=os.getenv("DEV_ADMIN_EMAIL", 'admin@local'),
        full_name=os.getenv("DEV_ADMIN_NAME", "Admin"),
        role="admin",
        sex="M"
    )
    __get_or_create_dev_user__(
        db,
        email=os.getenv("DEV_CLINICIAN_EMAIL", "doctor@local"),
        full_name=os.getenv("DEV_CLINICIAN_NAME", "doctor"),
        role="doctor",
        sex="F"
    )

def sign_in(
    db: Annotated[Session, Depends(get_db_session)],
    email: str = Header(...),
):
    user = db.execute(select(User).where(User.email == email)).scalars().first()
    if not user:
        raise RuntimeError("User not found")
    token = create_jwt_token(user.id)
    return {"access_token": token, "token_type": "bearer"}

def get_current_user(
    db: Annotated[Session, Depends(get_db_session)],
    header: Annotated[str, Header(..., alias="Authorization")]
) -> User:
    if not header.startswith("Bearer "):
        raise RuntimeError("Invalid authorization header")
    token = header.split(" ")[1]
    user = User()
    try:
        payload = decode_jwt_token(token)
        user_id = payload.get("sub")
        user = db.execute(select(User).where(User.id == user_id)).scalars().first() or User()
    except Exception as e:
        raise RuntimeError("Invalid token") from e
    
    return user

