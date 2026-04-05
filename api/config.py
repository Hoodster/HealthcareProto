from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()

def get_database_connection_schema() -> dict[str, str]:
    return {
    'host': os.getenv('DB_HOST', ''),
    'port': os.getenv('DB_PORT', ''),
    'database': os.getenv('DB_NAME', ''),
    'user': os.getenv('DB_USER', ''),
    'password': os.getenv('DB_PASSWORD', ''),
    }


def get_database_connection_url() -> str:
    return os.getenv('DB_URL', 'sqlite:///.output/application.db')
    


def get_openai_api_key() -> str | None:
    return os.getenv("OPENAI_API_KEY")