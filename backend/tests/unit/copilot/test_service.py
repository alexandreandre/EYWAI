"""
Tests du service applicatif du module copilot (application/service.py).

Dépendances mockées : OpenAI provider, SQL executor, user company resolver,
employee search, collective agreement provider. Pas d'appel réel à OpenAI ni DB.
"""

from unittest.mock import patch, MagicMock

import pytest

from app.modules.copilot.application.dto import AgentMessageDto
from app.modules.copilot.application.service import (
    generate_sql_from_prompt,
    format_answer_from_data,
    execute_sql_query,
    get_company_id_for_user,
    fuzzy_search_employee,
    get_company_collective_agreements,
    analyze_intent_and_plan,
    execute_retrieval_step,
    answer_collective_agreement_question,
    synthesize_final_answer,
)


pytestmark = pytest.mark.unit


class TestGenerateSqlFromPrompt:
    @patch("app.modules.copilot.application.service.get_openai_provider")
    def test_delegates_to_provider_and_returns_sql(self, mock_get_provider):
        mock_provider = MagicMock()
        mock_provider.generate_sql_from_prompt.return_value = "SELECT 1"
        mock_get_provider.return_value = mock_provider

        result = generate_sql_from_prompt("Combien d'employés ?")

        assert result == "SELECT 1"
        mock_provider.generate_sql_from_prompt.assert_called_once()
        call_args = mock_provider.generate_sql_from_prompt.call_args
        assert call_args[0][0] == "Combien d'employés ?"


class TestFormatAnswerFromData:
    @patch("app.modules.copilot.application.service.get_openai_provider")
    def test_delegates_to_provider_and_returns_formatted_answer(
        self, mock_get_provider
    ):
        mock_provider = MagicMock()
        mock_provider.format_answer_from_data.return_value = "Il y a 5 employés."
        mock_get_provider.return_value = mock_provider

        result = format_answer_from_data(
            "Combien d'employés ?", [{"count": 5}], "SELECT COUNT(*) FROM employees"
        )

        assert result == "Il y a 5 employés."
        mock_provider.format_answer_from_data.assert_called_once_with(
            "Combien d'employés ?", [{"count": 5}], "SELECT COUNT(*) FROM employees"
        )


class TestExecuteSqlQuery:
    @patch("app.modules.copilot.application.service.get_sql_executor")
    def test_delegates_to_executor_and_returns_data(self, mock_get_executor):
        mock_executor = MagicMock()
        mock_executor.execute_read_only.return_value = [{"id": "1", "name": "Test"}]
        mock_get_executor.return_value = mock_executor

        result = execute_sql_query("SELECT * FROM employees LIMIT 1")

        assert result == [{"id": "1", "name": "Test"}]
        mock_executor.execute_read_only.assert_called_once_with(
            "SELECT * FROM employees LIMIT 1"
        )


class TestGetCompanyIdForUser:
    @patch("app.modules.copilot.application.service.get_user_company_resolver")
    def test_delegates_to_resolver_and_returns_company_id(self, mock_get_resolver):
        mock_resolver = MagicMock()
        mock_resolver.get_company_id_for_user.return_value = "company-123"
        mock_get_resolver.return_value = mock_resolver

        result = get_company_id_for_user("user-456")

        assert result == "company-123"
        mock_resolver.get_company_id_for_user.assert_called_once_with("user-456")


class TestFuzzySearchEmployee:
    @patch("app.modules.copilot.application.service.get_employee_search_provider")
    def test_delegates_to_provider_and_returns_matches(self, mock_get_provider):
        mock_provider = MagicMock()
        mock_provider.fuzzy_search_by_name.return_value = [
            {
                "employee": {"id": "e1", "first_name": "Jean", "last_name": "Dupont"},
                "similarity": 0.9,
            }
        ]
        mock_get_provider.return_value = mock_provider

        result = fuzzy_search_employee("Jean Dupont", threshold=0.6)

        assert len(result) == 1
        assert result[0]["employee"]["first_name"] == "Jean"
        mock_provider.fuzzy_search_by_name.assert_called_once_with("Jean Dupont", 0.6)


