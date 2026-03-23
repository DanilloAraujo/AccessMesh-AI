"""Gesture / sign-language input endpoints exposed at /gesture/*."""

from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, List, Optional, cast

from fastapi import APIRouter, HTTPException, Request, status, Depends
from pydantic import BaseModel, Field

from backend.app.auth import require_auth
from backend.app.limiter import limiter
from agents import agent_bus
from backend.app.session_store import append_message
from fastapi import Request as _Request
from shared.message_schema import (
    AccessibleMessage,
    GestureMessage,
    MessageType,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/gesture", tags=["Gesture"])


def _get_cosmos(request: _Request):
    """Return CosmosService if enabled, else None."""
    cosmos = getattr(request.app.state, "cosmos", None)
    if cosmos and getattr(cosmos, "is_enabled", False):
        return cosmos
    return None


async def _save_message(request: _Request, session_id: str, payload: Dict[str, Any]) -> None:
    """Persist to Cosmos if available, fall back to in-memory session_store."""
    cosmos = _get_cosmos(request)
    if cosmos:
        try:
            await cosmos.append_message(session_id, payload)
            return
        except Exception as _ce:
            logger.warning("[gesture_routes] Cosmos save failed (fallback to memory): %s", _ce)
    await append_message(session_id, payload)


async def _dispatch_gesture(
    gesture_label: str,
    text: str,
    confidence: float,
    session_id: str,
    user_id: str,
    language: str,
    landmarks: Optional[List[Dict[str, float]]] = None,
) -> Optional[AccessibleMessage]:
    """
    Publish a GestureMessage onto the Agent Mesh bus and collect the resulting
    AccessibleMessage.  Returns None on timeout.
    """
    meta: Dict[str, Any] = {"language": language, "target_language": language}
    if landmarks:
        meta["landmarks"] = landmarks

    gesture_msg = GestureMessage(
        session_id=session_id,
        sender_id=user_id,
        message_type=MessageType.GESTURE,
        text=text,
        gesture_label=gesture_label,
        confidence=confidence,
        metadata=meta,
    )
    result = await agent_bus.publish_and_collect(
        gesture_msg,
        collect_type=MessageType.ACCESSIBLE,
        timeout=30.0,
    )
    return cast(Optional[AccessibleMessage], result)


# ── Pydantic models ───────────────────────────────────────────────────────────

class GestureProcessRequest(BaseModel):
    gesture_label: str = Field(
        ...,
        max_length=200,
        description="Pre-classified gesture / sign label from the frontend.",
    )
    session_id: str = Field(..., max_length=128, description="Session / room identifier.")
    user_id: str    = Field(..., max_length=128, description="Participant user_id.")
    language: str   = Field(default="en-US", max_length=10, description="BCP-47 language tag.")


class GestureProcessResponse(BaseModel):
    message_id: str
    text: str
    source: str
    features_applied: List[str]
    translated_content: Optional[str] = None


class LandmarksRequest(BaseModel):
    landmarks: List[Dict[str, float]] = Field(
        ...,
        description="List of (x, y, z) landmark coordinates from MediaPipe.",
    )
    session_id: str = Field(..., max_length=128)
    user_id: str    = Field(..., max_length=128)
    language: str   = Field(default="en-US", max_length=10)


class GestureFrameRequest(BaseModel):
    frame_b64: str  = Field(..., description="Base64-encoded JPEG frame from the camera.")
    session_id: str = Field(..., max_length=128, description="Session / room identifier.")
    user_id: str    = Field(..., max_length=128, description="Participant user_id.")
    language: str   = Field(default="en-US", max_length=10, description="BCP-47 language tag.")


class GestureFrameResponse(BaseModel):
    message_id: str
    text: str
    gesture_label: str
    confidence: float
    source: str
    features_applied: List[str]
    translated_content: Optional[str] = None


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post(
    "/process",
    response_model=GestureProcessResponse,
    summary="Process a pre-classified gesture through the Agent Mesh",
)
@limiter.limit("30/minute")
async def process_gesture(
    request: Request,
    body: GestureProcessRequest,
    _claims: dict = Depends(require_auth),
) -> GestureProcessResponse:
    """
    Publishes a GestureMessage onto the Agent Mesh bus.  The GestureAgent
    recognises the label to text, re-publishes as a TranscriptionMessage that
    flows through the full pipeline (Router -> Accessibility || Translation ->
    fan-in ACCESSIBLE).
    """
    if not body.gesture_label.strip():
        raise HTTPException(status_code=422, detail="gesture_label cannot be empty.")

    try:
        terminal = await _dispatch_gesture(
            gesture_label=body.gesture_label,
            text=body.gesture_label,
            confidence=1.0,
            session_id=body.session_id,
            user_id=body.user_id,
            language=body.language,
        )
        if terminal is None:
            return GestureProcessResponse(
                message_id=str(uuid.uuid4()),
                text=body.gesture_label,
                source="gesture",
                features_applied=[],
            )
        content = terminal.text or body.gesture_label
        translated = terminal.metadata.get("translated_text") if terminal.metadata else None
        await _save_message(request, body.session_id, {
            "id": terminal.message_id,
            "content": content,
            "source": "gesture",
            "from": body.user_id,
        })
        return GestureProcessResponse(
            message_id=terminal.message_id,
            text=content,
            source="gesture",
            features_applied=[
                f.value if hasattr(f, "value") else f
                for f in terminal.features_applied
            ],
            translated_content=translated,
        )
    except Exception as exc:
        logger.exception("Error processing gesture input")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post(
    "/landmarks",
    response_model=GestureProcessResponse,
    summary="Accept raw MediaPipe hand landmark arrays for server-side classification",
)
@limiter.limit("30/minute")
async def process_landmarks(
    body: LandmarksRequest,
    request: Request,
    _claims: dict = Depends(require_auth),
) -> GestureProcessResponse:
    """
    Receives MediaPipe hand landmark arrays from the frontend GestureCamera,
    runs the rule-based gesture classifier, and publishes onto the Agent Mesh
    bus if confidence is sufficient.
    """
    gesture_svc = getattr(request.app.state, "gesture", None)
    if gesture_svc is None:
        raise HTTPException(status_code=503, detail="GestureService not initialised.")

    try:
        recognition = gesture_svc.recognise_from_landmarks(
            [dict(lm) for lm in body.landmarks]
        )
    except Exception as exc:
        logger.warning("[gesture/landmarks] Classification error: %s", exc)
        recognition = {"text": "", "gesture_label": "unknown", "confidence": 0.0}

    label      = recognition.get("gesture_label", "unknown")
    confidence = float(recognition.get("confidence", 0.0))
    text       = recognition.get("text", "")

    if not text or label == "unknown" or confidence < 0.5:
        return GestureProcessResponse(
            message_id="",
            text=text or "",
            source="gesture",
            features_applied=[],
        )

    try:
        terminal = await _dispatch_gesture(
            gesture_label=label,
            text=text,
            confidence=confidence,
            session_id=body.session_id,
            user_id=body.user_id,
            language=body.language,
            landmarks=[dict(lm) for lm in body.landmarks],
        )
    except Exception as exc:
        logger.exception("[gesture/landmarks] Pipeline error")
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    if terminal is None:
        return GestureProcessResponse(
            message_id=str(uuid.uuid4()),
            text=text,
            source="gesture",
            features_applied=[],
        )
    recognized_text = terminal.text or text
    translated = terminal.metadata.get("translated_text") if terminal.metadata else None
    await _save_message(request, body.session_id, {
        "id": terminal.message_id,
        "content": recognized_text,
        "source": "gesture",
        "from": body.user_id,
    })
    return GestureProcessResponse(
        message_id=terminal.message_id,
        text=recognized_text,
        source="gesture",
        features_applied=[
            f.value if hasattr(f, "value") else f
            for f in terminal.features_applied
        ],
        translated_content=translated,
    )


@router.post(
    "/frame",
    response_model=GestureFrameResponse,
    summary="Recognise a sign from a camera frame via Azure OpenAI Vision",
)
@limiter.limit("30/minute")
async def process_frame(
    request: Request,
    body: GestureFrameRequest,
    _claims: dict = Depends(require_auth),
) -> GestureFrameResponse:
    """
    Accepts a raw base64 JPEG frame, calls GestureService.recognise_from_frame_b64()
    (which internally queries Azure OpenAI GPT-4o Vision), then publishes the result
    onto the Agent Mesh bus and broadcasts to all session participants.
    """
    gesture_svc = getattr(request.app.state, "gesture", None)
    if gesture_svc is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="GestureService not initialised.")

    try:
        recognition = await gesture_svc.recognise_from_frame_b64(body.frame_b64)
    except Exception as exc:
        logger.warning("[gesture/frame] Recognition failed: %s", exc)
        recognition = {"text": "", "gesture_label": "unknown", "confidence": 0.0}

    label      = recognition.get("gesture_label", "unknown")
    confidence = float(recognition.get("confidence", 0.0))
    text       = recognition.get("text", "")

    if not text or label == "unknown" or confidence < 0.4:
        return GestureFrameResponse(
            message_id="",
            text=text or "",
            gesture_label=label,
            confidence=confidence,
            source="gesture",
            features_applied=[],
        )

    try:
        terminal = await _dispatch_gesture(
            gesture_label=label,
            text=text,
            confidence=confidence,
            session_id=body.session_id,
            user_id=body.user_id,
            language=body.language,
        )
    except Exception as exc:
        logger.exception("[gesture/frame] Pipeline error")
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    if terminal is None:
        return GestureFrameResponse(
            message_id=str(uuid.uuid4()),
            text=text,
            gesture_label=label,
            confidence=confidence,
            source="gesture",
            features_applied=[],
        )
    recognized_text = terminal.text or text
    translated = terminal.metadata.get("translated_text") if terminal.metadata else None
    await _save_message(request, body.session_id, {
        "id": terminal.message_id,
        "content": recognized_text,
        "source": "gesture",
        "from": body.user_id,
    })
    return GestureFrameResponse(
        message_id=terminal.message_id,
        text=recognized_text,
        gesture_label=label,
        confidence=confidence,
        source="gesture",
        features_applied=[
            f.value if hasattr(f, "value") else f
            for f in terminal.features_applied
        ],
        translated_content=translated,
    )
