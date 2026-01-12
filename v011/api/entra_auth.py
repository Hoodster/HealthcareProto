from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

import httpx
import jwt
from jwt import PyJWKClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from v011.api.models import EntraIdentity, Profile, User


class EntraAuthError(RuntimeError):
    pass


@dataclass(frozen=True)
class EntraAuthConfig:
    tenant: str
    api_audience: str
    authority_host: str = "https://login.microsoftonline.com"
    token_version: str = "v2.0"
    clock_skew_seconds: int = 60

    @property
    def openid_config_url(self) -> str:
        return f"{self.authority_host}/{self.tenant}/{self.token_version}/.well-known/openid-configuration"


def build_entra_config_from_env() -> EntraAuthConfig:
    tenant = os.getenv("ENTRA_TENANT_ID") or os.getenv("AZURE_TENANT_ID")
    audience = os.getenv("ENTRA_API_AUDIENCE") or os.getenv("ENTRA_CLIENT_ID")
    if not tenant:
        raise EntraAuthError("Missing ENTRA_TENANT_ID (Azure tenant id or domain)")
    if not audience:
        raise EntraAuthError("Missing ENTRA_API_AUDIENCE (recommended) or ENTRA_CLIENT_ID")
    return EntraAuthConfig(tenant=tenant, api_audience=audience)


_openid_cache: dict[str, tuple[float, dict[str, Any]]] = {}
_jwks_client_cache: dict[str, tuple[float, PyJWKClient]] = {}


def _get_openid_config(cfg: EntraAuthConfig) -> dict[str, Any]:
    now = time.time()
    cached = _openid_cache.get(cfg.openid_config_url)
    if cached and (now - cached[0]) < 3600:
        return cached[1]
    with httpx.Client(timeout=10.0) as client:
        resp = client.get(cfg.openid_config_url)
        resp.raise_for_status()
        data = resp.json()
    _openid_cache[cfg.openid_config_url] = (now, data)
    return data


def _get_jwks_client(cfg: EntraAuthConfig) -> PyJWKClient:
    openid = _get_openid_config(cfg)
    jwks_uri = openid.get("jwks_uri")
    if not jwks_uri:
        raise EntraAuthError("OpenID configuration missing jwks_uri")

    now = time.time()
    cached = _jwks_client_cache.get(jwks_uri)
    if cached and (now - cached[0]) < 3600:
        return cached[1]

    client = PyJWKClient(jwks_uri)
    _jwks_client_cache[jwks_uri] = (now, client)
    return client


def validate_entra_access_token(token: str, cfg: EntraAuthConfig) -> Dict[str, Any]:
    openid = _get_openid_config(cfg)
    issuer = openid.get("issuer")
    if not issuer:
        raise EntraAuthError("OpenID configuration missing issuer")

    jwk_client = _get_jwks_client(cfg)
    try:
        signing_key = jwk_client.get_signing_key_from_jwt(token)
    except Exception as exc:  # noqa: BLE001
        raise EntraAuthError(f"Unable to resolve signing key: {exc}")

    # Audience can be either a GUID (app id) or an App ID URI (api://...) depending on registration.
    try:
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=cfg.api_audience,
            issuer=issuer,
            leeway=cfg.clock_skew_seconds,
            options={"require": ["exp", "iss", "aud"]},
        )
    except jwt.ExpiredSignatureError:
        raise EntraAuthError("Token expired")
    except jwt.InvalidAudienceError:
        raise EntraAuthError("Invalid token audience (aud)")
    except jwt.InvalidIssuerError:
        raise EntraAuthError("Invalid token issuer (iss)")
    except jwt.PyJWTError as exc:
        raise EntraAuthError(f"Invalid token: {exc}")

    if not claims.get("tid"):
        raise EntraAuthError("Missing tid claim")
    if not (claims.get("oid") or claims.get("sub")):
        raise EntraAuthError("Missing oid/sub claim")
    return claims


def _email_from_claims(claims: Dict[str, Any]) -> str:
    # Common possibilities in v2 tokens: preferred_username, upn, email
    for key in ("preferred_username", "upn", "email"):
        val = claims.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip().lower()
    oid = str(claims.get("oid") or claims.get("sub"))
    return f"{oid}@entra.local"


def ensure_local_user_for_entra(db: Session, claims: Dict[str, Any]) -> User:
    tenant_id = str(claims["tid"])
    object_id = str(claims.get("oid") or claims.get("sub"))

    stmt = select(EntraIdentity).where(
        EntraIdentity.tenant_id == tenant_id,
        EntraIdentity.object_id == object_id,
    )
    identity = db.execute(stmt).scalars().first()
    if identity:
        user = identity.user
        if not user:
            raise EntraAuthError("Entra identity mapping is corrupted")
        return user

    email = _email_from_claims(claims)
    existing_user = db.execute(select(User).where(User.email == email)).scalars().first()
    if existing_user:
        user = existing_user
    else:
        # password_hash/api_token are legacy fields; keep them populated to satisfy schema.
        user = User(email=email, password_hash="__entra__", api_token=os.urandom(24).hex())
        db.add(user)
        db.flush()
        db.add(Profile(user_id=user.id, full_name=claims.get("name"), role="entra"))

    db.add(EntraIdentity(user_id=user.id, tenant_id=tenant_id, object_id=object_id))
    db.commit()
    db.refresh(user)
    return user


def swagger_oauth_settings() -> dict[str, Any]:
    """Settings passed to FastAPI's swagger_ui_init_oauth.

    For Swagger UI auth you typically use a *separate* Entra public client app (SPA) with PKCE.
    """

    client_id = os.getenv("ENTRA_SWAGGER_CLIENT_ID") or ""
    return {
        "clientId": client_id,
        "usePkceWithAuthorizationCodeGrant": True,
    }


def entra_oauth2_urls(cfg: EntraAuthConfig) -> tuple[str, str]:
    authorization_url = f"{cfg.authority_host}/{cfg.tenant}/oauth2/v2.0/authorize"
    token_url = f"{cfg.authority_host}/{cfg.tenant}/oauth2/v2.0/token"
    return authorization_url, token_url
