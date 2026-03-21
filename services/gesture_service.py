from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

@dataclass
class GestureConfig:

    api_key: str = ""
    api_endpoint: str = ""
    model_name: str = "stub"
    deployment_name: str = "gpt-4o"
    api_version: str = "2025-01-01-preview"
    confidence_threshold: float = 0.7
    timeout_seconds: float = 10.0




class GestureService:
    """
    Service for gesture recognition using rule-based and Azure OpenAI methods.

    This class provides methods to recognize gestures from labels, hand landmarks, or image frames (base64),
    supporting both local rule-based and cloud-based (OpenAI) approaches.
    """

    def __init__(self, config: Optional[GestureConfig] = None) -> None:
        """
        Initialize the GestureService with the given configuration or from shared settings.

        Args:
            config (Optional[GestureConfig]): Optional configuration for gesture recognition. If not provided, uses shared settings.
        """
        if config is None:
            from shared.config import settings  # noqa: PLC0415
            config = GestureConfig(
                api_key=settings.gesture_api_key or "",
                api_endpoint=settings.gesture_api_endpoint or "",
                model_name="azure_openai" if (settings.gesture_api_endpoint and settings.gesture_api_key) else "stub",
                deployment_name=settings.gesture_api_deployment_name or "gpt-4o",
                api_version=settings.gesture_api_version or "2025-01-01-preview",
            )
        self._config = config


    def recognise_from_label(
        self,
        gesture_label: str,
    ) -> Dict[str, Any]:
        """
        Recognize a gesture from a label string.

        Args:
            gesture_label (str): The gesture label (e.g., 'thumbs_up').

        Returns:
            Dict[str, Any]: A dictionary with the recognized text, label, and confidence.
        """
        text = gesture_label.replace("_", " ").capitalize()
        logger.debug("GestureService.recognise_from_label: '%s' → '%s'", gesture_label, text)
        return {"text": text, "gesture_label": gesture_label, "confidence": 1.0}


    @staticmethod
    def _classify_landmarks_rule_based(
        landmarks: List[Dict[str, float]],
    ) -> Dict[str, Any]:
        """
        Rule-based classification of hand landmarks into gesture labels.

        Args:
            landmarks (List[Dict[str, float]]): List of hand landmark points.

        Returns:
            Dict[str, Any]: A dictionary with the recognized text, label, and confidence.
        """
        if len(landmarks) < 21:
            return {"text": "", "gesture_label": "unknown", "confidence": 0.0}

        def y(i: int) -> float: return landmarks[i]["y"]
        def x(i: int) -> float: return landmarks[i]["x"]

        def extended(tip_i: int, pip_i: int) -> bool:
            return y(tip_i) < y(pip_i) - 0.04

        def hypot2(i: int, j: int) -> float:
            return ((x(i) - x(j)) ** 2 + (y(i) - y(j)) ** 2) ** 0.5

        th  = hypot2(4, 5) > 0.10
        idx = extended(8, 6)
        mid = extended(12, 10)
        rng = extended(16, 14)
        pnk = extended(20, 18)

        ok_sign = hypot2(4, 8) < 0.07 and mid and rng and pnk

        if ok_sign:
            return {"text": "OK",         "gesture_label": "ok_sign",    "confidence": 0.90}
        if th and idx and not mid and not rng and pnk:
            return {"text": "I love you", "gesture_label": "i_love_you", "confidence": 0.90}
        if th and not idx and not mid and not rng and pnk:
            return {"text": "Hang loose", "gesture_label": "shaka",      "confidence": 0.85}
        if not th and idx and not mid and not rng and pnk:
            return {"text": "Rock on",    "gesture_label": "rock_on",    "confidence": 0.85}
        if not th and idx and mid and not rng and not pnk:
            return {"text": "Peace",      "gesture_label": "peace",      "confidence": 0.90}
        if not th and idx and not mid and not rng and not pnk:
            return {"text": "One",        "gesture_label": "pointing",   "confidence": 0.85}
        if th and not idx and not mid and not rng and not pnk:
            if y(4) < y(0):
                return {"text": "Good",   "gesture_label": "thumbs_up",  "confidence": 0.90}
            return {"text": "No",         "gesture_label": "thumbs_down","confidence": 0.80}
        if idx and mid and rng and pnk:
            return {"text": "Hello",      "gesture_label": "open_hand",  "confidence": 0.85}
        if not th and not idx and not mid and not rng and not pnk:
            return {"text": "Yes",        "gesture_label": "fist",       "confidence": 0.80}

        return {"text": "", "gesture_label": "unknown", "confidence": 0.0}

    def recognise_from_landmarks(
        self,
        landmarks: List[Dict[str, float]],
    ) -> Dict[str, Any]:
        """
        Recognize a gesture from a list of hand landmarks using rule-based logic.

        Args:
            landmarks (List[Dict[str, float]]): List of hand landmark points.

        Returns:
            Dict[str, Any]: A dictionary with the recognized text, label, and confidence.
        """
        result = self._classify_landmarks_rule_based(landmarks)
        logger.debug(
            "GestureService.recognise_from_landmarks: %s (conf=%.2f)",
            result["gesture_label"], result["confidence"],
        )
        return result


    async def recognise_from_frame_b64(
        self,
        frame_b64: str,
        mime_type: str = "image/jpeg",
    ) -> Dict[str, Any]:
        """
        Recognize a gesture from a base64-encoded image frame using Azure OpenAI.

        Args:
            frame_b64 (str): The base64-encoded image data.
            mime_type (str, optional): The MIME type of the image. Defaults to "image/jpeg".

        Returns:
            Dict[str, Any]: A dictionary with the recognized text, label, and confidence.

        Raises:
            RuntimeError: If the service is not properly configured.
            json.JSONDecodeError: If the response cannot be parsed.
            httpx.HTTPStatusError: If the HTTP request fails.
        """
        if not self._config.api_endpoint or not self._config.api_key or self._config.model_name == "stub":
            raise RuntimeError(
                "GestureService: Azure OpenAI is not configured — "
                "set GESTURE_API_ENDPOINT and GESTURE_API_KEY to enable frame-based gesture recognition."
            )

        url = (
            f"{self._config.api_endpoint.rstrip('/')}/openai/deployments/"
            f"{self._config.deployment_name}/chat/completions"
            f"?api-version={self._config.api_version}"
        )
        payload = {
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are an expert sign language interpreter specialising in ASL and LIBRAS. "
                        "Analyse the image and identify any sign language gesture being performed. "
                        "Respond ONLY with a valid JSON object — no markdown, no extra text: "
                        '{"gesture_label":"<snake_case>","text":"<English translation>","confidence":<0.0-1.0>}. '
                        'If no clear sign is visible respond: {"gesture_label":"unknown","text":"","confidence":0.0}.'
                    ),
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime_type};base64,{frame_b64}",
                                "detail": "low",
                            },
                        },
                        {
                            "type": "text",
                            "text": "What sign language gesture is the person making?",
                        },
                    ],
                },
            ],
            "max_tokens": 80,
            "temperature": 0,
        }

        try:
            async with httpx.AsyncClient(timeout=self._config.timeout_seconds) as client:
                resp = await client.post(
                    url,
                    json=payload,
                    headers={
                        "api-key": self._config.api_key,
                        "Content-Type": "application/json",
                    },
                )
                resp.raise_for_status()
            raw = resp.json()["choices"][0]["message"]["content"].strip()
            raw = raw.lstrip("```json").lstrip("```").rstrip("```").strip()
            parsed = json.loads(raw)
            return {
                "text": parsed.get("text", ""),
                "gesture_label": parsed.get("gesture_label", "unknown"),
                "confidence": float(parsed.get("confidence", 0.0)),
            }
        except json.JSONDecodeError as exc:
            logger.warning("GestureService: could not parse Azure OpenAI response: %s", exc)
            raise
        except httpx.HTTPStatusError as exc:
            logger.error(
                "GestureService: Azure OpenAI request failed (%s): %s",
                exc.response.status_code, exc,
            )
            raise
