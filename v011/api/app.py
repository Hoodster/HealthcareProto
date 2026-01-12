from __future__ import annotations

from fastapi import FastAPI

from v011.api.config import load_env
from v011.api.db import init_db
from v011.api.routes.ai_routes import router as ai_router
from v011.api.routes.auth_routes import router as auth_router
from v011.api.routes.chat_routes import router as chat_router
from v011.api.routes.patient_routes import router as patient_router
from v011.api.entra_auth import build_entra_config_from_env, entra_oauth2_urls, swagger_oauth_settings


def create_app() -> FastAPI:
    load_env()
    init_db()

    # Configure Swagger OAuth2 (optional). If ENTRA_* vars are missing, docs still work,
    # but the Authorize button won't be preconfigured.
    swagger_oauth = None
    try:
        cfg = build_entra_config_from_env()
        authorization_url, token_url = entra_oauth2_urls(cfg)
        swagger_oauth = swagger_oauth_settings()
    except Exception:  # noqa: BLE001
        authorization_url, token_url = None, None

    app = FastAPI(
        title="HealthcareProto v011 API",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        swagger_ui_init_oauth=swagger_oauth,
    )

    # Expose useful URLs as part of the OpenAPI description (helps with clients).
    if authorization_url and token_url:
        app.description = (
            "OAuth2 Authorization URL: "
            + authorization_url
            + "\nOAuth2 Token URL: "
            + token_url
        )
    app.include_router(auth_router)
    app.include_router(patient_router)
    app.include_router(chat_router)
    app.include_router(ai_router)

    @app.get("/health")
    def health():
        return {"status": "ok"}

    return app


app = create_app()
