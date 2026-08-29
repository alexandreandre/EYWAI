"""Extraction JSON structurée depuis un PDF envoyé nativement au modèle (sans OCR local)."""

from __future__ import annotations

import base64
import json
import logging
from typing import Any

from app.shared.infrastructure.ai.client import require_llm_api_key
from app.shared.infrastructure.ai.client_async import chat_completions_create_async
from app.shared.infrastructure.ai.structured_extractor import StructuredExtractionResult

logger = logging.getLogger(__name__)


async def extract_structured_json_from_pdf(
    *,
    system_prompt: str,
    user_prompt: str,
    pdf_bytes: bytes,
    filename: str = "document.pdf",
    json_schema: dict[str, Any],
    schema_name: str = "pdf_extraction",
    model: str,
    temperature: float = 0.0,
    max_tokens: int | None = None,
) -> StructuredExtractionResult | None:
    """PDF en file part OpenRouter + sortie JSON schématisée. Retry une fois."""
    require_llm_api_key()
    encoded = base64.b64encode(pdf_bytes).decode("ascii")
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": user_prompt},
                {
                    "type": "file",
                    "file": {
                        "filename": filename,
                        "file_data": f"data:application/pdf;base64,{encoded}",
                    },
                },
            ],
        },
    ]
    request_kwargs: dict[str, Any] = {
        "model": model,
        "temperature": temperature,
        "messages": messages,
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": schema_name, "strict": True, "schema": json_schema},
        },
    }
    if max_tokens is not None:
        request_kwargs["max_tokens"] = max_tokens

    last_error: Exception | None = None
    for attempt in range(2):
        try:
            resp = await chat_completions_create_async(**request_kwargs)
            raw = (resp.choices[0].message.content or "").strip()
            data = json.loads(raw)
            if not isinstance(data, dict):
                return None
            usage = getattr(resp, "usage", None)
            tokens = int(getattr(usage, "total_tokens", 0) or 0) if usage else 0
            return StructuredExtractionResult(data=data, tokens_used=tokens)
        except Exception as exc:
            last_error = exc
            logger.warning(
                "extract_structured_json_from_pdf tentative %s échouée: %s",
                attempt + 1,
                exc,
            )
    logger.error("extract_structured_json_from_pdf échouée après retry: %s", last_error)
    return None


__all__ = ["extract_structured_json_from_pdf"]
