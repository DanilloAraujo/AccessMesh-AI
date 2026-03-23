"""Speech-pipeline endpoints exposed at /speech/*."""

from __future__ import annotations

import base64
import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from pydantic import BaseModel, Field

from backend.app.auth import require_auth
from backend.app.limiter import limiter
from backend.app.message_router import MessageRouter
from backend.app.session_store import append_message
from mcp.mcp_client import mcp_client as _mcp_client
from typing import Any, Dict

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/speech", tags=["Speech"])



def _get_cosmos(request: Request):
    """Return CosmosService if enabled, else None."""
    cosmos = getattr(request.app.state, "cosmos", None)
    if cosmos and getattr(cosmos, "is_enabled", False):
        return cosmos
    return None


async def _save_message(request: Request, session_id: str, payload: Dict[str, Any]) -> None:
    """Persist to Cosmos if available, fall back to in-memory session_store."""
    cosmos = _get_cosmos(request)
    if cosmos:
        try:
            await cosmos.append_message(session_id, payload)
            return
        except Exception as _ce:
            logger.warning("[speech_routes] Cosmos save failed (fallback to memory): %s", _ce)
    await append_message(session_id, payload)


def _get_router(request: Request) -> MessageRouter:
    r: Optional[MessageRouter] = getattr(request.app.state, "message_router", None)
    if r is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MessageRouter not initialised.",
        )
    return r


def _get_speech_service(request: Request):
    svc = getattr(request.app.state, "speech", None)
    if svc is None or not svc.is_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Speech service not configured. Set AZURE_SPEECH_KEY and AZURE_SPEECH_REGION.",
        )
    return svc



class VoiceRequest(BaseModel):
    text: str        = Field(..., max_length=4_000, description="Transcribed speech text.")
    session_id: str  = Field(..., max_length=128,   description="Session / room identifier.")
    user_id: str     = Field(..., max_length=128,   description="Participant user_id.")
    display_name: str = Field(default="", max_length=128, description="Sender display name shown in conversation.")
    language: str    = Field(default="en-US", max_length=10, description="BCP-47 language tag.")
    target_language: str = Field(default="en-US", max_length=10, description="BCP-47 target language for translation.")


class VoiceResponse(BaseModel):
    message_id: str
    text: str
    source: str
    features_applied: List[str]
    translated_content: Optional[str] = None


class SpeechTokenResponse(BaseModel):
    token: str
    region: str


class TranscribeResponse(BaseModel):
    text: str
    confidence: float
    language: str



