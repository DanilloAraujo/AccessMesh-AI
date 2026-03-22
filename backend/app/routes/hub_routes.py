"""Unified omni-channel message endpoint."""

from __future__ import annotations

import logging
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from backend.app.auth import require_auth
from backend.app.limiter import limiter
from backend.app.message_router import MessageRouter
from backend.app.session_store import append_message

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/hub", tags=["Hub"])



def _get_router(request: Request) -> MessageRouter:
    r: Optional[MessageRouter] = getattr(request.app.state, "message_router", None)
    if r is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MessageRouter not initialised.",
        )
    return r


def _get_cosmos(request: Request):
    """Return CosmosService if enabled, else None."""
    cosmos = getattr(request.app.state, "cosmos", None)
    if cosmos and getattr(cosmos, "is_enabled", False):
        return cosmos
    return None


async def _save_message(request: Request, session_id: str, payload: dict) -> None:
    """Persist to Cosmos if available, fall back to in-memory session_store."""
    cosmos = _get_cosmos(request)
    if cosmos:
        try:
            await cosmos.append_message(session_id, payload)
            return
        except Exception as _ce:
            logger.warning("[hub_routes] Cosmos save failed (fallback to memory): %s", _ce)
    await append_message(session_id, payload)



class HubMessageRequest(BaseModel):
    """
    Unified omni-channel message request.

    For speech / text:  populate ``content`` with the transcribed / typed text.
    For gesture:        populate ``content`` with the gesture label
                        (e.g. ``"thumbs_up"``) OR set ``gesture_label``.
    """

    channel: str = Field(
        default="web",
        max_length=64,
        description=(
            "Origin channel — 'web', 'mobile', 'video', 'teams', 'slack', 'call-center'."
            " All channels converge to the same hub (RB05 omnichannel)."
        ),
    )
    input_type: Literal["speech", "gesture", "text"] = Field(
        ...,
        description="Modality of the input.",
    )
    content: str = Field(
        ...,
        max_length=4_000,
        description="Transcribed text, typed message, or gesture label.",
    )
    session_id: str = Field(..., max_length=128)
    user_id: str    = Field(..., max_length=128)
    language: str   = Field(default="en-US", max_length=10)
    target_language: str = Field(default="en-US", max_length=10)
    display_name: str    = Field(default="", max_length=256)


class HubMessageResponse(BaseModel):
    message_id: str
    source: str
    text: str
    features_applied: list[str]
    sign_gloss: Optional[list[dict]] = None
    translated_content: Optional[str] = None
    audio_b64: Optional[str] = None



@router.post(
    "/message",
    response_model=HubMessageResponse,
    summary="Unified omni-channel message endpoint (RB04/RB05)",
)
@limiter.limit("30/minute")
async def hub_message(
    request: Request,
    body: HubMessageRequest,
    msg_router: MessageRouter = Depends(_get_router),
    _claims: dict = Depends(require_auth),
) -> HubMessageResponse:
    """
    Dispatch a multimodal message through the full agent pipeline and
    broadcast the result to all session participants.

    Returns the enriched AccessibleMessage for optimistic UI updates.
    """
    if not body.content.strip():
        raise HTTPException(status_code=422, detail="content cannot be empty.")

    logger.info(
        "hub_message: channel=%s input_type=%s session=%s user=%s",
        body.channel, body.input_type, body.session_id, body.user_id,
    )

    try:
        if body.input_type == "speech":
            payload = await msg_router.route_voice(
                body.content,
                session_id=body.session_id,
                user_id=body.user_id,
                language=body.language,
                target_language=body.target_language,
                display_name=body.display_name,
            )
        elif body.input_type == "gesture":
            payload = await msg_router.route_gesture(
                body.content,
                session_id=body.session_id,
                user_id=body.user_id,
                language=body.language,
                target_language=body.target_language,
                display_name=body.display_name,
            )
        else:  # "text"
            payload = await msg_router.route_chat(
                body.content,
                session_id=body.session_id,
                user_id=body.user_id,
                display_name=body.display_name,
                target_language=body.target_language,
            )
    except Exception as exc:
        logger.exception("hub_message dispatch failed — input_type=%s", body.input_type)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    # Persist every modality (gesture, speech, text) to history so late-joining
    # participants see the full conversation when _loadHistory() is called.
    await _save_message(request, body.session_id, payload)

    return HubMessageResponse(
        message_id=payload.get("id", ""),
        source=payload.get("source", body.input_type),
        text=payload.get("content", body.content),
        features_applied=payload.get("features_applied", []),
        sign_gloss=payload.get("sign_gloss") or None,
        translated_content=payload.get("translated_content"),
        audio_b64=payload.get("audio_b64"),
    )
