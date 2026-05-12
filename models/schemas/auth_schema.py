from __future__ import annotations

import datetime as dt
from typing import Literal

from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    email: str
    password: str = Field(min_length=6)
    full_name: str
    role: str = 'patient'
    dob: dt.date | None = None
    sex: Literal['male', 'female'] | None = None


class LoginRequest(BaseModel):
    email: str
    password: str


class AccessTokenResponse(BaseModel):
    access_token: str
    token_type: str
    expires_in: int
    

class LoginOut(LoginRequest):
    pass


class ProfileOut(BaseModel):
    user_id: str
    full_name: str
    role: str
    created_at: dt.datetime
