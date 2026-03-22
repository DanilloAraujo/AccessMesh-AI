"""
backend/app/models
──────────────────
Pydantic models for AccessMesh-AI.
"""

from .message_model import (
    AccessibilityFeature,
    AccessibleMessage,
    AudioChunkMessage,
    BaseMessage,
    GestureMessage,
    Language,
    MessageType,
    TranscriptionMessage,
)
from .meeting_model import Meeting, MeetingStatus, Participant
from .user_model import AccessibilityPreferences, User, UserRole

__all__ = [
    # message
    "MessageType",
    "AccessibilityFeature",
    "Language",
    "BaseMessage",
    "AudioChunkMessage",
    "TranscriptionMessage",
    "GestureMessage",
    "AccessibleMessage",
    # meeting
    "Meeting",
    "MeetingStatus",
    "Participant",
    # user
    "User",
    "UserRole",
    "AccessibilityPreferences",
]
