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
    execute_tool_calls,
    answer_app_usage_question,
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

        result = generate_sql_from_prompt("Combien d'employés ?", "company-123")

        assert result == "SELECT 1"
        mock_provider.generate_sql_from_prompt.assert_called_once()
        call_args = mock_provider.generate_sql_from_prompt.call_args
        assert call_args[0][0] == "Combien d'employés ?"
        # Le company_id de l'entreprise active est transmis au provider (3e arg).
        assert call_args[0][2] == "company-123"


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

        result = fuzzy_search_employee(
            "Jean Dupont", threshold=0.6, company_id="company-123"
        )

        assert len(result) == 1
        assert result[0]["employee"]["first_name"] == "Jean"
        mock_provider.fuzzy_search_by_name.assert_called_once_with(
            "Jean Dupont", 0.6, "company-123"
        )


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


class TestExecuteToolCalls:
    """Dispatch fermé au niveau service : le company_id serveur est toujours imposé."""

    @patch("app.modules.copilot.application.service.execute_tool")
    def test_parses_and_dispatches_with_server_company(self, mock_execute_tool):
        mock_execute_tool.return_value = {"count": 5}

        results = execute_tool_calls(
            [{"tool": "employee_count", "arguments": {"employment_status": "actif"}}],
            company_id="c1",
        )

        assert len(results) == 1
        assert results[0]["success"] is True
        assert results[0]["data"] == {"count": 5}
        assert results[0]["tool"] == "employee_count"
        # Le company_id transmis à execute_tool est celui du serveur (2e arg).
        call_args = mock_execute_tool.call_args
        assert call_args[0][1] == "c1"

    @patch("app.modules.copilot.application.service.execute_tool")
    def test_empty_or_none_returns_no_results(self, mock_execute_tool):
        assert execute_tool_calls(None, company_id="c1") == []
        assert execute_tool_calls([], company_id="c1") == []
        mock_execute_tool.assert_not_called()

    @patch("app.modules.copilot.application.service.execute_tool")
    def test_llm_supplied_company_id_is_rejected(self, mock_execute_tool):
        # Un company_id fourni par le LLM fait échouer le parsing : aucune requête
        # n'est exécutée et un marqueur d'erreur est renvoyé (fail-closed).
        results = execute_tool_calls(
            [{"tool": "employee_count", "arguments": {"company_id": "autre"}}],
            company_id="c1",
        )
        mock_execute_tool.assert_not_called()
        assert len(results) == 1
        assert results[0]["success"] is False
        assert "error" in results[0]

    @patch("app.modules.copilot.application.service.execute_tool")
    def test_tool_error_is_captured_per_call(self, mock_execute_tool):
        mock_execute_tool.side_effect = RuntimeError("boom")
        results = execute_tool_calls(
            [{"tool": "employee_count", "arguments": {}}], company_id="c1"
        )
        assert results[0]["success"] is False
        assert "boom" in results[0]["error"]


class TestProviderPlanSchema:
    """La planification LLM expose des appels d'outils typés, jamais de SQL brut."""

    def test_failure_returns_fail_closed_marker(self):
        from app.modules.copilot.infrastructure.providers import OpenAIProvider

        with patch(
            "app.modules.copilot.infrastructure.providers.chat_completions_create",
            side_effect=RuntimeError("llm down"),
        ):
            plan = OpenAIProvider().analyze_intent_and_plan("Combien d'employés ?", [], "")

        assert plan["requires_data_retrieval"] is False
        assert plan.get("error")
        assert plan.get("data_tool_calls") == []
        # Aucun repli vers une requête SQL générique.
        assert "data_retrieval_steps" not in plan

    def test_valid_plan_surfaces_tool_calls(self):
        response = MagicMock()
        response.choices = [
            MagicMock(
                message=MagicMock(
                    content=(
                        '{"intent": "count", "needs_clarification": false, '
                        '"requires_data_retrieval": true, '
                        '"data_tool_calls": [{"tool": "employee_count", '
                        '"arguments": {"employment_status": "actif"}}]}'
                    )
                )
            )
        ]
        with patch(
            "app.modules.copilot.infrastructure.providers.chat_completions_create",
            return_value=response,
        ):
            plan = OpenAIProviderImport().analyze_intent_and_plan(
                "Combien d'actifs ?", [], ""
            )
        assert plan["data_tool_calls"][0]["tool"] == "employee_count"

    def test_system_prompt_lists_tools_and_forbids_sql(self):
        captured = {}

        def _capture(*args, **kwargs):
            captured["messages"] = kwargs.get("messages")
            raise RuntimeError("stop after capture")

        with patch(
            "app.modules.copilot.infrastructure.providers.chat_completions_create",
            side_effect=_capture,
        ):
            OpenAIProviderImport().analyze_intent_and_plan("x", [], "")

        system_prompt = captured["messages"][0]["content"]
        for tool_name in (
            "employee_count",
            "employee_search",
            "payroll_summary",
            "absence_summary",
            "planning_summary",
            "hr_indicators",
        ):
            assert tool_name in system_prompt
        assert "data_tool_calls" in system_prompt


def OpenAIProviderImport():
    from app.modules.copilot.infrastructure.providers import OpenAIProvider

    return OpenAIProvider()


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


class TestAnswerAppUsageQuestion:
    @patch("app.modules.copilot.application.service.get_openai_provider")
    def test_delegates_to_provider_with_guide(self, mock_get_provider):
        mock_provider = MagicMock()
        mock_provider.answer_app_usage_question.return_value = (
            "Menu latéral → EYWAI Paie → Lancer la paie."
        )
        mock_get_provider.return_value = mock_provider
        history = [AgentMessageDto(role="user", content="Comment lancer la paie ?")]

        result = answer_app_usage_question("Comment lancer la paie ?", history)

        assert result == "Menu latéral → EYWAI Paie → Lancer la paie."
        mock_provider.answer_app_usage_question.assert_called_once()
        call_args = mock_provider.answer_app_usage_question.call_args
        assert call_args[0][0] == "Comment lancer la paie ?"
        assert call_args[0][1] == [
            {"role": "user", "content": "Comment lancer la paie ?"}
        ]
        # Le guide produit est transmis en 3e argument et n'est pas vide.
        assert isinstance(call_args[0][2], str) and call_args[0][2]


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
