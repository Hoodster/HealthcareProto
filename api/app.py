from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes.auth_routes import router as auth_router
from api.routes.chat_routes import router as chat_router
from api.routes.patient_routes import router as patient_router
from api.routes.mimic_routes import router as mimic_router
from api.routes.evaluation_routes import router as evaluation_router
from api.routes.benchmark_routes import router as benchmark_router
from api.routes.pipeline_routes import router as pipeline_router
from api.routes.documentation_routes import router as documentation_router

import logging

from api.db import SessionLocal, init_db
from api.rag_store import get_rag_status, init_rag_store, sync_patient_documents
from api.drug_db_store import init_drug_db_store

log = logging.getLogger(__name__)


API_PREFIX = "/hp_proto/api"


@asynccontextmanager
async def _lifespan(app: FastAPI):
    init_db()
    init_rag_store()
    init_drug_db_store()
    try:
        db = SessionLocal()
        try:
            sync_stats = sync_patient_documents(db)
            if sync_stats["documents"]:
                log.info(
                    "RAG patient docs synced: %d documents, %d chunks",
                    sync_stats["documents"],
                    sync_stats["chunks"],
                )
        finally:
            db.close()
    except Exception as exc:
        log.warning("RAG patient document sync skipped: %s", exc)
    yield


def create_app() -> FastAPI:
    api_router = APIRouter(prefix=API_PREFIX)

    app = FastAPI(
        title="HealthcareProto API",
        version="0.1.2-beta",
        docs_url=f"{API_PREFIX}/swagger",
        redoc_url=f"{API_PREFIX}/redoc",
        openapi_url=f"{API_PREFIX}/openapi.json",
        lifespan=_lifespan,
    )

    cors_origins = [
        o.strip()
        for o in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
        if o.strip()
    ]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    api_router.include_router(auth_router)
    api_router.include_router(patient_router)
    api_router.include_router(documentation_router)
    api_router.include_router(chat_router)
    api_router.include_router(mimic_router)
    api_router.include_router(evaluation_router)
    api_router.include_router(benchmark_router)
    api_router.include_router(pipeline_router)

    @api_router.get("/health")
    def health(verify_rag: bool = False):
        rag = get_rag_status()
        if verify_rag and rag.get("enabled"):
            from api.rag_store import retrieve_context

            rag["retrieval_ok"] = bool(
                retrieve_context("amiodarone QTc prolongation", top_k=1)
            )
        return {"status": "ok", "rag": rag}

    app.include_router(api_router)

    return app


app = create_app()
