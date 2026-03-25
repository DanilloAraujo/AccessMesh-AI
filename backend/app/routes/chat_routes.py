"""Plain-text chat endpoints exposed at /chat/*."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from backend.app.auth import require_auth
from backend.app.limiter import limiter
from backend.app.message_router import MessageRouter
from backend.app.session_store import append_message, get_messages_async
from services.summarization_service import SummarizationService
from shared.message_schema import BaseMessage, MeetingSummaryMessage, MessageType

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["Chat"])


def _get_cosmos(request: Request):
    """Return CosmosService if enabled, else None."""
    cosmos = getattr(request.app.state, "cosmos", None)
    if cosmos and getattr(cosmos, "is_enabled", False):
        return cosmos
    return None


def _get_router(request: Request) -> MessageRouter:
    r: Optional[MessageRouter] = getattr(request.app.state, "message_router", None)
    if r is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MessageRouter not initialised.",
        )
    return r


def _get_summary_svc(request: Request) -> SummarizationService:
    svc: Optional[SummarizationService] = getattr(request.app.state, "summarization", None)
    if svc is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="SummarizationService not initialised.",
        )
    return svc



class ChatSendRequest(BaseModel):
    text: str         = Field(..., max_length=4_000, description="Message content.")
    session_id: str   = Field(..., max_length=128,   description="Session / room identifier.")
    user_id: str      = Field(..., max_length=128,   description="Sender user_id.")
    display_name: str = Field(default="", max_length=128, description="Sender display name.")
    language: str     = Field(default="en-US", max_length=10, description="BCP-47 source language of the sender.")


class ChatSendResponse(BaseModel):
    status: str
    session_id: str
    from_user: str
    message_id: str
    text: str
    features_applied: list[str] = []
    sign_gloss: Optional[list[dict]] = None
    audio_b64: Optional[str] = None



@router.post(
    "/send",
    response_model=ChatSendResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Broadcast a chat message to the session",
)
@limiter.limit("30/minute")
async def send_message(
    request: Request,
    body: ChatSendRequest,
    msg_router: MessageRouter = Depends(_get_router),
    _claims: dict = Depends(require_auth),
) -> ChatSendResponse:
    """
    Routes a plain-text chat message through the AI pipeline
    (router → accessibility) and broadcasts the enriched result
    (with sign_gloss) to all participants in the session.
    """
    if not body.text.strip():
        raise HTTPException(status_code=422, detail="text cannot be empty.")

    try:
        payload = await msg_router.route_chat(
            body.text,
            session_id=body.session_id,
            user_id=body.user_id,
            display_name=body.display_name,
            language=body.language,
        )

        # Persist via session_store which resolves Cosmos → memory fallback internally
        await append_message(body.session_id, payload)

        return ChatSendResponse(
            status="sent",
            session_id=body.session_id,
            from_user=body.display_name or body.user_id,
            message_id=payload["id"],
            text=payload["content"],
            features_applied=payload.get("features_applied", []),
            sign_gloss=payload.get("sign_gloss"),
            audio_b64=payload.get("audio_b64"),
        )
    except Exception as exc:
        logger.exception("Error routing chat message")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get(
    "/history/{session_id}",
    summary="Return message history for a session",
)
async def get_history(
    session_id: str,
    request: Request,
    _claims: dict = Depends(require_auth),
) -> Dict[str, Any]:
    """Return the last up to 200 messages for the given session."""
    messages = await get_messages_async(session_id)
    source = "cosmos" if _get_cosmos(request) else "memory"
    return {"session_id": session_id, "messages": messages, "count": len(messages), "source": source}


class SummaryRequestBody(BaseModel):
    user_id: str = Field(default="system", max_length=128, description="User requesting the summary.")


@router.post(
    "/summary/{session_id}",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Request an async meeting summary (Ata) via Service Bus",
)
async def request_summary(
    session_id: str,
    request: Request,
    body: SummaryRequestBody = SummaryRequestBody(),
    _claims: dict = Depends(require_auth),
) -> Dict[str, Any]:
    """
    Enqueues a SUMMARY_REQUEST event on the Agent Bus.

    When Service Bus is configured, the event is forwarded to the
    ``sub-summary-request`` subscription where the SummaryAgent worker
    picks it up, reads the full history from Cosmos, calls GPT-4o and
    delivers the resulting SUMMARY event back via WebPubSub — without
    blocking this HTTP request.

    When Service Bus is not configured (local dev), the summary is
    generated synchronously and returned directly.
    """
    pipeline = getattr(request.app.state, "pipeline", None)
    bus = getattr(pipeline, "_bus", None) if pipeline else None
    sb_service = getattr(request.app.state, "servicebus", None)
    sb_enabled = sb_service and getattr(sb_service, "is_enabled", False)

    if bus and sb_enabled:
        # Async path: publish SUMMARY_REQUEST → SB → SummaryAgent worker
        summary_request = BaseMessage(
            session_id=session_id,
            sender_id=body.user_id,
            message_type=MessageType.SUMMARY_REQUEST,
            metadata={"requested_by": body.user_id},
        )
        asyncio.create_task(
            bus.publish(summary_request),
            name=f"chat-routes:summary-request:{session_id}",
        )
        logger.info(
            "[request_summary] SUMMARY_REQUEST enqueued on bus for session=%s", session_id
        )
        return {
            "status": "processing",
            "session_id": session_id,
            "message": "Summary generation started. Result will be delivered via WebSocket.",
        }

    # Fallback: synchronous generation when SB unavailable (local dev)
    logger.info(
        "[request_summary] SB unavailable — generating summary synchronously for session=%s",
        session_id,
    )
    messages = await get_messages_async(session_id)
    if not messages:
        return {
            "session_id": session_id,
            "summary": "No messages recorded for this session yet.",
            "key_points": [],
            "message_count": 0,
            "stub": True,
        }

    summary_svc: SummarizationService = _get_summary_svc(request)
    texts = [m.get("content", "") for m in messages if m.get("content", "").strip()]
    result = await summary_svc.summarise(texts)
    result["session_id"] = session_id
    result["message_count"] = len(texts)

    # Publish SUMMARY event so it is forwarded to SB sub-summary and WebPubSub
    if bus:
        summary_msg = MeetingSummaryMessage(
            session_id=session_id,
            sender_id="system",
            message_type=MessageType.SUMMARY,
            summary_text=result.get("summary", ""),
            key_points=result.get("key_points", []),
            participant_ids=[],
            total_messages=len(texts),
        )
        asyncio.create_task(
            bus.publish(summary_msg),
            name=f"chat-routes:summary-publish:{session_id}",
        )
    return result


@router.get(
    "/summary/{session_id}",
    summary="[DEPRECATED] Synchronous summary — use POST /summary/{session_id} instead",
    deprecated=True,
)
async def get_summary_legacy(
    session_id: str,
    request: Request,
    summary_svc: SummarizationService = Depends(_get_summary_svc),
    _claims: dict = Depends(require_auth),
) -> Dict[str, Any]:
    """
    Legacy synchronous endpoint kept for backwards compatibility.
    Prefer POST /chat/summary/{session_id} which returns 202 immediately
    and delivers the result via WebSocket without blocking the client.
    """
    messages = await get_messages_async(session_id)
    if not messages:
        return {
            "session_id": session_id,
            "summary": "No messages recorded for this session yet.",
            "key_points": [],
            "message_count": 0,
            "stub": True,
        }

    texts = [m.get("content", "") for m in messages if m.get("content", "").strip()]
    result = await summary_svc.summarise(texts)
    result["session_id"] = session_id
    result["message_count"] = len(texts)

    try:
        pipeline = getattr(request.app.state, "pipeline", None)
        if pipeline and getattr(pipeline, "_bus", None):
            summary_msg = MeetingSummaryMessage(
                session_id=session_id,
                sender_id="system",
                message_type=MessageType.SUMMARY,
                summary_text=result.get("summary", ""),
                key_points=result.get("key_points", []),
                participant_ids=[],
                total_messages=len(texts),
            )
            asyncio.create_task(
                pipeline._bus.publish(summary_msg),
                name=f"chat-routes:summary-publish:{session_id}",
            )
    except Exception as _sb_exc:
        logger.warning("[get_summary_legacy] Failed to publish SUMMARY to agent bus: %s", _sb_exc)

    return result


def _get_cosmos(request: Request):
    """Return CosmosService if enabled, else None."""
    cosmos = getattr(request.app.state, "cosmos", None)
    if cosmos and getattr(cosmos, "is_enabled", False):
        return cosmos
    return None


def _get_router(request: Request) -> MessageRouter:
    r: Optional[MessageRouter] = getattr(request.app.state, "message_router", None)
    if r is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MessageRouter not initialised.",
        )
    return r


def _get_summary_svc(request: Request) -> SummarizationService:
    svc: Optional[SummarizationService] = getattr(request.app.state, "summarization", None)
    if svc is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="SummarizationService not initialised.",
        )
    return svc



class ChatSendRequest(BaseModel):
    text: str         = Field(..., max_length=4_000, description="Message content.")
    session_id: str   = Field(..., max_length=128,   description="Session / room identifier.")
    user_id: str      = Field(..., max_length=128,   description="Sender user_id.")
    display_name: str = Field(default="", max_length=128, description="Sender display name.")
    language: str     = Field(default="en-US", max_length=10, description="BCP-47 source language of the sender.")


class ChatSendResponse(BaseModel):
    status: str
    session_id: str
    from_user: str
    message_id: str
    text: str
    features_applied: list[str] = []
    sign_gloss: Optional[list[dict]] = None
    audio_b64: Optional[str] = None



@router.post(
    "/send",
    response_model=ChatSendResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Broadcast a chat message to the session",
)
@limiter.limit("30/minute")
async def send_message(
    request: Request,
    body: ChatSendRequest,
    msg_router: MessageRouter = Depends(_get_router),
    _claims: dict = Depends(require_auth),
) -> ChatSendResponse:
    """
    Routes a plain-text chat message through the AI pipeline
    (router → accessibility) and broadcasts the enriched result
    (with sign_gloss) to all participants in the session.
    """
    if not body.text.strip():
        raise HTTPException(status_code=422, detail="text cannot be empty.")

    try:
        payload = await msg_router.route_chat(
            body.text,
            session_id=body.session_id,
            user_id=body.user_id,
            display_name=body.display_name,
            language=body.language,
        )

        cosmos = _get_cosmos(request)
        if cosmos:
            # Persist to Cosmos DB asynchronously (non-blocking)
            try:
                await cosmos.append_message(body.session_id, payload)
            except Exception as _ce:
                logger.warning("[chat_routes] Cosmos save failed (fallback to memory): %s", _ce)
                await append_message(body.session_id, payload)
        else:
            await append_message(body.session_id, payload)

        return ChatSendResponse(
            status="sent",
            session_id=body.session_id,
            from_user=body.display_name or body.user_id,
            message_id=payload["id"],
            text=payload["content"],
            features_applied=payload.get("features_applied", []),
            sign_gloss=payload.get("sign_gloss"),
            audio_b64=payload.get("audio_b64"),
        )
    except Exception as exc:
        logger.exception("Error routing chat message")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get(
    "/history/{session_id}",
    summary="Return message history for a session",
)
async def get_history(
    session_id: str,
    request: Request,
    _claims: dict = Depends(require_auth),
) -> Dict[str, Any]:
    """Return the last up to 200 messages for the given session."""
    cosmos = _get_cosmos(request)
    if cosmos:
        try:
            messages = await cosmos.get_messages(session_id)
            return {"session_id": session_id, "messages": messages, "count": len(messages), "source": "cosmos"}
        except Exception as _ce:
            logger.warning("[chat_routes] Cosmos read failed (fallback to memory): %s", _ce)

    msgs = get_messages(session_id)
    return {"session_id": session_id, "messages": msgs, "count": len(msgs), "source": "memory"}


@router.get(
    "/summary/{session_id}",
    summary="Generate a meeting summary (Ata) for the session",
)
async def get_summary(
    session_id: str,
    request: Request,
    summary_svc: SummarizationService = Depends(_get_summary_svc),
    _claims: dict = Depends(require_auth),
) -> Dict[str, Any]:
    """
    Runs the SummarizationService over all messages recorded for the session.
    Returns a structured summary with key points.
    """
    # 1. Cosmos DB is the primary store: it holds all messages that survived
    #    across restarts and captures every modality (chat, speech, gesture).
    #    With unique room IDs generated by the frontend, each session_id maps
    #    to exactly one meeting — no cross-session contamination.
    cosmos = _get_cosmos(request)
    messages: List[Dict[str, Any]] = []
    if cosmos:
        try:
            messages = await cosmos.get_messages(session_id)
            logger.info("[get_summary] Loaded %d messages from Cosmos for session %s", len(messages), session_id)
        except Exception as _ce:
            logger.warning("[get_summary] Cosmos read failed, falling back to memory: %s", _ce)

    # 2. Fall back to in-memory store (local dev / Cosmos unavailable).
    if not messages:
        messages = get_messages(session_id)
        logger.info("[get_summary] Loaded %d messages from memory for session %s", len(messages), session_id)

    if not messages:
        return {
            "session_id": session_id,
            "summary": "No messages recorded for this session yet.",
            "key_points": [],
            "message_count": 0,
            "stub": True,
        }

    texts = [m.get("content", "") for m in messages if m.get("content", "").strip()]
    result = await summary_svc.summarise(texts)
    result["session_id"] = session_id
    result["message_count"] = len(texts)

    # Publish a SUMMARY event to the Agent Bus so it is forwarded to the
    # Azure Service Bus topic (sub-summary subscription) for external consumers.
    try:
        pipeline = getattr(request.app.state, "pipeline", None)
        if pipeline and getattr(pipeline, "_bus", None):
            summary_msg = MeetingSummaryMessage(
                session_id=session_id,
                sender_id="system",
                message_type=MessageType.SUMMARY,
                summary_text=result.get("summary", ""),
                key_points=result.get("key_points", []),
                participant_ids=[],
                total_messages=len(texts),
            )
            asyncio.create_task(
                pipeline._bus.publish(summary_msg),
                name=f"chat-routes:summary-publish:{session_id}",
            )
            logger.info("[get_summary] SUMMARY event queued on Agent Bus for session %s", session_id)
    except Exception as _sb_exc:
        logger.warning("[get_summary] Failed to publish SUMMARY to agent bus: %s", _sb_exc)

    return result