class TestGetCompanyCollectiveAgreements:
    @patch("app.modules.copilot.application.service.get_collective_agreement_provider")
    def test_delegates_to_provider_and_returns_agreements(self, mock_get_provider):
        mock_provider = MagicMock()
        mock_provider.get_company_agreements.return_value = [
            {"id": "cc-1", "name": "SYNTEC", "idcc": "1486"}
        ]
        mock_get_provider.return_value = mock_provider

        result = get_company_collective_agreements("company-123")

        assert len(result) == 1
        assert result[0]["name"] == "SYNTEC"
        mock_provider.get_company_agreements.assert_called_once_with("company-123")


class TestAnalyzeIntentAndPlan:
    @patch("app.modules.copilot.application.service.get_openai_provider")
    def test_delegates_to_provider_and_returns_plan(self, mock_get_provider):
        mock_provider = MagicMock()
        mock_provider.analyze_intent_and_plan.return_value = {
            "intent": "count_employees",
            "needs_clarification": False,
            "requires_data_retrieval": True,
            "data_retrieval_steps": ["Compter les employés"],
        }
        mock_get_provider.return_value = mock_provider
        history = [AgentMessageDto(role="user", content="Combien d'employés ?")]

        result = analyze_intent_and_plan("Combien d'employés ?", history, [])

        assert result["intent"] == "count_employees"
        assert result["requires_data_retrieval"] is True
        mock_provider.analyze_intent_and_plan.assert_called_once()
        call_args = mock_provider.analyze_intent_and_plan.call_args
        assert call_args[0][0] == "Combien d'employés ?"
        assert call_args[0][1] == [{"role": "user", "content": "Combien d'employés ?"}]


class TestExecuteRetrievalStep:
    @patch("app.modules.copilot.application.service.get_sql_executor")
    @patch("app.modules.copilot.application.service.get_openai_provider")
    def test_select_query_executes_and_returns_data(
        self, mock_get_openai, mock_get_executor
    ):
        mock_openai = MagicMock()
        mock_openai.generate_sql_for_step.return_value = (
            "SELECT COUNT(*) FROM employees"
        )
        mock_get_openai.return_value = mock_openai
        mock_executor = MagicMock()
        mock_executor.execute_read_only.return_value = [{"count": 10}]
        mock_get_executor.return_value = mock_executor

        result = execute_retrieval_step("Compter les employés", {})

        assert result["success"] is True
        assert result["sql"] == "SELECT COUNT(*) FROM employees"
        assert result["data"] == [{"count": 10}]

    @patch("app.modules.copilot.application.service.get_openai_provider")
    def test_non_select_returns_error_dict(self, mock_get_openai):
        mock_openai = MagicMock()
        mock_openai.generate_sql_for_step.return_value = "DELETE FROM employees"
        mock_get_openai.return_value = mock_openai

        result = execute_retrieval_step("Supprimer", {})

        assert result["success"] is False
        assert "error" in result


class TestAnswerCollectiveAgreementQuestion:
    @patch("app.modules.copilot.application.service.get_openai_provider")
    def test_delegates_to_provider_and_returns_answer(self, mock_get_provider):
        mock_provider = MagicMock()
        mock_provider.answer_collective_agreement_question.return_value = (
            "25 jours ouvrés."
        )
        mock_get_provider.return_value = mock_provider
        agreement = {"name": "SYNTEC", "idcc": "1486", "full_text": "Article 1..."}
        plan = {"intent": "conges"}

        result = answer_collective_agreement_question("Congés payés ?", agreement, plan)

        assert result == "25 jours ouvrés."
        mock_provider.answer_collective_agreement_question.assert_called_once_with(
            "Congés payés ?", agreement, plan
        )


class TestSynthesizeFinalAnswer:
    @patch("app.modules.copilot.application.service.get_openai_provider")
    def test_delegates_to_provider_and_returns_synthesis(self, mock_get_provider):
        mock_provider = MagicMock()
        mock_provider.synthesize_final_answer.return_value = (
            "Votre entreprise compte 10 employés."
        )
        mock_get_provider.return_value = mock_provider
        plan = {"intent": "count"}
        retrieval_results = [
            {"success": True, "sql": "SELECT COUNT(*)", "data": [{"count": 10}]}
        ]

        result = synthesize_final_answer(
            "Combien d'employés ?", plan, retrieval_results
        )

        assert result == "Votre entreprise compte 10 employés."
        mock_provider.synthesize_final_answer.assert_called_once()
        call_args = mock_provider.synthesize_final_answer.call_args
        assert call_args[0][0] == "Combien d'employés ?"
        assert call_args[0][2] == retrieval_results
