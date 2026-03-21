from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

class CosmosConfig:

    def __init__(
        self,
        endpoint: str,
        key: str,
        database: str = "accessmesh",
        container_sessions: str = "sessions",
        container_messages: str = "messages",
        container_users: str = "users",
    ) -> None:
        self.endpoint = endpoint
        self.key = key
        self.database = database
        self.container_sessions = container_sessions
        self.container_messages = container_messages
        self.container_users = container_users



class CosmosService:
    """
    Service for interacting with Azure Cosmos DB for sessions, messages, and users.

    This class provides asynchronous methods to initialize the Cosmos DB client, manage sessions, messages, and user data,
    and check if the service is enabled. It supports upserting and retrieving documents in dedicated containers.
    """

    def __init__(self, config: Optional[CosmosConfig] = None) -> None:
        """
        Initialize the CosmosService with the given configuration or from shared settings.

        Args:
            config (Optional[CosmosConfig]): Optional configuration for Cosmos DB. If not provided, uses shared settings.
        """
        if config is None:
            from shared.config import settings  # noqa: PLC0415
            if settings.cosmos_endpoint and settings.cosmos_key:
                config = CosmosConfig(
                    endpoint=settings.cosmos_endpoint,
                    key=settings.cosmos_key,
                    database=settings.cosmos_database,
                    container_sessions=settings.cosmos_container_sessions,
                    container_messages=settings.cosmos_container_messages,
                    container_users=settings.cosmos_container_users,
                )
        self._config = config if (config and config.endpoint and config.key) else None
        self._enabled = False
        self._client: Any = None
        self._sessions_container: Any = None
        self._messages_container: Any = None
        self._users_container: Any = None

    async def initialize(self) -> None:
        """
        Asynchronously initialize the Cosmos DB client and containers.

        Raises:
            RuntimeError: If connection to Cosmos DB fails.
        """
        if not self._config:
            return
        try:
            from azure.cosmos.aio import CosmosClient as _AsyncCosmosClient  # noqa: PLC0415
            from azure.cosmos import PartitionKey  # noqa: PLC0415

            self._client = _AsyncCosmosClient(
                url=self._config.endpoint,
                credential=self._config.key,
            )
            db = await self._client.create_database_if_not_exists(
                id=self._config.database,
                offer_throughput=400,
            )
            self._sessions_container = await db.create_container_if_not_exists(
                id=self._config.container_sessions,
                partition_key=PartitionKey(path="/session_id"),
            )
            self._messages_container = await db.create_container_if_not_exists(
                id=self._config.container_messages,
                partition_key=PartitionKey(path="/session_id"),
            )
            self._users_container = await db.create_container_if_not_exists(
                id=self._config.container_users,
                partition_key=PartitionKey(path="/user_id"),
            )
            self._enabled = True
            logger.info(
                "CosmosService: async connected — database=%s containers=%s,%s,%s",
                self._config.database,
                self._config.container_sessions,
                self._config.container_messages,
                self._config.container_users,
            )
        except Exception as exc:
            logger.error(
                "CosmosService: failed to connect to Azure Cosmos DB. %s", exc
            )
            raise RuntimeError(
                f"CosmosService: failed to connect to Azure Cosmos DB: {exc}"
            ) from exc

    async def close(self) -> None:
        """
        Asynchronously close the Cosmos DB client connection.
        """
        if self._client:
            await self._client.close()
            self._client = None

    # ── Session operations ───────────────────────────────────────────────────

    async def upsert_session(self, session_id: str, data: Dict[str, Any]) -> None:
        """
        Upsert (insert or update) a session document in the sessions container.

        Args:
            session_id (str): The session ID.
            data (Dict[str, Any]): The session data to store.
        """
        if not self._enabled:
            raise RuntimeError("CosmosService is not initialized — call initialize() after configuring COSMOS_ENDPOINT and COSMOS_KEY.")
        doc = {**data, "id": session_id, "session_id": session_id}
        try:
            await self._sessions_container.upsert_item(body=doc)
            logger.debug("CosmosService: upserted session=%s", session_id)
        except Exception as exc:
            logger.warning("CosmosService.upsert_session failed: %s", exc)

    async def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a session document by session ID.

        Args:
            session_id (str): The session ID.

        Returns:
            Optional[Dict[str, Any]]: The session document if found, otherwise None.
        """
        if not self._enabled:
            raise RuntimeError("CosmosService is not initialized — call initialize() after configuring COSMOS_ENDPOINT and COSMOS_KEY.")
        try:
            return await self._sessions_container.read_item(
                item=session_id, partition_key=session_id
            )
        except Exception:
            return None

    async def list_active_sessions(self) -> List[Dict[str, Any]]:
        """
        List all active session documents.

        Returns:
            List[Dict[str, Any]]: A list of active session documents.
        """
        if not self._enabled:
            raise RuntimeError("CosmosService is not initialized — call initialize() after configuring COSMOS_ENDPOINT and COSMOS_KEY.")
        try:
            results: List[Dict[str, Any]] = []
            async for item in self._sessions_container.query_items(
                query="SELECT * FROM c WHERE c.status = 'active'",
            ):
                results.append(item)
            return results
        except Exception as exc:
            logger.warning("CosmosService.list_active_sessions failed: %s", exc)
            return []

    # ── Message operations ───────────────────────────────────────────────────

    async def append_message(self, session_id: str, message: Dict[str, Any]) -> None:
        """
        Append a message document to the messages container for a session.

        Args:
            session_id (str): The session ID.
            message (Dict[str, Any]): The message data to store.
        """
        if not self._enabled:
            raise RuntimeError("CosmosService is not initialized — call initialize() after configuring COSMOS_ENDPOINT and COSMOS_KEY.")
        doc = {
            **message,
            "id": message.get("id") or f"{session_id}_{datetime.now(timezone.utc).timestamp()}",
            "session_id": session_id,
            "stored_at": datetime.now(timezone.utc).isoformat(),
        }
        try:
            await self._messages_container.upsert_item(body=doc)
        except Exception as exc:
            logger.warning("CosmosService.append_message failed: %s", exc)

    async def get_messages(
        self, session_id: str, limit: int = 200
    ) -> List[Dict[str, Any]]:
        """
        Retrieve messages for a session, ordered by stored time.

        Args:
            session_id (str): The session ID.
            limit (int, optional): Maximum number of messages to retrieve. Defaults to 200.

        Returns:
            List[Dict[str, Any]]: A list of message documents.
        """
        if not self._enabled:
            raise RuntimeError("CosmosService is not initialized — call initialize() after configuring COSMOS_ENDPOINT and COSMOS_KEY.")
        try:
            query = (
                f"SELECT TOP {limit} * FROM c WHERE c.session_id = @sid "
                "ORDER BY c.stored_at ASC"
            )
            items: List[Dict[str, Any]] = []
            async for item in self._messages_container.query_items(
                query=query,
                parameters=[{"name": "@sid", "value": session_id}],
                partition_key=session_id,
            ):
                items.append(item)
            return items
        except Exception as exc:
            logger.warning("CosmosService.get_messages failed: %s", exc)
            return []

    @property
    def is_enabled(self) -> bool:
        """
        Indicates whether the CosmosService is enabled and initialized.

        Returns:
            bool: True if the service is enabled, False otherwise.
        """
        return self._enabled

    # ── User operations ──────────────────────────────────────────────

    async def upsert_user(self, user_id: str, data: Dict[str, Any]) -> None:
        """
        Upsert (insert or update) a user document in the users container.

        Args:
            user_id (str): The user ID.
            data (Dict[str, Any]): The user data to store.
        """
        if not self._enabled:
            raise RuntimeError("CosmosService is not initialized — call initialize() after configuring COSMOS_ENDPOINT and COSMOS_KEY.")
        doc = {**data, "id": user_id, "user_id": user_id}
        try:
            await self._users_container.upsert_item(body=doc)
            logger.debug("CosmosService: upserted user=%s", user_id)
        except Exception as exc:
            logger.warning("CosmosService.upsert_user failed: %s", exc)

    async def get_user(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a user document by user ID.

        Args:
            user_id (str): The user ID.

        Returns:
            Optional[Dict[str, Any]]: The user document if found, otherwise None.
        """
        if not self._enabled:
            raise RuntimeError("CosmosService is not initialized — call initialize() after configuring COSMOS_ENDPOINT and COSMOS_KEY.")
        try:
            return await self._users_container.read_item(
                item=user_id, partition_key=user_id
            )
        except Exception:
            return None

    async def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a user document by email address.

        Args:
            email (str): The user's email address.

        Returns:
            Optional[Dict[str, Any]]: The user document if found, otherwise None.
        """
        if not self._enabled:
            raise RuntimeError("CosmosService is not initialized — call initialize() after configuring COSMOS_ENDPOINT and COSMOS_KEY.")
        try:
            results: List[Dict[str, Any]] = []
            async for item in self._users_container.query_items(
                query="SELECT * FROM c WHERE c.email = @email",
                parameters=[{"name": "@email", "value": email}],
            ):
                results.append(item)
            return results[0] if results else None
        except Exception as exc:
            logger.warning("CosmosService.get_user_by_email failed: %s", exc)
            return None
