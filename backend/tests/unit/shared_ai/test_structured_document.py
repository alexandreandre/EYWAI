"""Entrée PDF native : file part OpenRouter, parsing JSON, retry."""

import asyncio
import base64
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

pytestmark = pytest.mark.unit

_PDF = b"%PDF-1.4 fake"
_SCHEMA = {"type": "object", "properties": {"x": {"type": "integer"}}, "required": ["x"], "additionalProperties": False}


def _resp(content: str, tokens: int = 10):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
        usage=SimpleNamespace(total_tokens=tokens),
    )


def test_pdf_sent_as_file_part_and_parsed(monkeypatch):
    from app.shared.infrastructure.ai import structured_document as sd

    mock_create = AsyncMock(return_value=_resp('{"x": 7}'))
    monkeypatch.setattr(sd, "chat_completions_create_async", mock_create)

    result = asyncio.run(
        sd.extract_structured_json_from_pdf(
            system_prompt="sys",
            user_prompt="user",
            pdf_bytes=_PDF,
            filename="releve.pdf",
            json_schema=_SCHEMA,
            model="google/gemini-2.5-flash",
        )
    )

    assert result is not None and result.data == {"x": 7} and result.tokens_used == 10
    kwargs = mock_create.call_args.kwargs
    parts = kwargs["messages"][1]["content"]
    file_part = next(p for p in parts if p["type"] == "file")
    assert file_part["file"]["filename"] == "releve.pdf"
    expected_prefix = "data:application/pdf;base64," + base64.b64encode(_PDF).decode()[:8]
    assert file_part["file"]["file_data"].startswith(expected_prefix)
    assert kwargs["response_format"]["json_schema"]["strict"] is True


def test_retry_once_then_none(monkeypatch):
    from app.shared.infrastructure.ai import structured_document as sd

    mock_create = AsyncMock(side_effect=[_resp("pas du json"), _resp("toujours pas")])
    monkeypatch.setattr(sd, "chat_completions_create_async", mock_create)

    result = asyncio.run(
        sd.extract_structured_json_from_pdf(
            system_prompt="s", user_prompt="u", pdf_bytes=_PDF,
            json_schema=_SCHEMA, model="google/gemini-2.5-flash",
        )
    )
    assert result is None
    assert mock_create.call_count == 2
