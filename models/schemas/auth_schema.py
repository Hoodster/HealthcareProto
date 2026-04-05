from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, Field
from pydantic_core.core_schema import str_schema


class RegisterRequest(BaseModel):
    email: str
    password: str = Field(min_length=6)
    full_name: str | None = None
    role: str | None = None


class LoginRequest(BaseModel):
    email: str
    password: str


class AccessTokenResponse(BaseModel):
    access_token: str
    token_type: str
    expires_in: int


class AuthResponse(BaseModel):
    token: str
    user_id: str
    email: str
    

class LoginOut(LoginRequest):
    pass


class ProfileOut(BaseModel):
    user_id: str
    full_name: str | None
    role: str | None
    created_at: dt.datetime

    class Config:
        from_attributes = True
