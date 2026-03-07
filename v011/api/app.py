from __future__ import annotations

from fastapi import FastAPI

from v011.api.config import load_env
from v011.api.db import init_db
from v011.api.routes.ai_routes import router as ai_router
from v011.api.routes.chat_routes import router as chat_router
from v011.api.routes.patient_routes import router as patient_router


def create_app() -> FastAPI:
    load_env()
    init_db()

    app = FastAPI(
        title="HealthcareProto v011 API",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    app.include_router(patient_router)
    app.include_router(chat_router)
    app.include_router(ai_router)

    @app.get("/health")
    def health():
        return {"status": "ok"}

    return app


app = create_app()
