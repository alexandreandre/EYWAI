"""
Extraction JSON structurée depuis une image via OpenRouter (multimodal).
"""

from __future__ import annotations

import base64
import json
import logging
from typing import Any

from app.shared.infrastructure.ai.client import chat_completions_create, require_llm_api_key
from app.shared.infrastructure.ai.structured_extractor import StructuredExtractionResult

logger = logging.getLogger(__name__)


def _image_data_url(image_bytes: bytes, mime_type: str) -> str:
    encoded = base64.b64encode(image_bytes).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def extract_structured_json_from_image(
    *,
    system_prompt: str,
    user_prompt: str,
    image_bytes: bytes,
    mime_type: str = "image/png",
    json_schema: dict[str, Any],
    schema_name: str = "vision_extraction",
    model: str,
    temperature: float = 0.0,
    max_tokens: int | None = None,
) -> StructuredExtractionResult | None:
    """
    Appelle OpenRouter avec une image + consigne texte, sortie JSON schématisée.
    Retry une fois en cas d'échec de parsing JSON.
    """
    require_llm_api_key()
    data_url = _image_data_url(image_bytes, mime_type)
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": user_prompt},
                {"type": "image_url", "image_url": {"url": data_url}},
            ],
        },
    ]
    request_kwargs: dict[str, Any] = {
        "model": model,
        "temperature": temperature,
        "messages": messages,
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": schema_name,
                "strict": True,
                "schema": json_schema,
            },
        },
    }
    if max_tokens is not None:
        request_kwargs["max_tokens"] = max_tokens

    last_error: Exception | None = None
    for attempt in range(2):
        try:
            resp = chat_completions_create(**request_kwargs)
            raw = (resp.choices[0].message.content or "").strip()
            data = json.loads(raw)
            if not isinstance(data, dict):
                return None
            usage = getattr(resp, "usage", None)
            tokens = 0
            if usage is not None:
                tokens = int(getattr(usage, "total_tokens", 0) or 0)
            return StructuredExtractionResult(data=data, tokens_used=tokens)
        except Exception as exc:
            last_error = exc
            logger.warning(
                "extract_structured_json_from_image tentative %s échouée: %s",
                attempt + 1,
                exc,
            )

    logger.error("extract_structured_json_from_image échouée après retry: %s", last_error)
    return None


__all__ = ["extract_structured_json_from_image"]
