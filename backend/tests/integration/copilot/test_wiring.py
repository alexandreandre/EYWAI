"""
Tests de câblage (injection de dépendances et flux bout en bout) du module copilot.

Vérifie que les routes sont enregistrées, que get_current_user est bien injecté,
et que le flux HTTP -> router -> commands -> (service mocké) fonctionne.
"""

from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.core.security import get_current_user


pytestmark = pytest.mark.integration


@pytest.fixture
def fake_user():
    u = MagicMock()
    u.id = "wiring-test-user-id"
    return u


@pytest.fixture
def app_with_copilot_user(fake_user):
    """Surcharge get_current_user pour les tests de wiring."""
    from app.main import app

    app.dependency_overrides[get_current_user] = lambda: fake_user
    try:
        yield app
    finally:
        app.dependency_overrides.pop(get_current_user, None)


class TestCopilotRoutesRegistered:
    """Vérifie que les routes du module copilot sont montées sur l'app."""

    def test_copilot_query_route_exists_returns_401_without_auth(
        self, client: TestClient
    ):
        """POST /api/copilot/query existe (401 sans token, pas 404)."""
        response = client.post("/api/copilot/query", json={"prompt": "test"})
        assert response.status_code == 401

    def test_copilot_query_agent_route_exists_returns_401_without_auth(
        self, client: TestClient
    ):
        """POST /api/copilot/query-agent existe (401 sans token, pas 404)."""
        response = client.post(
            "/api/copilot/query-agent",
            json={"prompt": "test", "conversation_history": []},
        )
        assert response.status_code == 401


class TestCopilotDependencyInjection:
    """Vérifie que l'utilisateur authentifié est bien injecté dans les commandes."""

    @patch("app.modules.copilot.api.router.commands.execute_text_to_sql")
    def test_handle_query_receives_user_id_from_get_current_user(
        self, mock_execute, client: TestClient, app_with_copilot_user, fake_user
    ):
        """Le router appelle la commande avec le user_id issu de get_current_user."""
        mock_execute.return_value = MagicMock(
            answer="Réponse",
            sql_query="SELECT 1",
            data=None,
        )
        test_client = TestClient(app_with_copilot_user)
        response = test_client.post(
            "/api/copilot/query",
            json={"prompt": "Combien d'employés ?"},
        )
        assert response.status_code == 200
        call_args = mock_execute.call_args[0][0]
        assert call_args.user_id == fake_user.id
        assert call_args.user_id == "wiring-test-user-id"

    @patch("app.modules.copilot.api.router.commands.handle_agent_query")
    def test_handle_agent_query_receives_user_id_and_history(
        self, mock_handle, client: TestClient, app_with_copilot_user, fake_user
    ):
        """Le router agent appelle la commande avec user_id et conversation_history mappés."""
        mock_handle.return_value = MagicMock(
            answer="Réponse agent",
            needs_clarification=False,
            clarification_question=None,
            sql_queries=None,
            data=None,
            thought_process="Plan...",
        )
        test_client = TestClient(app_with_copilot_user)
        response = test_client.post(
            "/api/copilot/query-agent",
            json={
                "prompt": "Combien d'employés ?",
                "conversation_history": [
                    {"role": "user", "content": "Combien d'employés ?"},
                    {"role": "assistant", "content": "Je cherche..."},
                ],
            },
        )
        assert response.status_code == 200
        call_input = mock_handle.call_args[0][0]
        assert call_input.user_id == fake_user.id
        assert len(call_input.conversation_history) == 2
        assert call_input.conversation_history[0].role == "user"
        assert call_input.conversation_history[1].role == "assistant"


class TestCopilotEndToEndFlow:
    """Flux bout en bout : HTTP -> router -> commande (mockée) -> réponse HTTP."""

    @patch("app.modules.copilot.api.router.commands.execute_text_to_sql")
    def test_text_to_sql_e2e_response_shape(
        self, mock_execute, client: TestClient, app_with_copilot_user
    ):
        """Réponse QueryResponse contient answer, sql_query, data."""
        mock_execute.return_value = MagicMock(
            answer="Il y a 3 employés.",
            sql_query="SELECT COUNT(*) FROM employees",
            data=[{"count": 3}],
        )
        test_client = TestClient(app_with_copilot_user)
        response = test_client.post(
            "/api/copilot/query",
            json={"prompt": "Combien d'employés ?"},
        )
        assert response.status_code == 200
        body = response.json()
        assert "answer" in body
        assert "sql_query" in body
        assert "data" in body
        assert body["answer"] == "Il y a 3 employés."
        assert body["sql_query"] == "SELECT COUNT(*) FROM employees"
        assert body["data"] == [{"count": 3}]

    @patch("app.modules.copilot.api.router.commands.handle_agent_query")
    def test_agent_e2e_response_shape(
        self, mock_handle, client: TestClient, app_with_copilot_user
    ):
        """Réponse AgentResponse contient answer, needs_clarification, thought_process, etc."""
        mock_handle.return_value = MagicMock(
            answer="Votre entreprise compte 3 employés.",
            needs_clarification=False,
            clarification_question=None,
            sql_queries=["SELECT COUNT(*) FROM employees"],
            data=[[{"count": 3}]],
            thought_process="Plan: count employees",
        )
        test_client = TestClient(app_with_copilot_user)
        response = test_client.post(
            "/api/copilot/query-agent",
            json={"prompt": "Combien d'employés ?", "conversation_history": []},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["answer"] == "Votre entreprise compte 3 employés."
        assert body["needs_clarification"] is False
        assert body["thought_process"] == "Plan: count employees"
        assert body["sql_queries"] == ["SELECT COUNT(*) FROM employees"]
