"""Abstract base class for omnichannel adapters."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ChannelContext:
    """
    Immutable context passed to every adapter call.

    Contains runtime values that are not present in the raw payload but are
    needed to build a valid  ``HubMessageRequest``.
    """

    session_id: str
    user_id: str
    language: str = "en-US"
    target_language: str = "en-US"
    display_name: str = ""
    communication_mode: str = "text"   # one of: text | sign_language | voice
    extra: dict = field(default_factory=dict)


class ChannelAdapter(ABC):
    """
    Abstract omnichannel adapter.

    Subclass this to integrate a new communication channel.
    ``channel_id`` must uniquely identify the channel (e.g. "teams", "slack").
    ``adapt()`` must be pure (no side effects) and return a ``HubMessageRequest``.
    """

    #: Short identifier for the channel — used in telemetry and routing logs.
    channel_id: str = "unknown"

    @abstractmethod
    def adapt(self, raw_input: Any, context: ChannelContext):  # -> HubMessageRequest
        """
        Translate *raw_input* (channel-specific payload) into a
        ``HubMessageRequest`` suitable for ``MessageRouter``.

        Args:
            raw_input:  Channel-specific payload object.
            context:    Runtime context (session, user, language preferences).

        Returns:
            ``HubMessageRequest`` populated from the translated payload.
        """
        raise NotImplementedError
