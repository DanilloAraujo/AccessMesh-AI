"""
backend/adapters
────────────────
Omnichannel adapter layer for AccessMesh-AI.

Each adapter translates channel-specific payloads into the unified
``HubMessageRequest`` format consumed by ``POST /hub/message``.

Plugging a new channel
──────────────────────
1. Create  ``backend/adapters/<channel>_adapter.py``
2. Subclass  ``ChannelAdapter``  and implement  ``adapt(raw_input)``
3. In the channel's webhook/bot handler, call  ``adapter.adapt(payload)``
   and forward the result to the  ``MessageRouter``  (or POST /hub/message).

No changes to the pipeline, agents, or existing routes are required.

Available adapters
──────────────────
- web_adapter.WebAdapter          — browser / PWA (already the default)

Planned (not yet implemented)
────────────────────────────
- TeamsAdapter   — Microsoft Teams via Bot Framework Activity webhook
- MobileAdapter  — React Native / Flutter apps (same REST, thinner wrapper)
- SlackAdapter   — Slack Events API
- ApiAdapter     — Generic REST client / third-party integration
"""

from backend.adapters.base_adapter import ChannelAdapter, ChannelContext
from backend.adapters.web_adapter import WebAdapter

__all__ = ["ChannelAdapter", "ChannelContext", "WebAdapter"]
