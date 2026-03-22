"""
backend/adapters/web_adapter.py
────────────────────────────────
ChannelAdapter implementation for the AccessMesh-AI web / PWA frontend.

The web frontend already calls  ``POST /hub/message``  directly with a
fully-formed payload, so this adapter is a thin identity wrapper.  Its
value is to make the omnichannel contract explicit and to serve as a
reference implementation when building other adapters.

Usage (from a route or service)
────────────────────────────────
    from backend.adapters.web_adapter import WebAdapter
    from backend.adapters.base_adapter import ChannelContext

    adapter = WebAdapter()
    hub_request = adapter.adapt(
        raw_input={
            "input_type": "text",
            "content": "Hello!",
        },
        context=ChannelContext(
            session_id="abc",
            user_id="user-1",
            language="pt-BR",
            target_language="en-US",
            display_name="Maria",
            communication_mode="text",
        ),
    )
    # hub_request can now be passed to MessageRouter.route_*()
"""

from __future__ import annotations

from typing import Any, Dict

from backend.adapters.base_adapter import ChannelAdapter, ChannelContext
from backend.app.routes.hub_routes import HubMessageRequest


class WebAdapter(ChannelAdapter):
    """
    Adapter for the AccessMesh-AI web / PWA channel.

    Accepts either:
    - A dict already shaped like ``HubMessageRequest`` (pass-through), or
    - A minimal dict with at least ``input_type`` and ``content``.
    """

    channel_id = "web"

    def adapt(self, raw_input: Any, context: ChannelContext) -> HubMessageRequest:
        """
        Build a ``HubMessageRequest`` from a web payload dict and context.

        ``raw_input`` is expected to be a dict with at minimum:
          - ``input_type``: "speech" | "gesture" | "text"
          - ``content``:    message text or gesture label

        All other fields are populated from *context*.
        """
        if isinstance(raw_input, HubMessageRequest):
            return raw_input

        payload: Dict[str, Any] = raw_input if isinstance(raw_input, dict) else {}

        return HubMessageRequest(
            channel=self.channel_id,
            input_type=payload.get("input_type", "text"),
            content=payload.get("content", ""),
            session_id=context.session_id,
            user_id=context.user_id,
            language=payload.get("language", context.language),
            target_language=payload.get("target_language", context.target_language),
            display_name=payload.get("display_name", context.display_name),
        )
