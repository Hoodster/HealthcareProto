from __future__ import annotations

import os

from dotenv import load_dotenv

def get_database_connection_schema() -> dict:
    load_dotenv()
    DB_CONFIG = {
    'host': os.getenv('DB_HOST', ''),
    'port': os.getenv('DB_PORT', ''),
    'database': os.getenv('DB_NAME', ''),
    'user': os.getenv('DB_USER', ''),
    'password': os.getenv('DB_PASSWORD', ''),
    }
    return DB_CONFIG


def get_database_connection_url() -> str:
    load_dotenv()
    return (
        os.getenv('DB_URL')
        or os.getenv("DATABASE_URL")
        or "sqlite:///.output/application.db"
    )


def get_openai_api_key() -> str | None:
    load_dotenv()
    return (
        os.getenv("OPENAI_API_KEY")
        or os.getenv("OPEN_API_KEY")
        or os.getenv("API_OPENAI")
    )


def get_openai_model() -> str:
    load_dotenv()
    return os.getenv("OPENAI_MODEL") or os.getenv("CHAT_MODEL") or "gpt-4o-mini"
