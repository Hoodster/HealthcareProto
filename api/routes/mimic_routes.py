from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

import models.schemas as schemas
from api.services.dummy_service import DummyService
from api.auth import get_db


router = APIRouter(prefix="/chats", tags=["chats"])


@router.post("", response_model=schemas.ChatOut)
def create_chat(
    payload: schemas.ChatCreate,
    db: Session = Depends(get_db),
):
    return DummyService.dummy()
