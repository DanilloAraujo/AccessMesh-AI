"""Azure Web PubSub service wrapper."""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

from azure.core.exceptions import AzureError
from azure.messaging.webpubsubservice import WebPubSubServiceClient
from pydantic import BaseModel

logger = logging.getLogger(__name__)



class WebPubSubConfig(BaseModel):
    """Web PubSub service configuration (read from environment variables)."""

    connection_string: str
    hub_name: str = "accessmesh"



class WebPubSubService:
    """Wrapper around Azure's WebPubSubServiceClient."""

    def __init__(self, config: Optional[WebPubSubConfig] = None) -> None:
        if config is None:
            from shared.config import settings  # noqa: PLC0415
            config = WebPubSubConfig(
                connection_string=settings.webpubsub_connection_string or "",
                hub_name=settings.webpubsub_hub_name,
            )
        self._hub_name = config.hub_name
        self._client = None
        if config.connection_string:
            try:
                self._client = WebPubSubServiceClient.from_connection_string(
                    connection_string=config.connection_string,
                    hub=config.hub_name,
                )
                logger.info(
                    "WebPubSubService started — hub: %s", config.hub_name
                )
            except Exception as exc:
                logger.warning("Failed to create WebPubSubServiceClient: %s", exc)
        else:
            logger.warning(
                "WebPubSubService: no connection string — running in stub mode. "
                "Set WEBPUBSUB_CONNECTION_STRING to enable."
            )

    @property
    def is_enabled(self) -> bool:
        return self._client is not None


    def get_client_access_token(
        self,
        user_id: str,
        groups: Optional[list[str]] = None,
        roles: Optional[list[str]] = None,
        minutes_to_expire: int = 60,
    ) -> Dict[str, Any]:
        """Generate a short-lived access token for a participant to connect to Web PubSub."""
        if self._client is None:
            raise RuntimeError("WebPubSubService is not configured — set WEBPUBSUB_CONNECTION_STRING.")
        try:
            token_response = self._client.get_client_access_token(
                user_id=user_id,
                groups=groups or [],
                roles=roles or ["webpubsub.joinLeaveGroup", "webpubsub.sendToGroup"],
                minutes_to_expire=minutes_to_expire,
            )
            logger.debug("Token generated for user_id=%s", user_id)
            return {
                "token": token_response["token"],
                "url": token_response["url"],
                "user_id": user_id,
                "hub": self._hub_name,
            }
        except AzureError as exc:
            logger.error("Error generating WebPubSub token: %s", exc)
            raise


    def send_to_all(self, message: Dict[str, Any]) -> None:
        """Send a message to all clients connected to the hub."""
        if self._client is None:
            raise RuntimeError(
                "WebPubSubService is not configured — set WEBPUBSUB_CONNECTION_STRING."
            )
        try:
            self._client.send_to_all(
                message=json.dumps(message, default=str),
                content_type="application/json",
            )
            logger.debug("Message sent to all: type=%s", message.get("message_type"))
        except AzureError as exc:
            logger.error("Failed to send to all: %s", exc)
            raise

    def send_to_group(self, group: str, message: Dict[str, Any]) -> None:
        """Send a message to a specific group (session/room)."""
        if self._client is None:
            raise RuntimeError(
                "WebPubSubService is not configured — set WEBPUBSUB_CONNECTION_STRING."
            )
        try:
            self._client.send_to_group(
                group=group,
                message=json.dumps(message, default=str),
                content_type="application/json",
            )
            logger.debug(
                "Message sent to group '%s': type=%s",
                group,
                message.get("message_type"),
            )
        except AzureError as exc:
            logger.error("Failed to send to group '%s': %s", group, exc)
            raise

    def send_to_user(self, user_id: str, message: Dict[str, Any]) -> None:
        """Send a message to a specific user."""
        if self._client is None:
            raise RuntimeError(
                "WebPubSubService is not configured — set WEBPUBSUB_CONNECTION_STRING."
            )
        try:
            self._client.send_to_user(
                user_id=user_id,
                message=json.dumps(message, default=str),
                content_type="application/json",
            )
            logger.debug("Message sent to user_id=%s", user_id)
        except AzureError as exc:
            logger.error("Failed to send to user '%s': %s", user_id, exc)
            raise


    def add_user_to_group(self, user_id: str, group: str) -> None:
        """Adds a user to a group (session)."""
        if self._client is None:
            raise RuntimeError(
                "WebPubSubService is not configured — set WEBPUBSUB_CONNECTION_STRING."
            )
        try:
            self._client.add_user_to_group(group=group, user_id=user_id)
            logger.info("user_id=%s added to group '%s'", user_id, group)
        except AzureError as exc:
            logger.error("Error adding user to group: %s", exc)
            raise

    def remove_user_from_group(self, user_id: str, group: str) -> None:
        """Removes a user from a group (session)."""
        if self._client is None:
            raise RuntimeError(
                "WebPubSubService is not configured — set WEBPUBSUB_CONNECTION_STRING."
            )
        try:
            self._client.remove_user_from_group(group=group, user_id=user_id)
            logger.info("user_id=%s removed from group '%s'", user_id, group)
        except AzureError as exc:
            logger.error("Error removing user from group: %s", exc)
            raise

    def check_connection(self) -> bool:
        """Return True if the Web PubSub connection is operational."""
        if self._client is None:
            return False
        try:
            # Generate a test token — lightweight operation with no side effect
            self._client.get_client_access_token(
                user_id="healthcheck", minutes_to_expire=1
            )
            return True
        except Exception as exc:
            logger.warning("WebPubSub health check failed: %s", exc)
            return False
