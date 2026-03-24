"""
backend/app/models/user_model.py

Pydantic models representing a system user and their accessibility preferences.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field

from shared.message_schema import CommunicationMode


class UserRole(str, Enum):
    """Role of a user in the system."""
    PARTICIPANT  = "participant"
    MODERATOR    = "moderator"
    INTERPRETER  = "interpreter"
    OBSERVER     = "observer"


class AccessibilityPreferences(BaseModel):
    """Accessibility features selected by the user."""

    sign_language: bool = Field(
        default=False,
        description="Enable real-time sign-language.",
    )
    subtitles: bool = Field(
        default=True,
        description="Show live caption / subtitle overlay.",
    )
    audio_description: bool = Field(
        default=False,
        description="Generate audio description for visual content.",
    )
    high_contrast: bool = Field(
        default=False,
        description="Apply high-contrast UI theme.",
    )
    large_text: bool = Field(
        default=False,
        description="Increase base font size.",
    )
    preferred_language: str = Field(
        default="en-US",
        description="BCP-47 tag for the user's preferred spoken language.",
    )
    translation_enabled: bool = Field(
        default=False,
        description="Automatically translate incoming messages.",
    )
    target_language: Optional[str] = Field(
        default=None,
        description="Target language for translation (BCP-47).",
    )
    communication_mode: CommunicationMode = Field(
        default=CommunicationMode.TEXT,
        description="Preferred input/output modality chosen by the user.",
    )


class User(BaseModel):
    """Application user profile."""

    user_id: str = Field(
        default_factory=lambda: str(uuid4()),
        description="Unique identifier (UUID v4).",
    )
    display_name: str = Field(..., description="Name shown to other participants.")
    email: Optional[str] = Field(
        default=None,
        description="User email — used as login identifier.",
    )
    hashed_password: str = Field(
        default="",
        description="bcrypt-hashed password. Empty for guest/dev accounts.",
    )
    role: UserRole = Field(default=UserRole.PARTICIPANT)
    accessibility: AccessibilityPreferences = Field(
        default_factory=AccessibilityPreferences,
        description="Accessibility feature configuration.",
    )
    active_sessions: List[str] = Field(
        default_factory=list,
        description="Session IDs the user is currently joined to.",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Account creation timestamp (UTC).",
    )
    last_seen: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Last activity timestamp (UTC).",
    )

    @property
    def enabled_features(self) -> List[str]:
        """Return a list of enabled accessibility feature names."""
        prefs = self.accessibility
        features: List[str] = []
        if prefs.sign_language:
            features.append("sign_language")
        if prefs.subtitles:
            features.append("subtitles")
        if prefs.audio_description:
            features.append("audio_description")
        if prefs.high_contrast:
            features.append("high_contrast")
        if prefs.large_text:
            features.append("large_text")
        if prefs.translation_enabled:
            features.append("translation")
        return features
