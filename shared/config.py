from __future__ import annotations

import logging
import os
from typing import Any, Dict, Tuple, Type

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict

logger = logging.getLogger(__name__)

_FIELD_TO_KV_SECRET: Dict[str, str] = {
    "webpubsub_connection_string":   "webpubsub-connection-string",
    "azure_speech_key":              "azure-speech-key",
    "gesture_api_key":               "gesture-api-key",
    "openai_key":                    "azure-openai-key",
    "avatar_api_key":                "avatar-api-key",
    "cosmos_key":                    "cosmos-key",
    "content_safety_key":            "content-safety-key",
    "translator_key":                "translator-key",
    "servicebus_connection_string":  "servicebus-connection-string",
    "appinsights_connection_string": "appinsights-connection-string",
    "secret_key":                    "app-secret-key",
}

class KeyVaultSettingsSource(PydanticBaseSettingsSource):
    """
    Custom Pydantic settings source that loads secrets from Azure Key Vault.

    This class attempts to retrieve secret values for configuration fields from Azure Key Vault,
    using the mapping defined in _FIELD_TO_KV_SECRET. If the Key Vault is not configured or
    accessible, it falls back to environment variables. Loaded secrets are stored in the _secrets
    dictionary and are used as a source for Pydantic settings resolution.

    Usage:
        - Set the AZURE_KEYVAULT_URL environment variable to enable Key Vault lookup.
        - Secrets are mapped by field name to Key Vault secret names via _FIELD_TO_KV_SECRET.
        - If Key Vault is unavailable, environment variables are used instead.
    """
    
    def __init__(self, settings_cls: Type[BaseSettings]) -> None:
        super().__init__(settings_cls)
        self._secrets: Dict[str, str] = {}

        vault_url = os.environ.get("AZURE_KEYVAULT_URL", "").strip()
        if not vault_url:
            logger.debug("KeyVaultSettingsSource: AZURE_KEYVAULT_URL not set — skipping KV lookup.")
            return

        try:
            from services.keyvault_service import get_keyvault_service  # noqa: PLC0415

            kv = get_keyvault_service(vault_url)
            if not kv.is_enabled:
                logger.warning(
                    "KeyVaultSettingsSource: KeyVaultService initialisation failed — "
                    "secrets will be read from environment variables instead."
                )
                return

            loaded = 0
            for field_name, secret_name in _FIELD_TO_KV_SECRET.items():
                value = kv.get_secret(secret_name)
                if value:
                    self._secrets[field_name] = value
                    loaded += 1

            logger.info(
                "KeyVaultSettingsSource: loaded %d/%d secret(s) from %s",
                loaded,
                len(_FIELD_TO_KV_SECRET),
                vault_url,
            )
        except Exception as exc:
            logger.error(
                "KeyVaultSettingsSource: unexpected error loading secrets — %s. "
                "Falling back to environment variables.",
                exc,
            )

    def get_field_value(
        self, field: Any, field_name: str
    ) -> Tuple[Any, str, bool]:
        return self._secrets.get(field_name), field_name, False

    def __call__(self) -> Dict[str, Any]:
        return {k: v for k, v in self._secrets.items() if v}


class Settings(BaseSettings):
   
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: Type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> Tuple[PydanticBaseSettingsSource, ...]:
        return (
            init_settings,
            KeyVaultSettingsSource(settings_cls),
            env_settings,
            dotenv_settings,
            file_secret_settings,
        )

    # ── Runtime ───────────────────────────────────────────────────────────────
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    app_debug: bool = False
    app_reload: bool = False

    # ── Key Vault (local dev only — NOT needed in App Service) ───────────────
    azure_keyvault_url: str = ""

    # ── Azure Web PubSub ──────────────────────────────────────────────────────
    webpubsub_connection_string: str = ""
    webpubsub_hub_name: str = "accessmesh"

    # ── Azure Speech ──────────────────────────────────────────────────────────
    azure_speech_key: str = ""
    azure_speech_region: str = ""
    speech_default_language: str = "en-US"

    # ── Azure OpenAI (Gesture) ────────────────────────────────────────────────
    gesture_api_key: str = ""
    gesture_api_endpoint: str = ""
    gesture_api_deployment_name: str = "gpt-4o-mini"
    gesture_api_version: str = "2025-01-01-preview"

    # ── Azure OpenAI ──────────────────────────────────────────────────────────
    openai_key: str = Field(default="", validation_alias=AliasChoices("azure_openai_api_key", "openai_key"))
    openai_endpoint: str = Field(default="", validation_alias=AliasChoices("azure_openai_endpoint", "openai_endpoint"))
    openai_deployment: str = Field(
        default="gpt-4o-mini",
        validation_alias=AliasChoices("azure_openai_deployment_name", "openai_deployment"),
    )
    openai_api_version: str = Field(
        default="2025-01-01-preview",
        validation_alias=AliasChoices("azure_openai_api_version", "openai_api_version"),
    )

    # ── Avatar ────────────────────────────────────────────────────────────────
    avatar_api_key: str = ""
    avatar_api_endpoint: str = ""
    avatar_provider: str = "stub"

    # ── Azure Cosmos DB ───────────────────────────────────────────────────────
    cosmos_endpoint: str = ""
    cosmos_key: str = ""
    cosmos_database: str = "accessmesh"
    cosmos_container_sessions: str = "sessions"
    cosmos_container_messages: str = "messages"
    cosmos_container_users: str = "users"

    # ── Azure Content Safety ──────────────────────────────────────────────────
    content_safety_endpoint: str = ""
    content_safety_key: str = ""

    # ── Azure AI Translator ───────────────────────────────────────────────────
    translator_key: str = ""
    translator_endpoint: str = "https://api.cognitive.microsofttranslator.com"
    translator_region: str = ""

    # ── Azure Service Bus ─────────────────────────────────────────────────────
    servicebus_connection_string: str = ""
    servicebus_topic_name: str = "accessmesh-events"

    # ── Azure Application Insights ────────────────────────────────────────────
    appinsights_connection_string: str = ""

    # ── JWT Auth ──────────────────────────────────────────────────────────────
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 480

    secret_key: str = Field(
        default="",
        description=(
            "Application signing secret. In production set via the Key Vault secret "
            "'app-secret-key' (resolved by App Service KV Reference) or the SECRET_KEY "
            "environment variable. An empty or weak value will emit a startup warning."
        ),
    )
    cors_origins: list[str] = Field(
        default=["http://localhost:5173", "http://localhost:3000"],
        description="Allowed CORS origins. Restrict to your frontend domain in production.",
    )

    @field_validator("secret_key", mode="after")
    @classmethod
    def _warn_weak_secret(cls, v: str) -> str:
        _insecure = {
            "",
            "changeme_super_secret_key",
            "changeme",
            "secret",
            "REPLACE_WITH_STRONG_RANDOM_SECRET",
        }
        if v in _insecure:
            import logging as _logging
            _logging.getLogger(__name__).warning(
                "SECRET_KEY is empty or uses an insecure default. "
                "Set the 'app-secret-key' secret in Azure Key Vault "
                "(or SECRET_KEY env var) before deploying to production."
            )
        return v


settings = Settings()
