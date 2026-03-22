"""
backend/app/models/meeting_model.py

Pydantic models representing a meeting session and its participants.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class MeetingStatus(str, Enum):
    """Lifecycle state of a meeting."""
    SCHEDULED = "scheduled"
    ACTIVE    = "active"
    PAUSED    = "paused"
    ENDED     = "ended"


class Participant(BaseModel):
    """A single participant inside a meeting session."""

    user_id: str = Field(..., description="Unique user identifier.")
    display_name: str = Field(default="", description="Human-readable name.")
    joined_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    is_active: bool = Field(default=True)
    accessibility_features: List[str] = Field(
        default_factory=list,
        description="Accessibility features requested by this participant.",
    )


class Meeting(BaseModel):
    """Represents a meeting session managed by the hub."""

    session_id: str = Field(
        default_factory=lambda: str(uuid4()),
        description="Unique session / room identifier.",
    )
    title: str = Field(default="AccessMesh Meeting")
    status: MeetingStatus = Field(default=MeetingStatus.ACTIVE)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    ended_at: Optional[datetime] = Field(default=None)
    participants: Dict[str, Participant] = Field(
        default_factory=dict,
        description="Map of user_id → Participant.",
    )
    language: str = Field(
        default="en-US",
        description="Primary language for this session.",
    )
    metadata: Dict[str, str] = Field(default_factory=dict)

    def add_participant(self, participant: Participant) -> None:
        self.participants[participant.user_id] = participant

    def remove_participant(self, user_id: str) -> None:
        if user_id in self.participants:
            self.participants[user_id].is_active = False

    @property
    def active_participant_count(self) -> int:
        return sum(1 for p in self.participants.values() if p.is_active)
