"""Pydantic schemas shared across all AccessMesh-AI services."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field



class MessageType(str, Enum):
    """Type of message traversing the hub."""
    AUDIO_CHUNK       = "audio_chunk"
    TRANSCRIPTION     = "transcription"
    GESTURE           = "gesture"
    ROUTED            = "routed"
    ACCESSIBLE        = "accessible"
    TRANSLATED        = "translated"
    AVATAR_READY      = "avatar_ready"
    SUMMARY           = "summary"
    CHAT              = "chat"
    SYSTEM            = "system"
    ERROR             = "error"


class AccessibilityFeature(str, Enum):
    """Accessibility features that can be enabled by participant."""
    SIGN_LANGUAGE     = "sign_language"
    AUDIO_DESCRIPTION = "audio_description"
    HIGH_CONTRAST     = "high_contrast"
    LARGE_TEXT        = "large_text"
    SUBTITLES         = "subtitles"


class Language(str, Enum):
    """Supported languages by the translation_agent."""
    PT_BR = "pt-BR"
    EN_US = "en-US"
    ES    = "es"
    FR    = "fr"
    DE    = "de"


class CommunicationMode(str, Enum):
    """Preferred communication mode chosen by a participant."""
    TEXT          = "text"
    SIGN_LANGUAGE = "sign_language"
    VOICE         = "voice"



class BaseMessage(BaseModel):
    """Base envelope for all system messages."""

    message_id: str = Field(
        default_factory=lambda: str(uuid4()),
        description="Unique identifier for the message (UUID v4).",
    )
    session_id: str = Field(
        ...,
        description="Identifier for the meeting session/room.",
    )
    sender_id: str = Field(
        ...,
        description="ID of the participant or agent that originated the message.",
    )
    message_type: MessageType = Field(
        ...,
        description="Type indicating which pipeline stage the message is in.",
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Moment of message creation (UTC).",
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata for free use by agents.",
    )

    model_config = {"use_enum_values": True}



class AudioChunkMessage(BaseMessage):
    """Audio fragment captured by the frontend."""

    message_type: MessageType = MessageType.AUDIO_CHUNK
    audio_data: str = Field(
        ...,
        description="Base64 encoded audio (WebM/Opus recommended).",
    )
    sample_rate: int = Field(
        default=16000,
        description="Sample rate in Hz.",
    )
    language_hint: Optional[Language] = Field(
        default=None,
        description="Language hint for the speech_agent.",
    )


class TranscriptionMessage(BaseMessage):
    """Text produced by the speech_agent from audio."""

    message_type: MessageType = MessageType.TRANSCRIPTION
    text: str = Field(..., description="Generated transcription.")
    confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Speech model confidence (0–1).",
    )
    detected_language: Optional[Language] = Field(
        default=None,
        description="Automatically detected language.",
    )


class RoutedMessage(BaseMessage):
    """Text after router_agent defines which agents to process."""

    message_type: MessageType = MessageType.ROUTED
    text: str = Field(..., description="Text to process.")
    target_agents: List[str] = Field(
        default_factory=list,
        description="List of target agents (e.g., ['accessibility_agent', 'translation_agent']).",
    )


class AccessibleMessage(BaseMessage):
    """Text enriched by the accessibility_agent."""

    message_type: MessageType = MessageType.ACCESSIBLE
    text: str = Field(..., description="Text with accessibility annotations.")
    original_text: str = Field(default="", description="Source text before any transformation.")
    features_applied: List[AccessibilityFeature] = Field(
        default_factory=list,
        description="Applied accessibility features.",
    )
    aria_labels: Dict[str, str] = Field(
        default_factory=dict,
        description="ARIA labels for frontend use.",
    )
    sign_gloss: Optional[str] = Field(
        default=None,
        description="LIBRAS / ASL gloss token string for sign-language rendering.",
    )
    audio_b64: Optional[str] = Field(
        default=None,
        description="Base64-encoded MP3 from Azure Neural TTS for voice-mode playback.",
    )


class TranslatedMessage(BaseMessage):
    """Text translated by the translation_agent."""

    message_type: MessageType = MessageType.TRANSLATED
    original_text: str = Field(..., description="Original text before translation.")
    translated_text: str = Field(..., description="Translated text.")
    source_language: Language = Field(..., description="Source language.")
    target_language: Language = Field(..., description="Target language.")


class AvatarReadyMessage(BaseMessage):
    """Signal that the avatar_agent has completed processing."""

    message_type: MessageType = MessageType.AVATAR_READY
    avatar_url: Optional[str] = Field(
        default=None,
        description="Temporary URL for the generated avatar video/image.",
    )
    animation_data: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Animation data for client-side rendering.",
    )
    confidence: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Speech-to-text transcription confidence (0–1) propagated from TranscriptionMessage.",
    )
    viseme_events: Optional[List[Dict[str, Any]]] = Field(
        default=None,
        description="Azure Neural TTS viseme timing events [{offset_ms, viseme_id}] for avatar lip-sync.",
    )


class SystemMessage(BaseMessage):
    """System control message (joins, leaves, heartbeats)."""

    message_type: MessageType = MessageType.SYSTEM
    event: str = Field(
        ...,
        description="System event (e.g., 'user_joined', 'user_left', 'heartbeat').",
    )
    payload: Dict[str, Any] = Field(default_factory=dict)


class ErrorMessage(BaseMessage):
    """Error message propagated through the pipeline."""

    message_type: MessageType = MessageType.ERROR
    error_code: str = Field(..., description="Error code.")
    error_message: str = Field(..., description="Human-readable error description.")
    origin_agent: Optional[str] = Field(
        default=None,
        description="Agent where the error was generated.",
    )
    recoverable: bool = Field(
        default=True,
        description="Indicates if the error is recoverable and the pipeline can continue.",
    )


class GestureMessage(BaseMessage):
    """Text produced by the gesture_agent from a sign-language signal."""

    message_type: MessageType = MessageType.GESTURE
    text: str = Field(..., description="Recognized gesture as natural text.")
    gesture_label: Optional[str] = Field(
        default=None,
        description="Raw gesture/sign label detected by the model.",
    )
    confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Gesture model confidence (0–1).",
    )


class MeetingSummaryMessage(BaseMessage):
    """Summary produced by the summary_agent at the end of a meeting."""

    message_type: MessageType = MessageType.SUMMARY
    summary_text: str = Field(..., description="Concise meeting summary.")
    key_points: List[str] = Field(
        default_factory=list,
        description="Bullet-point key takeaways extracted from the transcript.",
    )
    participant_ids: List[str] = Field(
        default_factory=list,
        description="List of participant IDs present in the session.",
    )
    total_messages: int = Field(
        default=0,
        description="Total number of messages processed during the session.",
    )



AnyMessage = (
    AudioChunkMessage
    | TranscriptionMessage
    | GestureMessage
    | RoutedMessage
    | AccessibleMessage
    | TranslatedMessage
    | AvatarReadyMessage
    | MeetingSummaryMessage
    | SystemMessage
    | ErrorMessage
)

_MESSAGE_CLASS_MAP: Dict[str, type] = {
    MessageType.AUDIO_CHUNK:  AudioChunkMessage,
    MessageType.TRANSCRIPTION: TranscriptionMessage,
    MessageType.GESTURE:      GestureMessage,
    MessageType.ROUTED:       RoutedMessage,
    MessageType.ACCESSIBLE:   AccessibleMessage,
    MessageType.TRANSLATED:   TranslatedMessage,
    MessageType.AVATAR_READY: AvatarReadyMessage,
    MessageType.SUMMARY:      MeetingSummaryMessage,
    MessageType.SYSTEM:       SystemMessage,
    MessageType.ERROR:        ErrorMessage,
}


def message_from_dict(data: Dict[str, Any]) -> BaseMessage:
    """Deserialize a plain dict to the correct BaseMessage subclass.

    Falls back to BaseMessage for unknown / missing message_type values.
    """
    try:
        msg_type = MessageType(data.get("message_type", ""))
        cls = _MESSAGE_CLASS_MAP.get(msg_type, BaseMessage)
    except ValueError:
        cls = BaseMessage
    return cls.model_validate(data)
