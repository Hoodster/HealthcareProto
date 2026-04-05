from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends

import models.schemas as schemas
from api.auth import CurrentUser, HPDbSession, get_all_users, get_current_user, sign_in
from api.models import User


router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/login", response_model=schemas.AccessTokenResponse)
def login(payload: schemas.LoginRequest, db: HPDbSession) -> dict[str, str]:
    # Password is accepted by the schema for forward compatibility, but current dev auth signs in by email.
    return sign_in(db=db, email=payload.email, password=payload.password)

@router.get("/users", response_model=list[schemas.LoginOut], description="List test user logins")
def list_users(db: HPDbSession):
    return get_all_users(db)

@router.get("/me")
def me(user: CurrentUser) -> dict[str, Any]:
    return {
        "id": user.id,
        "email": user.email,
    }