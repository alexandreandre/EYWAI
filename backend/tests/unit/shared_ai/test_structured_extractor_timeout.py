# backend/tests/unit/shared_ai/test_structured_extractor_timeout.py
"""extract_structured_json transmet le timeout par requête au client."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


def test_timeout_forwarded_to_client():
    from app.shared.infrastructure.ai import structured_extractor as se

    fake_resp = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content='{"ok": 1}'))],
        usage=SimpleNamespace(total_tokens=5),
    )
    with (
        patch.object(se, "require_llm_api_key"),
        patch.object(se, "chat_completions_create", MagicMock(return_value=fake_resp)) as mock_create,
    ):
        result = se.extract_structured_json(
            system_prompt="s",
            user_prompt="u",
            json_schema={"type": "object", "properties": {}, "additionalProperties": False},
            model="google/gemini-2.5-flash",
            timeout=60.0,
        )

    assert result is not None
    assert mock_create.call_args.kwargs["timeout"] == 60.0
