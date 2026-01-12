from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from v011.api import schemas
from v011.api.auth import get_current_user, get_db, hash_password, new_token, verify_password
from v011.api.models import Profile, User


router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=schemas.AuthResponse)
def register(req: schemas.RegisterRequest, db: Session = Depends(get_db)):
    existing = db.execute(select(User).where(User.email == req.email)).scalars().first()
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")
    user = User(
        email=req.email,
        password_hash=hash_password(req.password),
        api_token=new_token(),
    )
    db.add(user)
    db.flush()
    profile = Profile(user_id=user.id, full_name=req.full_name, role=req.role)
    db.add(profile)
    db.commit()
    return schemas.AuthResponse(token=user.api_token, user_id=user.id, email=user.email)


@router.post("/login", response_model=schemas.AuthResponse)
def login(req: schemas.LoginRequest, db: Session = Depends(get_db)):
    user = db.execute(select(User).where(User.email == req.email)).scalars().first()
    if not user or not verify_password(req.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    return schemas.AuthResponse(token=user.api_token, user_id=user.id, email=user.email)


@router.get("/me", response_model=schemas.ProfileOut)
def me(user: User = Depends(get_current_user)):
    if not user.profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    return user.profile
