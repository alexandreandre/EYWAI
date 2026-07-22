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
    for unsupported_example in (
        "Combien gagne Jean",
        "Prêts employeur en cours",
        "Acomptes sur prime en attente",
        "IJSS non rapprochées ce mois",
        "Salariés proches du contingent HS",
        "Mouvements CET en attente de validation",
        "HS badgeuse en attente de validation",
        "Bulletins participation en attente de réponse",
        "Titres de séjour expirant ce mois",
        "Crédits repos compensateurs du trimestre",
        "Jours de fractionnement CP accordés",
        "Salariés payés par chèque",
        "Avances avec dérogation au plafond net",
        "Jours CP ancienneté accordés cette année",
    ):
        assert unsupported_example not in prompt


def test_synthesis_sanitizes_internal_identifiers_before_provider_call():
    captured = {}

    def capture(**kwargs):
        captured["prompt"] = kwargs["messages"][0]["content"]
        response = MagicMock()
        response.choices = [
            MagicMock(message=MagicMock(content="Jean Dupont est actif."))
        ]
        return response

    retrieval_results = [
        {
            "tool": "employee_search",
            "success": True,
            "data": {
                "employees": [
                    {
                        "id": "employee-secret-id",
                        "employee_id": "employee-secret-id",
                        "company_id": "company-secret-id",
                        "first_name": "Jean",
                        "last_name": "Dupont",
                    }
                ]
            },
        }
    ]

    with patch(
        "app.modules.copilot.infrastructure.providers.chat_completions_create",
        side_effect=capture,
    ):
        answer = OpenAIProvider().synthesize_final_answer(
            "Qui est Jean Dupont ?",
            {"intent": "employee_search"},
            retrieval_results,
        )

    assert answer == "Jean Dupont est actif."
    assert "Jean" in captured["prompt"]
    assert "employee-secret-id" not in captured["prompt"]
    assert "company-secret-id" not in captured["prompt"]
