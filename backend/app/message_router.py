"""Routes incoming multimodal inputs to agent pipelines."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict

from backend.app.core.realtime_dispatcher import RealtimeDispatcher
from backend.app.models.message_model import MessageType
from mcp.mcp_client import mcp_client as _mcp_client

logger = logging.getLogger(__name__)


class MessageRouter:
    """Determines processing pipeline and dispatches results to sessions."""

    def __init__(
        self,
        pipeline: Any,                     # agents.pipeline.AgentMeshPipeline
        gesture_svc: Any,                  # kept for backwards-compat
        dispatcher: RealtimeDispatcher,
        content_safety: Any = None,        # services.content_safety_service.ContentSafetyService
    ) -> None:
        self._pipeline       = pipeline
        self._gesture        = gesture_svc
        self._dispatcher     = dispatcher
        self._content_safety = content_safety

    async def _screen(self, text: str) -> None:
        """Raise ValueError if content safety blocks the text."""
        if self._content_safety is None:
            logger.debug("[ContentSafety] Service not configured — screening skipped.")
            return
        if not getattr(self._content_safety, "is_enabled", False):
            logger.warning(
                "[ContentSafety] Service is disabled (missing credentials) — "
                "messages are NOT being screened. Set CONTENT_SAFETY_ENDPOINT "
                "and CONTENT_SAFETY_KEY in production."
            )
            return
        try:
            result = await asyncio.to_thread(self._content_safety.analyze_text, text)
            if not result.safe:
                logger.warning(
                    "[ContentSafety] BLOCKED category=%s score=%s text=%r",
                    result.category, result.score, text[:80],
                )
                raise ValueError(
                    f"Content blocked by safety screening: {result.reason or result.category}"
                )
        except ValueError:
            raise
        except Exception as exc:
            logger.warning("[ContentSafety] Screening error (pass-through): %s", exc)


    async def route_voice(
        self,
        text: str,
        session_id: str,
        user_id: str,
        language: str = "en-US",
        display_name: str = "",
    ) -> Dict[str, Any]:
        """
        Run transcribed voice text through the AgentMeshPipeline and broadcast.

        Returns the enriched payload dict.
        """
        logger.info(
            "MessageRouter.route_voice — session=%s user=%s lang=%s text=%s",
            session_id, user_id, language, text[:80],
        )
        await self._screen(text)
        accessible = await self._pipeline.run(
            text,
            session_id=session_id,
            user_id=user_id,
            language=language,
        )
        payload = self._build_payload(accessible, source="voice")
        if display_name:
            payload["from"] = display_name
        logger.info(
            "MessageRouter.route_voice done — id=%s features=%s",
            payload.get('id'), payload.get('features_applied'),
        )
        # Fire-and-forget: broadcast to other participants without blocking the HTTP response.
        # The sender already receives the enriched payload via the return value.
        asyncio.create_task(
            asyncio.to_thread(self._dispatcher.dispatch, session_id, payload, exclude_sender=user_id),
            name=f"dispatch:voice:{session_id}",
        )
        return payload

    async def route_gesture(
        self,
        gesture_label: str,
        session_id: str,
        user_id: str,
        language: str = "en-US",
        display_name: str = "",
    ) -> Dict[str, Any]:
        """
        Translate a gesture label to text via MCP gesture_recognition_tool
        (RB02: sinais → texto), then run through AgentMeshPipeline and broadcast.
        """

        mcp_result = await _mcp_client.call_tool(
            "gesture_recognition_tool",
            gesture_label=gesture_label,
            session_id=session_id,
            user_id=user_id,
        )
        if mcp_result and mcp_result.success and mcp_result.data:
            text = mcp_result.data.get("text") or gesture_label.replace("_", " ").capitalize()
        else:
            logger.warning(
                "gesture_recognition_tool failed (%s) — using raw label.",
                mcp_result.error if mcp_result else "no result",
            )
            text = gesture_label.replace("_", " ").capitalize()

        await self._screen(text)
        accessible = await self._pipeline.run(
            text,
            session_id=session_id,
            user_id=user_id,
            language=language,
        )
        payload = self._build_payload(accessible, source="gesture")
        if display_name:
            payload["from"] = display_name
        asyncio.create_task(
            asyncio.to_thread(self._dispatcher.dispatch, session_id, payload, exclude_sender=user_id),
            name=f"dispatch:gesture:{session_id}",
        )
        return payload

    async def route_chat(
        self,
        text: str,
        session_id: str,
        user_id: str,
        display_name: str = "",
        language: str = "en-US",
    ) -> Dict[str, Any]:
        """
        Route a chat message through the AgentMeshPipeline for full accessibility enrichment.
        OMNICHANNEL: voice, gesture, and text all receive subtitles + sign-language output.
        """
        await self._screen(text)
        accessible = await self._pipeline.run(
            text,
            session_id=session_id,
            user_id=user_id,
            language=language,
        )
        payload = self._build_payload(accessible, source="text")
        if display_name:
            payload["from"] = display_name
        asyncio.create_task(
            asyncio.to_thread(self._dispatcher.dispatch, session_id, payload, exclude_sender=user_id),
            name=f"dispatch:chat:{session_id}",
        )
        return payload


    @staticmethod
    def _build_payload(accessible: Any, source: str) -> Dict[str, Any]:
        """Convert an AccessibleMessage (agent output) to a broadcast dict."""
        metadata: Dict[str, Any] = getattr(accessible, "metadata", None) or {}
        return {
            "id":                 accessible.message_id,
            "type":               "message",
            "source":             source,
            "from":               accessible.sender_id,
            "content":            accessible.text,
            "features_applied":   [
                f.value if hasattr(f, "value") else str(f)
                for f in (getattr(accessible, "features_applied", None) or [])
            ],
            "timestamp":          accessible.timestamp.isoformat(),
        }
