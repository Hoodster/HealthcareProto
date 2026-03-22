from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)
    full_name: str | None = None
    role: str | None = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class AuthResponse(BaseModel):
    token: str
    user_id: str
    email: EmailStr


class ProfileOut(BaseModel):
    user_id: str
    full_name: str | None
    role: str | None
    created_at: dt.datetime

    class Config:
        from_attributes = True