@router.post(
    "/voice",
    response_model=VoiceResponse,
    summary="Process transcribed speech through the agent pipeline",
)
@limiter.limit("30/minute")
async def process_voice(
    request: Request,
    body: VoiceRequest,
    msg_router: MessageRouter = Depends(_get_router),
    _claims: dict = Depends(require_auth),
) -> VoiceResponse:
    """
    Receives browser-transcribed text and runs it through:
      RouterAgent → AccessibilityAgent ‖ TranslationAgent → fan-in ACCESSIBLE
    Then broadcasts the result to all session participants.
    """
    if not body.text.strip():
        raise HTTPException(status_code=422, detail="text cannot be empty.")

    logger.info(
        "[/speech/voice] → session=%s user=%s lang=%s target=%s text=%s",
        body.session_id, body.user_id, body.language, body.target_language, body.text[:80],
    )
    try:
        payload = await msg_router.route_voice(
            body.text,
            session_id=body.session_id,
            user_id=body.user_id,
            language=body.language,
            target_language=body.target_language,
            display_name=body.display_name,
        )
        logger.info(
            "[/speech/voice] ← id=%s features=%s",
            payload.get('id'), payload.get('features_applied'),
        )
        # Persist to Cosmos (primary) or in-memory store (fallback).
        await _save_message(request, body.session_id, payload)
        return VoiceResponse(
            message_id=payload.get("id", ""),
            text=payload.get("content", body.text),
            source="voice",
            features_applied=payload.get("features_applied", []),
            translated_content=payload.get("translated_content"),
        )
    except Exception as exc:
        logger.exception("Error processing voice input")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post(
    "/recognize",
    response_model=VoiceResponse,
    summary="Upload audio → transcribe via MCP → run full agent pipeline",
)
@limiter.limit("20/minute")
async def recognize_audio(
    request: Request,
    audio: UploadFile = File(..., description="WebM/Opus from MediaRecorder (≤ 10 MB)."),
    session_id: str  = Form(..., max_length=128),
    user_id: str     = Form(..., max_length=128),
    language: str    = Form(default="en-US", max_length=10),
    target_language: str = Form(default="en-US", max_length=10),
    msg_router: MessageRouter = Depends(_get_router),
    _claims: dict = Depends(require_auth),
) -> VoiceResponse:
    """
    End-to-end voice pipeline fully server-side:

      1. Receive WebM/Opus blob from the browser (via MediaRecorder).
      2. Base64-encode and pass to the MCP ``speech_to_text_tool`` for
         transcription (Azure Cognitive Services or stub).
      3. Feed the recognised text into the normal voice pipeline
         (RouterAgent → AccessibilityAgent ‖ TranslationAgent → fan-in ACCESSIBLE).
      4. The result is broadcast to all session participants.

    The browser never needs the Azure Speech SDK.
    """
    audio_bytes = await audio.read()
    if not audio_bytes:
        raise HTTPException(status_code=422, detail="Audio file is empty.")
    if len(audio_bytes) > 10 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Audio exceeds 10 MB limit.")

    logger.info(
        "[/speech/recognize] → session=%s user=%s lang=%s target=%s audio_bytes=%d",
        session_id, user_id, language, target_language, len(audio_bytes),
    )

    # Step 1 – transcribe via MCP tool
    audio_b64 = base64.b64encode(audio_bytes).decode()
    try:
        stt_result = await _mcp_client.call_tool(
            "speech_to_text_tool",
            audio_b64=audio_b64,
            session_id=session_id,
            user_id=user_id,
            language=language,
        )
    except Exception as exc:
        logger.exception("MCP speech_to_text_tool failed")
        raise HTTPException(status_code=500, detail=f"Transcription failed: {exc}") from exc

    if not stt_result or not stt_result.success:
        error_msg = stt_result.error if stt_result else "no result from MCP"
        raise HTTPException(status_code=502, detail=error_msg)

    recognised_text: str = (stt_result.data or {}).get("text", "").strip()
    if not recognised_text:
        # Return an empty-audio sentinel so the frontend can skip without
        # creating a message that has a falsy id (which confuses recipient filters).
        import uuid as _uuid  # noqa: PLC0415
        return VoiceResponse(
            message_id=str(_uuid.uuid4()),
            text="",
            source="voice",
            features_applied=[],
        )

    try:
        payload = await msg_router.route_voice(
            recognised_text,
            session_id=session_id,
            user_id=user_id,
            language=language,
            target_language=target_language,
        )
        logger.info(
            "[/speech/recognize] ← id=%s features=%s",
            payload.get('id'), payload.get('features_applied'),
        )
        # Persist to Cosmos (primary) or in-memory store (fallback).
        await _save_message(request, session_id, payload)
        return VoiceResponse(
            message_id=payload.get("id", ""),
            text=payload.get("content", recognised_text),
            source="voice",
            features_applied=payload.get("features_applied", []),
            translated_content=payload.get("translated_content"),
        )
    except Exception as exc:
        logger.exception("Error in voice pipeline after transcription")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get(
    "/token",
    response_model=SpeechTokenResponse,
    summary="Issue Azure Speech auth token for the browser SDK",
)
async def get_speech_token(
    speech_svc=Depends(_get_speech_service),
) -> SpeechTokenResponse:
    try:
        data = await speech_svc.get_speech_token()
        return SpeechTokenResponse(**data)
    except Exception as exc:
        logger.error("Failed to issue speech token: %s", exc)
        raise HTTPException(status_code=502, detail="Could not obtain speech token.") from exc


@router.post(
    "/transcribe",
    response_model=TranscribeResponse,
    summary="Server-side audio transcription",
)
async def transcribe_audio(
    audio: UploadFile = File(..., description="WAV PCM 16 kHz 16-bit mono."),
    language: str = Form(default="en-US"),
    speech_svc=Depends(_get_speech_service),
) -> TranscribeResponse:
    audio_bytes = await audio.read()
    if not audio_bytes:
        raise HTTPException(status_code=422, detail="Audio file is empty.")
    try:
        text, confidence = speech_svc.transcribe_from_bytes(audio_bytes, language=language)
        return TranscribeResponse(text=text, confidence=confidence, language=language)
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
