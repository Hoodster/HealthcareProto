from __future__ import annotations

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware


from api.db import init_db
from api.routes.ai_routes import router as ai_router
from api.routes.chat_routes import router as chat_router
from api.routes.patient_routes import router as patient_router
from api.routes.mimic_routes import router as mimic_router
from api.routes.evaluation_routes import router as evaluation_router
from api.routes.benchmark_routes import router as benchmark_router

from scripts.init_mimic_db import connect, connect_db


API_PREFIX = "/hp_proto/api"


def create_app() -> FastAPI:
    init_db()
    connect_db()
    api_router = APIRouter(prefix=API_PREFIX)

    app = FastAPI(
        title="HealthcareProto API",
        version="0.1.2-beta",
        docs_url=f"{API_PREFIX}/swagger",
        redoc_url=f"{API_PREFIX}/redoc",
        openapi_url=f"{API_PREFIX}/openapi.json",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    api_router.include_router(patient_router)
    api_router.include_router(chat_router)
    api_router.include_router(ai_router)
    api_router.include_router(mimic_router)
    api_router.include_router(evaluation_router)
    api_router.include_router(benchmark_router)

    @api_router.get("/health")
    def health():
        return {"status": "ok"}

    app.include_router(api_router)

    return app


app = create_app()
