from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

from azure.core.exceptions import AzureError
from azure.messaging.webpubsubservice import WebPubSubServiceClient
from pydantic import BaseModel

logger = logging.getLogger(__name__)

class WebPubSubConfig(BaseModel):
    connection_string: str
    hub_name: str = "accessmesh"

class WebPubSubService:
    """
    Service for integration with Azure Web PubSub.

    This class encapsulates common operations for real-time communication using Azure Web PubSub,
    including access token generation, sending messages to all, groups, or specific users,
    and managing user groups.

    Main methods:
        - get_client_access_token: Generates an access token for clients to connect to the hub.
        - send_to_all: Sends a message to all clients connected to the hub.
        - send_to_group: Sends a message to a specific group of clients.
        - send_to_user: Sends a message to a specific user.
        - add_user_to_group: Adds a user to a group.
        - remove_user_from_group: Removes a user from a group.
        - check_connection: Checks if the service connection is functional.
    """

    def __init__(self, config: Optional[WebPubSubConfig] = None) -> None:
        """
        Initialize the WebPubSubService with the given configuration or from shared settings.

        Args:
            config (Optional[WebPubSubConfig]): Optional configuration for Web PubSub. If not provided, uses shared settings.
        """
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
        """
        Indicates whether the WebPubSubService is enabled and properly configured.

        Returns:
            bool: True if the service is enabled, False otherwise.
        """
        return self._client is not None


    def get_client_access_token(
        self,
        user_id: str,
        groups: Optional[list[str]] = None,
        roles: Optional[list[str]] = None,
        minutes_to_expire: int = 60,
    ) -> Dict[str, Any]:
        """
        Generate an access token for a client to connect to the Web PubSub hub.

        Args:
            user_id (str): The user ID for the token.
            groups (Optional[list[str]]): Optional list of groups the user can join.
            roles (Optional[list[str]]): Optional list of roles for the user.
            minutes_to_expire (int): Token expiration time in minutes.

        Returns:
            Dict[str, Any]: A dictionary containing the token, URL, user ID, and hub name.

        Raises:
            RuntimeError: If the service is not configured.
            AzureError: If token generation fails.
        """
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
        """
        Send a message to all clients connected to the hub.

        Args:
            message (Dict[str, Any]): The message payload to send.

        Raises:
            RuntimeError: If the service is not configured.
            AzureError: If sending fails.
        """
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
        """
        Send a message to a specific group of clients.

        Args:
            group (str): The group name.
            message (Dict[str, Any]): The message payload to send.

        Raises:
            RuntimeError: If the service is not configured.
            AzureError: If sending fails.
        """
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
        """
        Send a message to a specific user.

        Args:
            user_id (str): The user ID.
            message (Dict[str, Any]): The message payload to send.

        Raises:
            RuntimeError: If the service is not configured.
            AzureError: If sending fails.
        """
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
        """
        Add a user to a group.

        Args:
            user_id (str): The user ID.
            group (str): The group name.

        Raises:
            RuntimeError: If the service is not configured.
            AzureError: If the operation fails.
        """
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
        """
        Remove a user from a group.

        Args:
            user_id (str): The user ID.
            group (str): The group name.

        Raises:
            RuntimeError: If the service is not configured.
            AzureError: If the operation fails.
        """
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
        """
        Check if the WebPubSubService connection is functional.

        Returns:
            bool: True if the connection is healthy, False otherwise.
        """
        if self._client is None:
            return False
        try:
            self._client.get_client_access_token(
                user_id="healthcheck", minutes_to_expire=1
            )
            return True
        except Exception as exc:
            logger.warning("WebPubSub health check failed: %s", exc)
            return False
