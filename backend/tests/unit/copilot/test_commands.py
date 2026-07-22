"""
Tests des commandes du module copilot (application/commands.py).

Repositories et service mockés : pas d'appel réel à OpenRouter ni à la DB.
"""

import os
from unittest.mock import patch

import pytest

from app.modules.copilot.application.commands import (
    execute_text_to_sql,
    handle_agent_query,
)
from app.modules.copilot.application.dto import (
    AgentQueryInput,
    TextToSqlInput,
    TextToSqlResult,
)


pytestmark = pytest.mark.unit


class TestExecuteTextToSql:
    """Commande execute_text_to_sql : Text-to-SQL avec vérification SELECT."""

    def test_raises_when_openrouter_key_missing(self):
        with patch.dict(os.environ, {}, clear=False):
            if "OPENROUTER_API_KEY" in os.environ:
                del os.environ["OPENROUTER_API_KEY"]
            with pytest.raises(ValueError, match="clé API manquante|pas configuré|OPENROUTER"):
                execute_text_to_sql(
                    TextToSqlInput(prompt="Combien d'employés ?", user_id="user-1")
                )

    @patch("app.modules.copilot.application.commands.get_company_id_for_user")
    @patch("app.modules.copilot.application.commands.generate_sql_from_prompt")
    @patch("app.modules.copilot.application.commands.only_select_allowed")
    @patch("app.modules.copilot.application.commands.execute_sql_query")
    @patch("app.modules.copilot.application.commands.format_answer_from_data")
    def test_success_returns_result(
        self, mock_format, mock_execute, mock_only_select, mock_generate, mock_company
    ):
        os.environ["OPENROUTER_API_KEY"] = "sk-or-test"
        mock_company.return_value = "company-123"
        mock_generate.return_value = "SELECT COUNT(*) FROM employees"
        mock_only_select.return_value = True
        mock_execute.return_value = [{"count": 5}]
        mock_format.return_value = "Il y a 5 employés."

        result = execute_text_to_sql(
            TextToSqlInput(prompt="Combien d'employés ?", user_id="user-1")
        )

        assert isinstance(result, TextToSqlResult)
        assert result.answer == "Il y a 5 employés."
        assert result.sql_query == "SELECT COUNT(*) FROM employees"
        assert result.data == [{"count": 5}]
        # Le company_id résolu est injecté dans la génération SQL.
        mock_generate.assert_called_once_with("Combien d'employés ?", "company-123")
        mock_only_select.assert_called_once()
        mock_execute.assert_called_once()
        mock_format.assert_called_once()

    @patch("app.modules.copilot.application.commands.get_company_id_for_user")
    @patch("app.modules.copilot.application.commands.generate_sql_from_prompt")
    @patch("app.modules.copilot.application.commands.only_select_allowed")
    def test_active_company_id_used_over_profile_for_text_to_sql(
        self, mock_only_select, mock_generate, mock_company
    ):
        # Si une entreprise active est fournie, on ne lit pas le profil.
        os.environ["OPENROUTER_API_KEY"] = "sk-or-test"
        mock_generate.return_value = "SELECT COUNT(*) FROM employees"
        mock_only_select.return_value = False  # court-circuite avant exécution

        with pytest.raises(PermissionError):
            execute_text_to_sql(
                TextToSqlInput(
                    prompt="Combien d'employés ?",
                    user_id="user-1",
                    active_company_id="company-active",
                )
            )

        mock_company.assert_not_called()
        mock_generate.assert_called_once_with("Combien d'employés ?", "company-active")

    @patch("app.modules.copilot.application.commands.get_company_id_for_user")
    @patch("app.modules.copilot.application.commands.generate_sql_from_prompt")
    @patch("app.modules.copilot.application.commands.only_select_allowed")
    def test_non_select_raises_permission_error(
        self, mock_only_select, mock_generate, mock_company
    ):
        os.environ["OPENROUTER_API_KEY"] = "sk-or-test"
        mock_company.return_value = "company-123"
        mock_generate.return_value = "DELETE FROM employees"
        mock_only_select.return_value = False

        with pytest.raises(PermissionError, match="non autorisée|SELECT"):
            execute_text_to_sql(
                TextToSqlInput(prompt="Supprime tout", user_id="user-1")
            )


