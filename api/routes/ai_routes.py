from __future__ import annotations

from fastapi import APIRouter, Depends

from api.auth import get_current_user
from api.services.ai_service import AIModelService


router = APIRouter(prefix="/ai", tags=["ai"], dependencies=[Depends(get_current_user)])


@router.get("/models")
def list_models():
    service = AIModelService()
    return service.list_models()


@router.post("/chat")
def chat(message: str):
    service = AIModelService()
    return service.chat(message)

