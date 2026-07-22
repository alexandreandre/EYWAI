"""Tests du provider LLM sans génération ni exécution SQL."""

from unittest.mock import MagicMock, patch

import pytest

from app.modules.copilot.infrastructure.providers import OpenAIProvider


pytestmark = pytest.mark.unit


def test_provider_exposes_no_sql_generation_method():
    provider = OpenAIProvider()
    assert not hasattr(provider, "generate_sql_from_prompt")
    assert not hasattr(provider, "generate_sql_for_step")
    assert not hasattr(provider, "format_answer_from_data")


def test_intent_prompt_has_tools_without_database_schema():
    captured = {}

    def capture(**kwargs):
        captured["prompt"] = kwargs["messages"][0]["content"]
        response = MagicMock()
        response.choices = [
            MagicMock(
                message=MagicMock(
                    content=(
                        '{"intent":"count","needs_clarification":false,'
                        '"requires_data_retrieval":true,'
                        '"data_tool_calls":[{"tool":"employee_count","arguments":{}}]}'
                    )
                )
            )
        ]
        return response

    with patch(
        "app.modules.copilot.infrastructure.providers.chat_completions_create",
        side_effect=capture,
    ):
        OpenAIProvider().analyze_intent_and_plan("Compte les salariés", [], "")

    prompt = captured["prompt"]
    assert "employee_count" in prompt
    assert "via SQL" not in prompt
    assert "Schéma de la base de données" not in prompt
    assert "CREATE TABLE" not in prompt
    assert "AAAA-JJ-MM" not in prompt
    assert '"date_start": "AAAA-MM-JJ"' in prompt
