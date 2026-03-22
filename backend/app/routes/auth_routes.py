"""Authentication endpoints for AccessMesh-AI."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, EmailStr, Field

from backend.app.auth import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    hash_password,
    require_auth,
    verify_password,
)
from backend.app.limiter import limiter
from shared.message_schema import CommunicationMode

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Auth"])




class RegisterRequest(BaseModel):
    display_name: str = Field(..., min_length=1, max_length=128)
    email: EmailStr = Field(..., description="Used as login identifier.")
    password: str = Field(..., min_length=8, max_length=128)
    communication_mode: CommunicationMode = Field(default=CommunicationMode.TEXT)
    preferred_language: str = Field(default="en-US", max_length=10)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., max_length=128)


class AuthResponse(BaseModel):
    access_token: str
    refresh_token: str = ""
    token_type: str = "bearer"
    user_id: str
    display_name: str
    communication_mode: str
    preferred_language: str


class PreferencesRequest(BaseModel):
    communication_mode: Optional[CommunicationMode] = None
    preferred_language: Optional[str]   = Field(default=None, max_length=10)
    target_language: Optional[str]      = Field(default=None, max_length=10)
    sign_language: Optional[bool]       = None
    subtitles: Optional[bool]           = None
    audio_description: Optional[bool]   = None
    high_contrast: Optional[bool]       = None
    large_text: Optional[bool]          = None
    translation_enabled: Optional[bool] = None


class PreferencesResponse(BaseModel):
    status: str
    user_id: str
    communication_mode: str
    preferred_language: str




class TokenRequest(BaseModel):
    user_id: str = Field(..., max_length=128, description="Participant user identifier.")
    display_name: str = Field(default="", max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str


@router.post(
    "/token",
    response_model=TokenResponse,
    summary="[Dev] Issue a JWT for any user_id (no password required)",
)
def issue_token(body: TokenRequest) -> TokenResponse:
    """
    Dev shortcut — disabled in production (requires app_debug=True).
    In production, use /auth/register + /auth/login.
    """
    from shared.config import settings as _settings  # noqa: PLC0415
    if not _settings.app_debug:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This endpoint is only available in debug/development mode.",
        )
    if not body.user_id.strip():
        raise HTTPException(status_code=422, detail="user_id cannot be empty.")
    token = create_access_token(
        subject=body.user_id,
        extra_claims={"display_name": body.display_name},
    )
    logger.info("Auth: dev JWT issued for user_id=%s", body.user_id)
    return TokenResponse(access_token=token, user_id=body.user_id)




@router.post(
    "/register",
    response_model=AuthResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new account",
)
@limiter.limit("10/minute")
async def register(request: Request, body: RegisterRequest) -> AuthResponse:
    """
    Creates a new user account.

    1. Checks email uniqueness via Cosmos DB (falls back gracefully when Cosmos is offline).
    2. Stores user document with bcrypt-hashed password.
    3. Returns a JWT immediately — no separate login step required.
    """
    cosmos = getattr(request.app.state, "cosmos", None)

    if cosmos and cosmos.is_enabled:
        existing = await cosmos.get_user_by_email(body.email)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An account with this email already exists.",
            )

    from uuid import uuid4
    user_id = str(uuid4())
    now_iso = datetime.now(timezone.utc).isoformat()

    user_doc: Dict[str, Any] = {
        "user_id": user_id,
        "display_name": body.display_name,
        "email": body.email,
        "hashed_password": hash_password(body.password),
        "communication_mode": body.communication_mode.value,
        "preferred_language": body.preferred_language,
        "target_language": body.preferred_language,
        "sign_language": body.communication_mode == CommunicationMode.SIGN_LANGUAGE,
        "subtitles": True,
        "audio_description": False,
        "high_contrast": False,
        "large_text": False,
        "translation_enabled": False,
        "created_at": now_iso,
        "last_seen": now_iso,
    }

    if cosmos and cosmos.is_enabled:
        await cosmos.upsert_user(user_id, user_doc)

    token = create_access_token(
        subject=user_id,
        extra_claims={
            "display_name": body.display_name,
            "email": body.email,
            "communication_mode": body.communication_mode.value,
            "preferred_language": body.preferred_language,
        },
    )
    logger.info("Auth: registered user_id=%s email=%s", user_id, body.email)
    return AuthResponse(
        access_token=token,
        refresh_token=create_refresh_token(user_id),
        user_id=user_id,
        display_name=body.display_name,
        communication_mode=body.communication_mode.value,
        preferred_language=body.preferred_language,
    )




@router.post(
    "/login",
    response_model=AuthResponse,
    summary="Authenticate with email and password",
)
@limiter.limit("10/minute")
async def login(request: Request, body: LoginRequest) -> AuthResponse:
    """
    Verify credentials and return a JWT with user claims.

    When Cosmos DB is offline the endpoint falls back to open mode (for
    local dev scenarios where no DB is configured).
    """
    cosmos = getattr(request.app.state, "cosmos", None)

    if cosmos and cosmos.is_enabled:
        user_doc = await cosmos.get_user_by_email(body.email)
        if not user_doc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password.",
            )
        if not verify_password(body.password, user_doc.get("hashed_password", "")):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password.",
            )
        # Refresh last_seen
        await cosmos.upsert_user(
            user_doc["user_id"],
            {**user_doc, "last_seen": datetime.now(timezone.utc).isoformat()},
        )
        token = create_access_token(
            subject=user_doc["user_id"],
            extra_claims={
                "display_name": user_doc.get("display_name", ""),
                "email": user_doc.get("email", ""),
                "communication_mode": user_doc.get("communication_mode", CommunicationMode.TEXT.value),
                "preferred_language": user_doc.get("preferred_language", "en-US"),
            },
        )
        logger.info("Auth: login user_id=%s", user_doc["user_id"])
        return AuthResponse(
            access_token=token,
            refresh_token=create_refresh_token(user_doc["user_id"]),
            user_id=user_doc["user_id"],
            display_name=user_doc.get("display_name", ""),
            communication_mode=user_doc.get("communication_mode", CommunicationMode.TEXT.value),
            preferred_language=user_doc.get("preferred_language", "en-US"),
        )

    # Cosmos offline — return 503 instead of issuing an open-mode token
    logger.warning("Auth: Cosmos offline, returning 503 for email=%s", body.email)
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Authentication service temporarily unavailable. Please try again later.",
    )




class RefreshRequest(BaseModel):
    refresh_token: str = Field(..., description="Refresh JWT issued during login/register.")


@router.post(
    "/refresh",
    response_model=AuthResponse,
    summary="Exchange a refresh token for a new access + refresh token pair",
)
@limiter.limit("20/minute")
async def refresh(request: Request, body: RefreshRequest) -> AuthResponse:
    """
    Issue a new access token (and rotate the refresh token) using a
    valid refresh JWT.  This allows the client to maintain sessions
    without re-entering credentials.
    """
    try:
        payload = decode_refresh_token(body.refresh_token)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        ) from exc

    user_id = payload.get("sub", "")
    if not user_id:
        raise HTTPException(status_code=422, detail="No sub in refresh token.")

    # Fetch latest user doc for fresh claims
    cosmos = getattr(request.app.state, "cosmos", None)
    user_doc: Dict[str, Any] = {}
    if cosmos and cosmos.is_enabled:
        user_doc = await cosmos.get_user(user_id) or {}

    access_token = create_access_token(
        subject=user_id,
        extra_claims={
            "display_name": user_doc.get("display_name", payload.get("display_name", "")),
            "email": user_doc.get("email", payload.get("email", "")),
            "communication_mode": user_doc.get("communication_mode", "text"),
            "preferred_language": user_doc.get("preferred_language", "en-US"),
        },
    )
    new_refresh = create_refresh_token(user_id)

    logger.info("Auth: refreshed tokens for user_id=%s", user_id)
    return AuthResponse(
        access_token=access_token,
        refresh_token=new_refresh,
        user_id=user_id,
        display_name=user_doc.get("display_name", payload.get("display_name", "")),
        communication_mode=user_doc.get("communication_mode", "text"),
        preferred_language=user_doc.get("preferred_language", "en-US"),
    )




@router.get(
    "/me",
    summary="Validate token and return claims",
)
def get_me(claims: dict = Depends(require_auth)) -> dict:
    """Return the decoded claims of the current Bearer token."""
    return {"user_id": claims.get("sub"), "claims": claims}


@router.put(
    "/me/preferences",
    response_model=PreferencesResponse,
    summary="Update communication mode and accessibility preferences",
)
async def update_preferences(
    request: Request,
    body: PreferencesRequest,
    claims: dict = Depends(require_auth),
) -> PreferencesResponse:
    """
    Persist user preferences to Cosmos DB.

    Allows any channel (web, mobile, Teams adapter) to update the user's
    preferred communication_mode and accessibility settings.  Changes are
    reflected on the next login / JWT refresh.
    """
    user_id: str = claims.get("sub", "")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="No sub in token.")

    cosmos = getattr(request.app.state, "cosmos", None)

    # Load existing document; fall back to a minimal stub when Cosmos is offline.
    existing: Dict[str, Any] = {}
    if cosmos and cosmos.is_enabled:
        existing = await cosmos.get_user(user_id) or {}

    # Merge — only update fields that were explicitly provided.
    updates: Dict[str, Any] = {
        "last_seen": datetime.now(timezone.utc).isoformat(),
    }
    if body.communication_mode is not None:
        updates["communication_mode"] = body.communication_mode.value
    if body.preferred_language is not None:
        updates["preferred_language"] = body.preferred_language
    if body.target_language is not None:
        updates["target_language"] = body.target_language
    if body.sign_language is not None:
        updates["sign_language"] = body.sign_language
    if body.subtitles is not None:
        updates["subtitles"] = body.subtitles
    if body.audio_description is not None:
        updates["audio_description"] = body.audio_description
    if body.high_contrast is not None:
        updates["high_contrast"] = body.high_contrast
    if body.large_text is not None:
        updates["large_text"] = body.large_text
    if body.translation_enabled is not None:
        updates["translation_enabled"] = body.translation_enabled

    merged = {**existing, **updates}

    if cosmos and cosmos.is_enabled:
        await cosmos.upsert_user(user_id, merged)

    comm_mode = merged.get("communication_mode", CommunicationMode.TEXT.value)
    pref_lang = merged.get("preferred_language", "en-US")

    logger.info(
        "Auth: preferences updated user_id=%s mode=%s lang=%s",
        user_id, comm_mode, pref_lang,
    )
    return PreferencesResponse(
        status="updated",
        user_id=user_id,
        communication_mode=comm_mode,
        preferred_language=pref_lang,
    )
