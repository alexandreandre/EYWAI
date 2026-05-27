"""Tests du client OpenRouter partagé."""

import os
from unittest.mock import MagicMock, patch

import pytest

from app.shared.infrastructure.ai import (
    MODEL_COPILOT,
    chat_completions_create,
    is_llm_configured,
    resolve_model,
)
from app.shared.infrastructure.ai.models import GPT_4O_MINI

pytestmark = pytest.mark.unit


class TestResolveModel:
    def test_alias_gpt4o_mini(self):
        assert resolve_model("gpt-4o-mini") == GPT_4O_MINI

    def test_passthrough_openrouter_id(self):
        assert resolve_model("anthropic/claude-3.5-sonnet") == "anthropic/claude-3.5-sonnet"

    def test_models_per_use_case_all_gpt4o_mini_for_now(self):
        assert MODEL_COPILOT == GPT_4O_MINI


class TestIsLlmConfigured:
    def test_false_without_key(self, monkeypatch):
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
        assert is_llm_configured() is False

    def test_true_with_key(self, monkeypatch):
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")
        assert is_llm_configured() is True


class TestChatCompletionsCreate:
    @patch("app.shared.infrastructure.ai.client.get_chat_client")
    def test_delegates_to_client(self, mock_get_client, monkeypatch):
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.chat.completions.create.return_value = "ok"

        chat_completions_create(
            model=MODEL_COPILOT,
            messages=[{"role": "user", "content": "test"}],
            temperature=0,
        )

        mock_client.chat.completions.create.assert_called_once()
        call_kwargs = mock_client.chat.completions.create.call_args.kwargs
        assert call_kwargs["model"] == GPT_4O_MINI
        assert call_kwargs["messages"] == [{"role": "user", "content": "test"}]

    def test_model_required(self, monkeypatch):
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")
        with pytest.raises(TypeError):
            chat_completions_create(messages=[{"role": "user", "content": "x"}])
