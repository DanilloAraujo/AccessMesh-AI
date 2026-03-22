"""JWT-based authentication utilities for AccessMesh-AI."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from passlib.context import CryptContext  # type: ignore[import]

logger = logging.getLogger(__name__)

_bearer_scheme = HTTPBearer(auto_error=False)
_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def _get_settings():
    from shared.config import settings  # local import avoids circular deps
    return settings


def hash_password(plain: str) -> str:
    """Return a bcrypt hash of *plain*."""
    return _pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """Return True if *plain* matches *hashed* (constant-time comparison)."""
    return _pwd_context.verify(plain, hashed)


# JWT helpers

def create_access_token(subject: str, extra_claims: Optional[dict] = None) -> str:
    """Issue a signed JWT for the given subject (user_id)."""
    from jose import jwt  # type: ignore[import]

    cfg = _get_settings()
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=cfg.jwt_expire_minutes)
    claims = {
        "sub": subject,
        "iat": now,
        "exp": expire,
        "token_type": "access",
        **(extra_claims or {}),
    }
    return jwt.encode(claims, cfg.secret_key, algorithm=cfg.jwt_algorithm)


def create_refresh_token(subject: str) -> str:
    """Issue a long-lived refresh token for the given subject (user_id)."""
    from jose import jwt  # type: ignore[import]

    cfg = _get_settings()
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=cfg.jwt_refresh_expire_minutes)
    claims = {
        "sub": subject,
        "iat": now,
        "exp": expire,
        "token_type": "refresh",
    }
    return jwt.encode(claims, cfg.secret_key, algorithm=cfg.jwt_algorithm)


def decode_refresh_token(token: str) -> dict:
    """Decode and validate a refresh JWT. Raises ValueError on failure."""
    payload = decode_access_token(token)
    if payload.get("token_type") != "refresh":
        raise ValueError("Token is not a refresh token.")
    return payload


def decode_access_token(token: str) -> dict:
    """Decode and validate a JWT. Raises ValueError on failure."""
    from jose import JWTError, jwt  # type: ignore[import]

    cfg = _get_settings()
    if not cfg.secret_key:
        raise ValueError("SECRET_KEY is not configured.")
    try:
        return jwt.decode(token, cfg.secret_key, algorithms=[cfg.jwt_algorithm])
    except JWTError as exc:
        raise ValueError(f"Invalid token: {exc}") from exc


def require_auth(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme),
) -> dict:
    """
    FastAPI dependency that validates a Bearer JWT.

    When SECRET_KEY is not configured the server runs in *open mode*
    and returns a stub payload so all endpoints remain functional during
    local development.  A startup warning is already emitted by config.py.
    """
    cfg = _get_settings()

    if not cfg.secret_key:
        # Open mode — useful in dev environments
        logger.warning(
            "⚠️  AUTH OPEN MODE: SECRET_KEY is not configured. "
            "All requests are accepted as anonymous. Do NOT use in production."
        )
        return {"sub": "anonymous", "mode": "open"}

    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Bearer token required.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        payload = decode_access_token(credentials.credentials)
        return payload
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
