"""
backend/app/models/message_model.py
Defines the data models for messages used in the backend of the application. 
These models are based on the shared message schema but may include additional fields or modifications specific to backend processing.

"""

from __future__ import annotations

from shared.message_schema import (  # noqa: F401
    AccessibilityFeature,
    AccessibleMessage,
    AudioChunkMessage,
    AvatarReadyMessage,
    BaseMessage,
    CommunicationMode,
    ErrorMessage,
    GestureMessage,
    Language,
    MeetingSummaryMessage,
    MessageType,
    RoutedMessage,
    SystemMessage,
    TranscriptionMessage,
    TranslatedMessage,
)

from pydantic import Field

# ---------------------------------------------------------------------------
# Backend-only models
# ---------------------------------------------------------------------------


class ChatMessage(BaseMessage):
    """Plain text chat message sent by a participant (backend response model)."""

    message_type: MessageType = MessageType.CHAT
    text: str = Field(..., description="Plain-text message content.")
    language: str = Field(default="en-US", description="BCP-47 language of the text.")
