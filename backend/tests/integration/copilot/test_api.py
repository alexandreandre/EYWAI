"""
Tests HTTP des routes du module copilot.

Routes testées :
- POST /api/copilot/query (Text-to-SQL)
- POST /api/copilot/query-agent (Agent)

Utilise client (TestClient), dependency_overrides pour get_current_user (utilisateur de test),
et mocks des commandes pour éviter OpenAI et DB réelles. Pour des tests E2E avec token réel,
ajouter dans conftest.py la fixture copilot_headers (voir commentaire en fin de conftest).
"""

from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.core.security import get_current_user


pytestmark = pytest.mark.integration


@pytest.fixture
def fake_user():
    """Utilisateur minimal pour les routes copilot (contract: .id utilisé par les commandes)."""
    u = MagicMock()
    u.id = "test-user-id-copilot"
    return u


@pytest.fixture
def client_with_copilot_user(client: TestClient, fake_user):
    """Client avec get_current_user surchargé pour retourner fake_user."""
    from app.main import app

    app.dependency_overrides[get_current_user] = lambda: fake_user
    try:
        yield client
    finally:
        app.dependency_overrides.pop(get_current_user, None)


class TestCopilotQuery:
    """POST /api/copilot/query — Text-to-SQL."""

    def test_query_without_auth_returns_401(self, client: TestClient):
        """Sans token → 401."""
        response = client.post(
            "/api/copilot/query", json={"prompt": "Combien d'employés ?"}
        )
        assert response.status_code == 401

    @patch("app.modules.copilot.api.router.commands.execute_text_to_sql")
    def test_query_with_auth_returns_200_and_response_body(
        self, mock_execute, client_with_copilot_user: TestClient
    ):
        """Avec auth (override) et commande mockée → 200, answer + sql_query + data."""
        mock_execute.return_value = MagicMock(
            answer="Il y a 5 employés.",
            sql_query="SELECT COUNT(*) FROM employees",
            data=[{"count": 5}],
        )
        response = client_with_copilot_user.post(
            "/api/copilot/query",
            json={"prompt": "Combien d'employés ?"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["answer"] == "Il y a 5 employés."
        assert data["sql_query"] == "SELECT COUNT(*) FROM employees"
        assert data["data"] == [{"count": 5}]
        mock_execute.assert_called_once()
        call_input = mock_execute.call_args[0][0]
        assert call_input.prompt == "Combien d'employés ?"
        assert call_input.user_id == "test-user-id-copilot"

    @patch("app.modules.copilot.api.router.commands.execute_text_to_sql")
    def test_query_value_error_returns_500(
        self, mock_execute, client_with_copilot_user: TestClient
    ):
        """ValueError (ex: clé API manquante) → 500."""
        mock_execute.side_effect = ValueError("Le service Copilote n'est pas configuré")
        response = client_with_copilot_user.post(
            "/api/copilot/query",
            json={"prompt": "Combien d'employés ?"},
        )
        assert response.status_code == 500
        assert "Copilote" in response.json().get("detail", "")

    @patch("app.modules.copilot.api.router.commands.execute_text_to_sql")
    def test_query_permission_error_returns_403(
        self, mock_execute, client_with_copilot_user: TestClient
    ):
        """PermissionError (requête non SELECT) → 403."""
        mock_execute.side_effect = PermissionError(
            "Requête non autorisée. Seuls les SELECT sont permis."
        )
        response = client_with_copilot_user.post(
            "/api/copilot/query",
            json={"prompt": "Supprime tous les employés"},
        )
        assert response.status_code == 403
        assert "SELECT" in response.json().get("detail", "")

    def test_query_missing_prompt_returns_422(
        self, client_with_copilot_user: TestClient
    ):
        """Body sans 'prompt' → 422."""
        response = client_with_copilot_user.post("/api/copilot/query", json={})
        assert response.status_code == 422


class TestCopilotQueryAgent:
    """POST /api/copilot/query-agent — Agent."""

    def test_query_agent_without_auth_returns_401(self, client: TestClient):
        """Sans token → 401."""
        response = client.post(
            "/api/copilot/query-agent",
            json={"prompt": "Combien d'employés ?", "conversation_history": []},
        )
        assert response.status_code == 401

    @patch("app.modules.copilot.api.router.commands.handle_agent_query")
    def test_query_agent_with_auth_returns_200_and_response_body(
        self, mock_handle, client_with_copilot_user: TestClient
    ):
        """Avec auth (override) et commande mockée → 200, answer, needs_clarification, etc."""
        mock_handle.return_value = MagicMock(
            answer="Votre entreprise compte 10 employés.",
            needs_clarification=False,
            clarification_question=None,
            sql_queries=["SELECT COUNT(*) FROM employees"],
            data=[[{"count": 10}]],
            thought_process="Plan d'action: ...",
        )
        response = client_with_copilot_user.post(
            "/api/copilot/query-agent",
            json={
                "prompt": "Combien d'employés ?",
                "conversation_history": [
                    {"role": "user", "content": "Combien d'employés ?"},
                ],
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["answer"] == "Votre entreprise compte 10 employés."
        assert data["needs_clarification"] is False
        assert data["sql_queries"] == ["SELECT COUNT(*) FROM employees"]
        mock_handle.assert_called_once()
        call_input = mock_handle.call_args[0][0]
        assert call_input.prompt == "Combien d'employés ?"
        assert call_input.user_id == "test-user-id-copilot"
        assert len(call_input.conversation_history) == 1
        assert call_input.conversation_history[0].role == "user"
        assert call_input.conversation_history[0].content == "Combien d'employés ?"

    @patch("app.modules.copilot.api.router.commands.handle_agent_query")
    def test_query_agent_lookup_error_returns_404(
        self, mock_handle, client_with_copilot_user: TestClient
    ):
        """LookupError (company non trouvée) → 404."""
        mock_handle.side_effect = LookupError(
            "Company ID non trouvé pour cet utilisateur"
        )
        response = client_with_copilot_user.post(
            "/api/copilot/query-agent",
            json={"prompt": "Combien d'employés ?", "conversation_history": []},
        )
        assert response.status_code == 404

    @patch("app.modules.copilot.api.router.commands.handle_agent_query")
    def test_query_agent_value_error_returns_500(
        self, mock_handle, client_with_copilot_user: TestClient
    ):
        """ValueError (ex: clé API manquante) → 500."""
        mock_handle.side_effect = ValueError("Le service Copilote n'est pas configuré.")
        response = client_with_copilot_user.post(
            "/api/copilot/query-agent",
            json={"prompt": "Combien d'employés ?", "conversation_history": []},
        )
        assert response.status_code == 500

    def test_query_agent_missing_prompt_returns_422(
        self, client_with_copilot_user: TestClient
    ):
        """Body sans 'prompt' → 422."""
        response = client_with_copilot_user.post(
            "/api/copilot/query-agent",
            json={"conversation_history": []},
        )
        assert response.status_code == 422
