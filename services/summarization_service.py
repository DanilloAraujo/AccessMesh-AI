from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "You are an expert meeting assistant. "
    "Given the transcript below, produce a 2–3 sentence summary and "
    "up to 5 bullet-point key takeaways. "
    "Respond in JSON: {\"summary\": \"...\", \"key_points\": [\"...\", ...]}."
)



@dataclass
class SummarizationConfig:

    api_key: str = ""
    api_endpoint: str = ""
    deployment_name: str = "gpt-4o-mini"
    api_version: str = "2025-01-01-preview"
    max_tokens: int = 512
    temperature: float = 0.3
    timeout_seconds: float = 30.0


class SummarizationService:
    """
    Service for generating meeting summaries and key points using Azure OpenAI.

    This class provides asynchronous and synchronous methods to summarize transcripts using a language model,
    returning a summary and key bullet points in JSON format.
    """

    def __init__(self, config: Optional[SummarizationConfig] = None) -> None:
        """
        Initialize the SummarizationService with the given configuration or from shared settings.

        Args:
            config (Optional[SummarizationConfig]): Optional configuration for summarization. If not provided, uses shared settings.
        """
        if config is None:
            from shared.config import settings  # noqa: PLC0415
            config = SummarizationConfig(
                api_key=settings.openai_key or "",
                api_endpoint=settings.openai_endpoint or "",
                deployment_name=settings.openai_deployment or "gpt-4o-mini",
                api_version=settings.openai_api_version or "2025-01-01-preview",
            )
        self._config = config


    async def _llm_summarise(self, full_text: str) -> Dict[str, Any]:
        """
        Asynchronously summarize the given text using Azure OpenAI.

        Args:
            full_text (str): The full transcript text to summarize.

        Returns:
            Dict[str, Any]: A dictionary with 'summary' and 'key_points'.
        """
        import json

        url = (
            f"{self._config.api_endpoint.rstrip('/')}"
            f"/openai/deployments/{self._config.deployment_name}"
            f"/chat/completions?api-version={self._config.api_version}"
        )
        headers = {
            "Content-Type": "application/json",
            "api-key": self._config.api_key,
        }
        body = {
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": full_text},
            ],
            "max_tokens": self._config.max_tokens,
            "temperature": self._config.temperature,
        }

        async with httpx.AsyncClient(timeout=self._config.timeout_seconds) as client:
            response = await client.post(url, headers=headers, json=body)
            response.raise_for_status()
            raw_json = response.json()

        content = raw_json["choices"][0]["message"]["content"]
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            return {"summary": content, "key_points": []}


    async def summarise(
        self,
        transcript_texts: List[str],
    ) -> Dict[str, Any]:
        """
        Asynchronously summarize a list of transcript texts.

        Args:
            transcript_texts (List[str]): List of transcript segments to summarize.

        Returns:
            Dict[str, Any]: A dictionary with 'summary' and 'key_points'.

        Raises:
            RuntimeError: If the service is not properly configured.
        """
        full_text = " ".join(t for t in transcript_texts if t.strip())

        if not self._config.api_key or not self._config.api_endpoint:
            raise RuntimeError(
                "SummarizationService: Azure OpenAI credentials not configured — "
                "set AZURE_OPENAI_KEY and AZURE_OPENAI_ENDPOINT."
            )

        result = await self._llm_summarise(full_text)
        result.setdefault("stub", False)
        logger.info(
            "SummarizationService: LLM summary generated (%d chars).",
            len(result.get("summary", "")),
        )
        return result

    def _llm_summarise_sync(self, full_text: str) -> Dict[str, Any]:
        """
        Synchronously summarize the given text using Azure OpenAI.

        Args:
            full_text (str): The full transcript text to summarize.

        Returns:
            Dict[str, Any]: A dictionary with 'summary' and 'key_points'.
        """
        import json

        url = (
            f"{self._config.api_endpoint.rstrip('/')}"
            f"/openai/deployments/{self._config.deployment_name}"
            f"/chat/completions?api-version={self._config.api_version}"
        )
        headers = {
            "Content-Type": "application/json",
            "api-key": self._config.api_key,
        }
        body = {
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": full_text},
            ],
            "max_tokens": self._config.max_tokens,
            "temperature": self._config.temperature,
        }
        with httpx.Client(timeout=self._config.timeout_seconds) as client:
            response = client.post(url, headers=headers, json=body)
            response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            return {"summary": content, "key_points": []}

    def summarise_sync(self, transcript_texts: List[str]) -> Dict[str, Any]:
        """
        Synchronously summarize a list of transcript texts.

        Args:
            transcript_texts (List[str]): List of transcript segments to summarize.

        Returns:
            Dict[str, Any]: A dictionary with 'summary' and 'key_points'.

        Raises:
            RuntimeError: If the service is not properly configured.
        """
        full_text = " ".join(t for t in transcript_texts if t.strip())

        if not self._config.api_key or not self._config.api_endpoint:
            raise RuntimeError(
                "SummarizationService: Azure OpenAI credentials not configured — "
                "set AZURE_OPENAI_KEY and AZURE_OPENAI_ENDPOINT."
            )

        result = self._llm_summarise_sync(full_text)
        result.setdefault("stub", False)
        logger.info(
            "SummarizationService: LLM summary generated (%d chars).",
            len(result.get("summary", "")),
        )
        return result
