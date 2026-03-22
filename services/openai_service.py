"""Azure OpenAI Chat Completions wrapper."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)


@dataclass
class OpenAIConfig:
    """Explicit configuration for OpenAIService (bypasses shared.config)."""

    key: str
    endpoint: str
    deployment: str = "gpt-4o-mini"
    api_version: str = "2025-01-01-preview"


class OpenAIService:
    """Thin synchronous wrapper around Azure OpenAI Chat Completions."""

    def __init__(self, config: Optional[OpenAIConfig] = None) -> None:
        if config is None:
            from shared.config import settings  # noqa: PLC0415
            config = OpenAIConfig(
                key=settings.openai_key or "",
                endpoint=settings.openai_endpoint or "",
                deployment=settings.openai_deployment or "gpt-4o-mini",
                api_version=settings.openai_api_version or "2025-01-01-preview",
            )
        self._key = config.key
        self._endpoint = config.endpoint
        self._deployment = config.deployment
        self._api_version = config.api_version

    @property
    def is_enabled(self) -> bool:
        """True when both key and endpoint are set."""
        return bool(self._key and self._endpoint)

    def chat_complete_sync(
        self,
        messages: List[Dict[str, Any]],
        max_tokens: int = 256,
        temperature: float = 0.1,
    ) -> Optional[str]:
        """
        Call Azure OpenAI Chat Completions synchronously.

        Parameters
        ----------
        messages:
            List of ``{"role": ..., "content": ...}`` dicts.
        max_tokens:
            Upper bound on the generated token count.
        temperature:
            Sampling temperature (0.0 = deterministic).

        Returns
        -------
        str | None
            The assistant reply text, or ``None`` when the call fails.
            Never raises on network / API errors — failures are logged as
            warnings and ``None`` is returned so callers can apply fallbacks.

        Raises
        ------
        RuntimeError
            When ``AZURE_OPENAI_KEY`` or ``AZURE_OPENAI_ENDPOINT`` are not
            configured — fail-fast so misconfiguration is visible early.
        """
        if not self.is_enabled:
            raise RuntimeError(
                "OpenAIService: Azure OpenAI not configured — "
                "set AZURE_OPENAI_KEY and AZURE_OPENAI_ENDPOINT."
            )

        url = (
            f"{self._endpoint.rstrip('/')}/openai/deployments/"
            f"{self._deployment}/chat/completions"
            f"?api-version={self._api_version}"
        )
        body: Dict[str, Any] = {
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.post(
                    url,
                    json=body,
                    headers={
                        "api-key": self._key,
                        "Content-Type": "application/json",
                    },
                )
                resp.raise_for_status()
                return resp.json()["choices"][0]["message"]["content"].strip()
        except Exception as exc:
            logger.warning("OpenAIService.chat_complete_sync failed: %s", exc)
            return None
