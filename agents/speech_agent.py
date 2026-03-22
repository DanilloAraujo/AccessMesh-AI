"""
Speech Agent — transcribes audio to text via MCP speech_to_text_tool.

Role (Agent Mesh): speech_agent

Delega a transcrição ao MCP tool `speech_to_text_tool` via MCPClient,
respeitando a fronteira de protocolo do Agent Mesh — agentes nunca
chamam serviços diretamente.

Agent Mesh integration: inherits from BaseAgent and subscribes to
AUDIO_CHUNK events so it can be triggered via the bus (true mesh
participant). The ``process_audio`` method is still available for
direct invocation by HTTP routes for backwards compatibility.

Input : audio bytes | AudioChunkMessage (via bus)
Output: TranscriptionMessage | None
"""

from __future__ import annotations

import base64
import logging
import uuid
from typing import TYPE_CHECKING, ClassVar, List, Optional, cast

from agents.base_agent import BaseAgent
from mcp.mcp_client import MCPClient, mcp_client as _default_mcp_client
from shared.message_schema import AudioChunkMessage, Language, MessageType, TranscriptionMessage

if TYPE_CHECKING:
    from agents.agent_bus import AsyncAgentBus
    from shared.message_schema import BaseMessage

logger = logging.getLogger(__name__)

_LANGUAGE_MAP: dict[str, Language] = {
    "en-US": Language.EN_US,
    "pt-BR": Language.PT_BR,
    "es": Language.ES,
    "fr": Language.FR,
    "de": Language.DE,
}


class SpeechAgent(BaseAgent):
    """
    Converte bytes de áudio em TranscriptionMessage chamando o MCP tool
    `speech_to_text_tool`. Broadcasting é responsabilidade do realtime_dispatcher.

    Agent Mesh role: subscribes to AUDIO_CHUNK events from the bus,
    transcribes the audio, and publishes a TranscriptionMessage for
    downstream agents (RouterAgent, etc.).
    """

    # Agent Mesh: consume AUDIO_CHUNK events from the bus
    subscribes_to: ClassVar[List[MessageType]] = [MessageType.AUDIO_CHUNK]

    def __init__(self, mcp_client: Optional[MCPClient] = None) -> None:
        self._mcp_client = mcp_client or _default_mcp_client

    async def process_audio(
        self,
        audio_bytes: bytes,
        *,
        session_id: str,
        user_id: str,
        language: str = "en-US",
    ) -> Optional[TranscriptionMessage]:
        """Transcrição via MCP. Retorna TranscriptionMessage ou None se silencioso."""
        audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")

        result = await self._mcp_client.call_tool(
            "speech_to_text_tool",
            audio_b64=audio_b64,
            session_id=session_id,
            user_id=user_id,
            language=language,
        )

        if not result.success or not result.data or not result.data.get("text"):
            logger.debug(
                "SpeechAgent.process_audio: no speech detected for user '%s'. error=%s",
                user_id, result.error or "-",
            )
            return None

        return TranscriptionMessage(
            message_id=str(uuid.uuid4()),
            session_id=session_id,
            sender_id=user_id,
            message_type=MessageType.TRANSCRIPTION,
            text=result.data["text"],
            confidence=float(result.data.get("confidence", 1.0)),
            detected_language=_LANGUAGE_MAP.get(language),
        )

    # ── Agent Mesh handler ────────────────────────────────────────────

    async def handle(self, event: "BaseMessage", bus: "AsyncAgentBus") -> None:
        """
        Receive an AudioChunkMessage from the bus, transcribe the audio,
        and publish a TranscriptionMessage for the downstream pipeline.
        """
        try:
            audio_msg = cast(AudioChunkMessage, event)
            audio_bytes = base64.b64decode(audio_msg.audio_data)
            language = audio_msg.language_hint or "en-US"
            if hasattr(language, "value"):
                language = language.value

            transcription = await self.process_audio(
                audio_bytes,
                session_id=audio_msg.session_id,
                user_id=audio_msg.sender_id,
                language=language,
            )
            if transcription:
                transcription.metadata["correlation_id"] = event.metadata.get(
                    "correlation_id", event.message_id
                )
                await bus.publish(transcription)
        except Exception as exc:
            logger.error("SpeechAgent.handle error: %s", exc, exc_info=True)
