from __future__ import annotations

import os

def get_database_url() -> str:
    return (
        os.getenv("V011_DATABASE_URL")
        or os.getenv("DATABASE_URL")
        or "sqlite:///.output/application.db"
    )


def get_openai_api_key() -> str | None:
    return (
        os.getenv("OPENAI_API_KEY")
        or os.getenv("OPEN_API_KEY")
        or os.getenv("API_OPENAI")
    )


def get_openai_model() -> str:
    return os.getenv("OPENAI_MODEL") or os.getenv("CHAT_MODEL") or "gpt-4o-mini"
