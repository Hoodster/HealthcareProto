from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


from api.db import init_db
from api.routes.ai_routes import router as ai_router
from api.routes.chat_routes import router as chat_router
from api.routes.patient_routes import router as patient_router


def create_app() -> FastAPI:
    init_db()

    app = FastAPI(
        title="HealthcareProto v011 API",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        root_path="/api",
    )
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["localhost:3000", "http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(patient_router)
    app.include_router(chat_router)
    app.include_router(ai_router)

    @app.get("/health")
    def health():
        return {"status": "ok"}

    return app


app = create_app()
