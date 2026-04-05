from __future__ import annotations

from fastapi import APIRouter

from api.services.ai_service import AIModelService


router = APIRouter(prefix="/ai", tags=["ai"])


@router.get("/models")
def list_models():
    service = AIModelService()
    return service.list_models()


@router.post("/chat")
def chat(message: str):
    service = AIModelService()
    return service.chat(message)

