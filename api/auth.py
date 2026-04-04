from __future__ import annotations

import datetime
import os
import secrets
from typing import Annotated, Optional

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.db import get_db_session
from api.models import Patient, Staff, User

from jwt import JWT, jwk_from_dict

EXAMPLE_SECRET = "aaa2137bbb"
bearer_scheme = HTTPBearer()

HPDbSession = Annotated[Session, Depends(get_db_session)]
HPBearerCredentials = Annotated[HTTPAuthorizationCredentials, Depends(bearer_scheme)]

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
    password: str,
    full_name: str, 
    role: str,
    sex: Optional[str] = None) -> User:
    
    def create_patient_profile(user):
        if not sex:
            raise ValueError("An information about sex must be provided for patient users")
        
        patient = Patient(
            user_id=user.id,
            sex=sex,
            dob=datetime)
        user = User(**user, 
                    patient=patient)   
                 
    def create_staff_profile(user):
        staff = Staff(
            user_id=user.id, 
            role=role,
            )
        user = User(**user, 
                    staff=staff)
    
    existing = db.execute(
        select(User)
        .join(User.staff)
        .join(User.patient)
        .where(User.email == email)).scalars().first()
    
    if existing:
        return existing

    user = User(
        email=email,
        full_name=full_name,
        password_hash=password,
        api_token=secrets.token_hex(24),
    )
    
    if role == "patient":
        create_patient_profile(user)
    elif role in ("doctor", "admin"):
        create_staff_profile(user)
    db.add(user)
    db.flush()
    db.commit()
    db.refresh(user)
    return user


def seed_users(db: Session):

    __get_or_create_dev_user__(
        db,
        email=os.getenv("DEV_ADMIN_EMAIL", 'admin@local'),
        password=os.getenv("DEV_ADMIN_PASSWORD", "admin"),
        full_name=os.getenv("DEV_ADMIN_NAME", "Admin"),
        role="admin"
    )
    __get_or_create_dev_user__(
        db,
        email=os.getenv("DEV_CLINICIAN_EMAIL", "doctor@local"),
        password=os.getenv("DEV_CLINICIAN_PASSWORD", "doctor"),
        full_name=os.getenv("DEV_CLINICIAN_NAME", "doctor"),
        role="doctor"
    )
    __get_or_create_dev_user__(
        db,
        email=os.getenv("DEV_PATIENT_EMAIL", "patient@local"),
        password=os.getenv("DEV_PATIENT_PASSWORD", "patient"),
        full_name=os.getenv("DEV_PATIENT_NAME", "patient"),
        role="patient",
        sex="M"
    )

def sign_in(
    db: HPDbSession,
    email: str,
    password: str
):
    seed_users(db)
    user = db.execute(select(User).where(User.email == email and User.password_hash == password)).scalars().first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    token = create_jwt_token(user.id)
    return {"access_token": token, "token_type": "bearer"}

def get_current_user(
    db: HPDbSession,
    credentials: HPBearerCredentials,
) -> User:
    try:
        user_id = decode_jwt_token(f"Bearer {credentials.credentials}")
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from e

    user = db.execute(select(User).where(User.id == user_id)).scalars().first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    return user

