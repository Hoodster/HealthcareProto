from __future__ import annotations

from fastapi import APIRouter

from v011.api.services.ai_model_service import AIModelService


router = APIRouter(prefix="/ai", tags=["ai"])


@router.get("/models")
def list_models():
    service = AIModelService()
    return service.list_models()
