from __future__ import annotations

import os

from dotenv import load_dotenv

def get_database_connection_schema() -> dict[str, str]:
    load_dotenv()
    return {
    'host': os.getenv('DB_HOST', ''),
    'port': os.getenv('DB_PORT', ''),
    'database': os.getenv('DB_NAME', ''),
    'user': os.getenv('DB_USER', ''),
    'password': os.getenv('DB_PASSWORD', ''),
    }


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