"""
mcp/tools/speech_to_text_tool.py

MCP Tool: speech_to_text_tool

Converts raw audio bytes (base64-encoded) into a text transcription by
calling SpeechService directly. Esta é a camada de implementação do MCP —
agentes da mesh devem usar MCPClient.call_tool() e nunca importar
esta ferramenta diretamente.
"""

from __future__ import annotations

import base64
import logging
from typing import Any, Dict

from services.speech_service import SpeechService

logger = logging.getLogger(__name__)


class SpeechToTextTool:
    """MCP tool que delega transcrição de áudio ao SpeechService (Azure Speech SDK)."""

    name: str = "speech_to_text_tool"
    description: str = (
        "Transcribes base64-encoded audio into text. "
        "Accepts WebM/Opus or WAV audio and returns the recognised text "
        "together with a confidence score."
    )
    input_schema: Dict[str, Any] = {
        "type": "object",
        "required": ["audio_b64", "session_id", "user_id"],
        "properties": {
            "audio_b64": {
                "type": "string",
                "description": "Base64-encoded audio bytes (WebM/Opus or WAV).",
            },
            "session_id": {
                "type": "string",
                "description": "Active meeting session ID.",
            },
            "user_id": {
                "type": "string",
                "description": "ID of the participant speaking.",
            },
            "language": {
                "type": "string",
                "default": "en-US",
                "description": "BCP-47 language tag for recognition (e.g. 'pt-BR').",
            },
        },
    }

    def __init__(self) -> None:
        self._svc = SpeechService()  # auto-carrega AZURE_SPEECH_KEY / AZURE_SPEECH_REGION
        if not self._svc.is_enabled:
            logger.warning(
                "SpeechToTextTool: AZURE_SPEECH_KEY / AZURE_SPEECH_REGION não configurados "
                "— transcrição indisponível (stub mode)."
            )

    def execute(
        self,
        audio_b64: str,
        session_id: str,
        user_id: str,
        language: str = "en-US",
    ) -> Dict[str, Any]:
        """Executa a ferramenta e retorna dict compatível com o protocolo MCP."""
        if not self._svc.is_enabled:
            return {
                "error": "Speech service not configured. Set AZURE_SPEECH_KEY and AZURE_SPEECH_REGION.",
                "text": "",
                "confidence": 0.0,
                "session_id": session_id,
                "user_id": user_id,
            }

        try:
            audio_bytes = base64.b64decode(audio_b64)
        except Exception as exc:
            logger.error("speech_to_text_tool: base64 inválido — %s", exc)
            return {"error": f"Invalid audio encoding: {exc}", "text": "", "confidence": 0.0,
                    "session_id": session_id, "user_id": user_id}

        text, confidence = self._svc.transcribe_from_bytes(audio_bytes, language=language)

        if not text:
            logger.debug("speech_to_text_tool: nenhum speech detectado para user='%s'", user_id)
            return {"text": "", "confidence": 0.0, "session_id": session_id, "user_id": user_id}

        return {
            "text": text,
            "confidence": confidence,
            "session_id": session_id,
            "user_id": user_id,
        }
