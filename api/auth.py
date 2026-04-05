from __future__ import annotations

import datetime
import email
import email
import os
import secrets
from typing import Annotated, Optional

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.db import get_db_session
from api.models import Staff, User

from jwt import JWT, jwk_from_dict

from api.services.patient_service import PatientService
from models import schemas
from models.schemas.auth_schema import AccessTokenResponse, LoginOut
from models.schemas.patient_schema import PatientCreate

EXAMPLE_SECRET = "aaa2137bbb"
bearer_scheme = HTTPBearer()

HPDbSession = Annotated[Session, Depends(get_db_session)]
HPBearerCredentials = Annotated[HTTPAuthorizationCredentials, Depends(bearer_scheme)]

def __retrieve_user_by_email__(db: Session, email: str) -> Optional[User]:
    return db.execute(select(User).where(User.email == email)).scalars().first()

def create_jwt_token(user_id: str):
    now = datetime.datetime.now(datetime.UTC)
    payload = {
        "sub": str(user_id),
        "iat": int(now.timestamp()),
        "exp": int((now + datetime.timedelta(hours=1000)).timestamp())
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


def register_user(
    db: Session,
    user_dto: schemas.RegisterRequest,
    skip_verification: bool = False
) -> User:
    
    if not skip_verification:
        existing = __retrieve_user_by_email__(db, user_dto.email)
        if existing:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User already exists")

    user = User(
        email=user_dto.email,
        full_name=user_dto.full_name,
        password_hash=user_dto.password,
        api_token=secrets.token_hex(24),
    )
    db.add(user)
    db.flush()
    return user


def __get_or_create_dev_user__(
    db: Session, 
    *, 
    email: str, 
    password: str,
    full_name: str, 
    role: str,
    dob: Optional[datetime.date] = None,
    sex: Optional[schemas.PatientSex] = None) -> User:
    
    existing = __retrieve_user_by_email__(db, email)
    
    if existing:
        return existing
    
    user = register_user(db, schemas.RegisterRequest(
        email=email,
        password=password,
        full_name=full_name,
        role=role
    ), skip_verification=True)
        
    if role == "patient":
        PatientService.create_patient_profile(db, PatientCreate(
            user_id=user.id,
            dob=dob,
            sex=sex or 'male'
        ))
    elif role == "doctor":
        staff = Staff(user_id=user.id, role="doctor")
        db.add(staff)
        db.commit()
    
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
        sex="male"
    )
    
def get_all_users(db: HPDbSession) -> list[LoginOut]:
    results = db.execute(select(User).where(User.email.endswith("@local"))).scalars().all()
    return [LoginOut(email=user.email, password=user.password_hash or '') for user in results]

def sign_in(
    db: HPDbSession,
    email: str,
    password: str
):
    seed_users(db)
    user = db.execute(
        select(User).where(User.email == email, User.password_hash == password)
    ).scalars().first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    token = create_jwt_token(user.id)
    return AccessTokenResponse(
        access_token=token,
        token_type="Bearer",
        expires_in=3600 * 1000
    ).model_dump()

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

CurrentUser = Annotated[User, Depends(get_current_user)]
