"""Tests du client OpenRouter partagé."""

from unittest.mock import MagicMock, patch

import pytest

from app.shared.infrastructure.ai import (
    MODEL_COPILOT_AGREEMENT,
    MODEL_COPILOT_APP_HELP,
    MODEL_COPILOT_PLANNING,
    MODEL_COPILOT_SYNTHESIS,
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

    def test_copilot_a_un_modele_par_role(self):
        """Chaque étape de l'assistant RH choisit son modèle (cf. banc d'essai)."""
        roles = {
            MODEL_COPILOT_PLANNING,
            MODEL_COPILOT_APP_HELP,
            MODEL_COPILOT_AGREEMENT,
            MODEL_COPILOT_SYNTHESIS,
        }
        assert all("/" in modele for modele in roles)
        # La planification est sur le chemin critique de chaque question : elle
        # ne doit pas partager le modèle de la branche convention, plus lourd.
        assert MODEL_COPILOT_PLANNING != MODEL_COPILOT_AGREEMENT

    def test_branche_convention_hors_contexte_128k(self):
        """Le texte de base intégral dépasse le contexte de gpt-4o-mini."""
        assert MODEL_COPILOT_AGREEMENT != GPT_4O_MINI


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
            model=GPT_4O_MINI,
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
