from __future__ import annotations

import os
from functools import lru_cache
from typing import Optional

from dotenv import load_dotenv

load_dotenv()


@lru_cache(maxsize=1)
def _keyvault_url() -> Optional[str]:
    url = os.getenv("AZURE_KEYVAULT_URL")
    if url:
        return url.rstrip("/") + "/"
    name = os.getenv("KEY_VAULT_NAME")
    if name:
        return f"https://{name}.vault.azure.net/"
    return None


@lru_cache(maxsize=1)
def _keyvault_client():
    vault_url = _keyvault_url()
    if not vault_url:
        return None
    try:
        from azure.identity import DefaultAzureCredential
        from azure.keyvault.secrets import SecretClient
        return SecretClient(vault_url=vault_url, credential=DefaultAzureCredential())
    except Exception as exc:  # pragma: no cover
        import warnings
        warnings.warn(f"Key Vault client init failed: {exc}")
        return None


def _get_secret(name: str, envName: Optional[str] = None) -> Optional[str]:
    client = _keyvault_client()
    if client is not None:
        try:
            return client.get_secret(name).value
        except Exception:
            pass
    return os.getenv(envName or name.replace("-", "_"))


def get_database_connection_schema() -> dict[str, str]:
    return {
        "host": _get_secret("DbHost", "DB_HOST") or "",
        "port": _get_secret("DbPort", "DB_PORT") or "",
        "database": _get_secret("DbName", "DB_NAME") or "",
        "user": _get_secret("DbUser", "DB_USER") or "",
        "password": _get_secret("DbPassword", "DB_PASSWORD") or "",
    }


def get_database_connection_url() -> str:
    url = _get_secret("DbUrl", "DB_URL") or _get_secret("db-url", "DB_URL")
    if url:
        return url

    parts = get_database_connection_schema()
    if all(parts.get(k) for k in ("host", "port", "database", "user", "password")):
        return (
            f"postgresql://{parts['user']}:{parts['password']}"
            f"@{parts['host']}:{parts['port']}/{parts['database']}"
        )

    return "sqlite:///.output/application.db"


def get_openai_api_key() -> Optional[str]:
    return _get_secret("ApiOpenAI", "API_OPENAI")

def get_claude_api_key() -> Optional[str]:
    return _get_secret("ApiClaude", "API_CLAUDE")
