"""Azure AI Content Safety wrapper."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

_DEFAULT_THRESHOLD = 2  # Azure score: 0=safe, 2=low, 4=medium, 6=high


@dataclass
class ContentSafetyConfig:
    endpoint: str
    key: str
    threshold: int = _DEFAULT_THRESHOLD


class ContentSafetyResult:
    def __init__(self, safe: bool, category: str = "", score: int = 0, reason: str = "") -> None:
        self.safe = safe
        self.category = category
        self.score = score
        self.reason = reason

    def __repr__(self) -> str:
        return f"ContentSafetyResult(safe={self.safe}, category={self.category!r}, score={self.score})"


class ContentSafetyService:
    """Wraps Azure AI Content Safety text analysis."""

    def __init__(self, config: Optional[ContentSafetyConfig] = None) -> None:
        if config is None:
            from shared.config import settings  # noqa: PLC0415
            if settings.content_safety_endpoint and settings.content_safety_key:
                config = ContentSafetyConfig(
                    endpoint=settings.content_safety_endpoint,
                    key=settings.content_safety_key,
                )
        self._enabled = False
        self._client = None
        self._threshold = _DEFAULT_THRESHOLD

        if config and config.endpoint and config.key:
            try:
                from azure.ai.contentsafety import ContentSafetyClient  # type: ignore[import]
                from azure.core.credentials import AzureKeyCredential

                self._client = ContentSafetyClient(
                    endpoint=config.endpoint,
                    credential=AzureKeyCredential(config.key),
                )
                self._threshold = config.threshold
                self._enabled = True
                logger.info("ContentSafetyService: connected to %s", config.endpoint)
            except Exception as exc:
                logger.error(
                    "ContentSafetyService: failed to init — service will be disabled. %s", exc
                )
                # Degrade gracefully: a Content Safety init failure (e.g. transient network
                # issue, wrong credentials) must not prevent the application from starting.
                # analyze_text() will raise RuntimeError only when explicitly called while
                # _enabled is False, giving callers a clear signal to handle the absence.

    def analyze_text(self, text: str) -> ContentSafetyResult:
        """
        Analyze text for harmful content.
        Returns ContentSafetyResult with safe=True when the text is safe to publish.
        Raises RuntimeError when the service is not configured.
        """
        if not self._enabled:
            raise RuntimeError(
                "ContentSafetyService is not configured — set CONTENT_SAFETY_ENDPOINT and CONTENT_SAFETY_KEY."
            )
        if not text.strip():
            return ContentSafetyResult(safe=True)

        if self._client is None: raise RuntimeError("ContentSafetyService client is not initialized")
        try:
            from azure.ai.contentsafety.models import AnalyzeTextOptions  # type: ignore[import]

            request = AnalyzeTextOptions(text=text[:10_000])
            response = self._client.analyze_text(request)

            for item in (response.categories_analysis or []):
                if item.severity is not None and item.severity >= self._threshold:
                    logger.warning(
                        "ContentSafety: blocked text — category=%s severity=%d",
                        item.category, item.severity
                    )
                    return ContentSafetyResult(
                        safe=False,
                        category=str(item.category),
                        score=item.severity,
                        reason=f"Content flagged as {item.category} (severity={item.severity})",
                    )
            return ContentSafetyResult(safe=True)

        except Exception as exc:
            logger.error("ContentSafetyService.analyze_text error: %s", exc)
            raise

    @property
    def is_enabled(self) -> bool:
        return self._enabled
