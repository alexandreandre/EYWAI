"""
Extraction JSON structurée via OpenRouter (contexte injecté, sans recherche web).
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

from app.shared.infrastructure.ai.client import chat_completions_create, require_llm_api_key

logger = logging.getLogger(__name__)


@dataclass
class StructuredExtractionResult:
    data: dict[str, Any]
    tokens_used: int


def extract_structured_json(
    *,
    system_prompt: str,
    user_prompt: str,
    json_schema: dict[str, Any],
    schema_name: str = "extraction",
    model: str,
    temperature: float = 0.0,
    max_tokens: int | None = None,
    timeout: float | None = None,
) -> StructuredExtractionResult | None:
    """
    Appelle OpenRouter avec sortie JSON strictement schématisée.
    Retry une fois en cas d'échec de parsing JSON.
    """
    require_llm_api_key()
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
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
    if timeout is not None:
        request_kwargs["timeout"] = timeout

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
                "extract_structured_json tentative %s échouée: %s", attempt + 1, exc
            )

    logger.error("extract_structured_json échouée après retry: %s", last_error)
    return None
