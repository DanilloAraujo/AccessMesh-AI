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
    """
    Represents the result of a content safety analysis.

    Attributes:
        safe (bool): Whether the content is considered safe.
        category (str): The category of detected unsafe content, if any.
        score (int): The severity score of the detected content.
        reason (str): A human-readable reason for the result.
    """
    def __init__(self, safe: bool, category: str = "", score: int = 0, reason: str = "") -> None:
        """
        Initialize a ContentSafetyResult instance.

        Args:
            safe (bool): Whether the content is safe.
            category (str, optional): The detected category. Defaults to "".
            score (int, optional): The severity score. Defaults to 0.
            reason (str, optional): The reason for the result. Defaults to "".
        """
        self.safe = safe
        self.category = category
        self.score = score
        self.reason = reason

    def __repr__(self) -> str:
        """
        Return a string representation of the ContentSafetyResult.
        """
        return f"ContentSafetyResult(safe={self.safe}, category={self.category!r}, score={self.score})"


class ContentSafetyService:
    """
    Service for analyzing text content for safety using Azure Content Safety.

    This class provides methods to check if a given text is safe according to configured thresholds and Azure's content safety categories.
    """

    def __init__(self, config: Optional[ContentSafetyConfig] = None) -> None:
        """
        Initialize the ContentSafetyService.

        Args:
            config (Optional[ContentSafetyConfig]): Optional configuration. If not provided, attempts to load from shared settings.
        """
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

    def analyze_text(self, text: str) -> ContentSafetyResult:
        """
        Analyze the given text for unsafe content.

        Args:
            text (str): The text to analyze.

        Returns:
            ContentSafetyResult: The result of the analysis, indicating if the text is safe, and details if not.

        Raises:
            RuntimeError: If the service is not enabled or not properly configured.
            Exception: If an error occurs during analysis.
        """
        if not self._enabled:
            raise RuntimeError(
                "ContentSafetyService is not configured — set CONTENT_SAFETY_ENDPOINT and CONTENT_SAFETY_KEY."
            )
        if not text.strip():
            return ContentSafetyResult(safe=True)

        if self._client is None:
            raise RuntimeError("ContentSafetyService client is not initialized")
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
        """
        Indicates whether the ContentSafetyService is enabled and properly configured.

        Returns:
            bool: True if the service is enabled, False otherwise.
        """
        return self._enabled