class TestHandleAgentQuery:
    """Commande handle_agent_query : agent avec intent, clarification, conventions, données."""

    def test_raises_when_openrouter_key_missing(self):
        with patch.dict(os.environ, {}, clear=False):
            if "OPENROUTER_API_KEY" in os.environ:
                del os.environ["OPENROUTER_API_KEY"]
            with pytest.raises(ValueError, match="pas configuré|OPENROUTER"):
                handle_agent_query(
                    AgentQueryInput(
                        prompt="Combien d'employés ?",
                        conversation_history=[],
                        user_id="user-1",
                    )
                )

    @patch("app.modules.copilot.application.commands.analyze_intent_and_plan")
    @patch("app.modules.copilot.application.commands.get_company_collective_agreements")
    @patch("app.modules.copilot.application.commands.get_company_id_for_user")
    def test_raises_lookup_error_when_no_company_for_data_question(
        self, mock_get_company, mock_get_agreements, mock_analyze
    ):
        # Ni entreprise active, ni company_id de profil : une question de données
        # nécessite une entreprise → LookupError.
        mock_get_company.return_value = None
        mock_get_agreements.return_value = []
        mock_analyze.return_value = {
            "needs_clarification": False,
            "requires_app_help": False,
            "requires_collective_agreement": False,
            "requires_data_retrieval": True,
            "data_retrieval_steps": ["Compter les employés"],
        }
        os.environ["OPENROUTER_API_KEY"] = "sk-or-test"

        with pytest.raises(LookupError, match="Company ID non trouvé"):
            handle_agent_query(
                AgentQueryInput(
                    prompt="Combien d'employés ?",
                    conversation_history=[],
                    user_id="user-1",
                    active_company_id=None,
                )
            )

    @patch("app.modules.copilot.application.commands.answer_app_usage_question")
    @patch("app.modules.copilot.application.commands.analyze_intent_and_plan")
    @patch("app.modules.copilot.application.commands.get_company_collective_agreements")
    @patch("app.modules.copilot.application.commands.get_company_id_for_user")
    def test_app_help_works_without_company(
        self, mock_get_company, mock_get_agreements, mock_analyze, mock_app_help
    ):
        # L'aide à l'utilisation du logiciel ne dépend pas de l'entreprise.
        mock_get_company.return_value = None
        mock_get_agreements.return_value = []
        mock_analyze.return_value = {
            "needs_clarification": False,
            "requires_app_help": True,
        }
        mock_app_help.return_value = "Menu latéral → EYWAI Paie → Lancer la paie."
        os.environ["OPENROUTER_API_KEY"] = "sk-or-test"

        result = handle_agent_query(
            AgentQueryInput(
                prompt="Comment lancer la paie ?",
                conversation_history=[],
                user_id="user-1",
                active_company_id=None,
            )
        )

        assert "EYWAI Paie" in result.answer
        mock_app_help.assert_called_once()

    @patch("app.modules.copilot.application.commands.synthesize_final_answer")
    @patch("app.modules.copilot.application.commands.execute_retrieval_step")
    @patch("app.modules.copilot.application.commands.get_company_collective_agreements")
    @patch("app.modules.copilot.application.commands.get_company_id_for_user")
    @patch("app.modules.copilot.application.commands.analyze_intent_and_plan")
    def test_active_company_id_used_over_profile_lookup(
        self,
        mock_analyze,
        mock_get_company,
        mock_get_agreements,
        mock_retrieval,
        mock_synthesize,
    ):
        # Si une entreprise active est fournie, on ne lit pas le profil.
        mock_get_agreements.return_value = []
        mock_analyze.return_value = {
            "needs_clarification": False,
            "requires_data_retrieval": True,
            "data_retrieval_steps": ["Compter les employés"],
        }
        mock_retrieval.return_value = {
            "success": True,
            "sql": "SELECT COUNT(*) FROM employees",
            "data": [{"count": 3}],
        }
        mock_synthesize.return_value = "3 employés."
        os.environ["OPENROUTER_API_KEY"] = "sk-or-test"

        result = handle_agent_query(
            AgentQueryInput(
                prompt="Combien d'employés ?",
                conversation_history=[],
                user_id="user-1",
                active_company_id="company-active",
            )
        )

        assert result.answer == "3 employés."
        mock_get_company.assert_not_called()
        mock_get_agreements.assert_called_once_with("company-active")

    @patch("app.modules.copilot.application.commands.get_company_collective_agreements")
    @patch("app.modules.copilot.application.commands.get_company_id_for_user")
    @patch("app.modules.copilot.application.commands.analyze_intent_and_plan")
    def test_needs_clarification_returns_result(
        self, mock_analyze, mock_get_company, mock_get_agreements
    ):
        os.environ["OPENROUTER_API_KEY"] = "sk-or-test"
        mock_get_company.return_value = "company-123"
        mock_get_agreements.return_value = []
        mock_analyze.return_value = {
            "needs_clarification": True,
            "clarification_question": "Voulez-vous compter tous les employés ou seulement les CDI ?",
        }

        result = handle_agent_query(
            AgentQueryInput(
                prompt="Combien d'employés ?",
                conversation_history=[],
                user_id="user-1",
            )
        )

        assert result.needs_clarification is True
        assert (
            result.clarification_question
            == "Voulez-vous compter tous les employés ou seulement les CDI ?"
        )
        assert result.answer == ""

    @patch("app.modules.copilot.application.commands.answer_app_usage_question")
    @patch("app.modules.copilot.application.commands.get_company_collective_agreements")
    @patch("app.modules.copilot.application.commands.get_company_id_for_user")
    @patch("app.modules.copilot.application.commands.analyze_intent_and_plan")
    def test_requires_app_help_returns_usage_answer(
        self, mock_analyze, mock_get_company, mock_get_agreements, mock_app_help
    ):
        os.environ["OPENROUTER_API_KEY"] = "sk-or-test"
        mock_get_company.return_value = "company-123"
        mock_get_agreements.return_value = []
        mock_analyze.return_value = {
            "needs_clarification": False,
            "requires_app_help": True,
            "requires_collective_agreement": False,
            "requires_data_retrieval": False,
        }
        mock_app_help.return_value = (
            "Pour lancer la paie : Menu latéral → EYWAI Paie → Lancer la paie."
        )

        result = handle_agent_query(
            AgentQueryInput(
                prompt="Comment lancer la paie ?",
                conversation_history=[],
                user_id="user-1",
            )
        )

        assert result.needs_clarification is False
        assert "EYWAI Paie" in result.answer
        mock_app_help.assert_called_once()

    @patch("app.modules.copilot.application.commands.synthesize_final_answer")
    @patch("app.modules.copilot.application.commands.execute_retrieval_step")
    @patch("app.modules.copilot.application.commands.get_company_collective_agreements")
    @patch("app.modules.copilot.application.commands.get_company_id_for_user")
    @patch("app.modules.copilot.application.commands.analyze_intent_and_plan")
    def test_data_retrieval_flow_returns_synthesized_answer(
        self,
        mock_analyze,
        mock_get_company,
        mock_get_agreements,
        mock_retrieval,
        mock_synthesize,
    ):
        os.environ["OPENROUTER_API_KEY"] = "sk-or-test"
        mock_get_company.return_value = "company-123"
        mock_get_agreements.return_value = []
        mock_analyze.return_value = {
            "needs_clarification": False,
            "requires_employee_search": False,
            "requires_collective_agreement": False,
            "requires_data_retrieval": True,
            "data_retrieval_steps": ["Compter les employés"],
        }
        mock_retrieval.return_value = {
            "success": True,
            "sql": "SELECT COUNT(*) FROM employees",
            "data": [{"count": 10}],
        }
        mock_synthesize.return_value = "Votre entreprise compte 10 employés."

        result = handle_agent_query(
            AgentQueryInput(
                prompt="Combien d'employés ?",
                conversation_history=[],
                user_id="user-1",
            )
        )

        assert result.needs_clarification is False
        assert result.answer == "Votre entreprise compte 10 employés."
        assert result.sql_queries == ["SELECT COUNT(*) FROM employees"]
        mock_synthesize.assert_called_once()
        # Le company_id doit être injecté dans le contexte de récupération SQL.
        context_arg = mock_retrieval.call_args[0][1]
        assert context_arg.get("company_id") == "company-123"

    @patch("app.modules.copilot.application.commands.synthesize_final_answer")
    @patch("app.modules.copilot.application.commands.execute_retrieval_step")
    @patch("app.modules.copilot.application.commands.fuzzy_search_employee")
    @patch("app.modules.copilot.application.commands.get_company_collective_agreements")
    @patch("app.modules.copilot.application.commands.get_company_id_for_user")
    @patch("app.modules.copilot.application.commands.analyze_intent_and_plan")
    def test_employee_search_is_scoped_to_active_company(
        self,
        mock_analyze,
        mock_get_company,
        mock_get_agreements,
        mock_fuzzy,
        mock_retrieval,
        mock_synthesize,
    ):
        os.environ["OPENROUTER_API_KEY"] = "sk-or-test"
        mock_get_company.return_value = "company-123"
        mock_get_agreements.return_value = []
        mock_analyze.return_value = {
            "needs_clarification": False,
            "requires_employee_search": True,
            "employee_query": "Jean Dupont",
            "requires_data_retrieval": True,
            "data_retrieval_steps": ["Récupérer le salaire"],
        }
        mock_fuzzy.return_value = [
            {
                "employee": {"id": "e1", "first_name": "Jean", "last_name": "Dupont"},
                "similarity": 0.99,
                "full_name": "Jean Dupont",
            }
        ]
        mock_retrieval.return_value = {"success": True, "sql": "SELECT 1", "data": [{}]}
        mock_synthesize.return_value = "Jean Dupont gagne 2500 €."

        handle_agent_query(
            AgentQueryInput(
                prompt="Combien gagne Jean Dupont ?",
                conversation_history=[],
                user_id="user-1",
            )
        )

        # La recherche floue est limitée à l'entreprise active.
        mock_fuzzy.assert_called_once_with("Jean Dupont", company_id="company-123")

    @patch("app.modules.copilot.application.commands.get_company_collective_agreements")
    @patch("app.modules.copilot.application.commands.get_company_id_for_user")
    @patch("app.modules.copilot.application.commands.analyze_intent_and_plan")
    def test_requires_collective_agreement_no_agreements_returns_message(
        self, mock_analyze, mock_get_company, mock_get_agreements
    ):
        os.environ["OPENROUTER_API_KEY"] = "sk-or-test"
        mock_get_company.return_value = "company-123"
        mock_get_agreements.return_value = []
        mock_analyze.return_value = {
            "needs_clarification": False,
            "requires_collective_agreement": True,
        }

        result = handle_agent_query(
            AgentQueryInput(
                prompt="Combien de jours de congés payés ?",
                conversation_history=[],
                user_id="user-1",
            )
        )

        assert (
            "aucune convention collective" in result.answer.lower()
            or "n'a aucune convention" in result.answer
        )

    @patch(
        "app.modules.copilot.application.commands.answer_collective_agreement_question"
    )
    @patch("app.modules.copilot.application.commands.get_company_collective_agreements")
    @patch("app.modules.copilot.application.commands.get_company_id_for_user")
    @patch("app.modules.copilot.application.commands.analyze_intent_and_plan")
    def test_requires_collective_agreement_single_agreement_calls_answer(
        self, mock_analyze, mock_get_company, mock_get_agreements, mock_answer
    ):
        os.environ["OPENROUTER_API_KEY"] = "sk-or-test"
        mock_get_company.return_value = "company-123"
        mock_get_agreements.return_value = [
            {
                "id": "cc-1",
                "name": "SYNTEC",
                "idcc": "1486",
                "full_text": "Article 1...",
            }
        ]
        mock_analyze.return_value = {
            "needs_clarification": False,
            "requires_collective_agreement": True,
        }
        mock_answer.return_value = "La convention prévoit 25 jours ouvrés."

        result = handle_agent_query(
            AgentQueryInput(
                prompt="Combien de jours de congés payés ?",
                conversation_history=[],
                user_id="user-1",
            )
        )

        assert result.answer == "La convention prévoit 25 jours ouvrés."
        mock_answer.assert_called_once()

    @patch("app.modules.copilot.application.commands.fuzzy_search_employee")
    @patch("app.modules.copilot.application.commands.get_company_collective_agreements")
    @patch("app.modules.copilot.application.commands.get_company_id_for_user")
    @patch("app.modules.copilot.application.commands.analyze_intent_and_plan")
    def test_employee_search_no_match_returns_clarification_message(
        self, mock_analyze, mock_get_company, mock_get_agreements, mock_fuzzy
    ):
        os.environ["OPENROUTER_API_KEY"] = "sk-or-test"
        mock_get_company.return_value = "company-123"
        mock_get_agreements.return_value = []
        mock_analyze.return_value = {
            "needs_clarification": False,
            "requires_employee_search": True,
            "employee_query": "Jean Dupont",
            "requires_data_retrieval": False,
        }
        mock_fuzzy.return_value = []

        result = handle_agent_query(
            AgentQueryInput(
                prompt="Combien gagne Jean Dupont ?",
                conversation_history=[],
                user_id="user-1",
            )
        )

        assert (
            "aucun employé" in result.answer.lower()
            or "n'ai trouvé aucun" in result.answer
        )
