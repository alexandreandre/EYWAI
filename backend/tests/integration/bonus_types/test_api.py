"""
Tests d'intégration HTTP des routes du module bonus_types.

Routes : GET/POST /api/bonus-types, PUT/DELETE /api/bonus-types/{id},
GET /api/bonus-types/calculate/{id}.
Utilise : client (TestClient), dependency_overrides pour get_current_user,
et mock du service (get_bonus_types_service) pour éviter la DB réelle.
"""
from datetime import datetime
from uuid import uuid4
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.modules.bonus_types.domain.entities import BonusType
from app.modules.bonus_types.domain.enums import BonusTypeKind
from app.modules.bonus_types.application.dto import BonusCalculationResult
from app.modules.users.schemas.responses import User, CompanyAccess


pytestmark = pytest.mark.integration

# UUIDs valides pour active_company_id (build_create_input fait UUID(str(company_id)))
TEST_COMPANY_ID = "550e8400-e29b-41d4-a716-446655440000"
TEST_RH_USER_ID = "660e8400-e29b-41d4-a716-446655440001"


def _make_rh_user(company_id: str = TEST_COMPANY_ID, user_id: str = TEST_RH_USER_ID):
    """Utilisateur de test avec droits RH sur l'entreprise et active_company_id."""
    return User(
        id=user_id,
        email="rh@bonus-test.com",
        first_name="RH",
        last_name="Bonus",
        is_super_admin=False,
        is_group_admin=False,
        accessible_companies=[
            CompanyAccess(
                company_id=company_id,
                company_name="Test Co",
                role="rh",
                is_primary=True,
            ),
        ],
        active_company_id=company_id,
    )


def _make_employee_user(company_id: str = TEST_COMPANY_ID):
    """Utilisateur sans droits RH (collaborateur)."""
    return User(
        id="770e8400-e29b-41d4-a716-446655440002",  # UUID valide pour build_create_input
        email="emp@bonus-test.com",
        first_name="Emp",
        last_name="Bonus",
        is_super_admin=False,
        is_group_admin=False,
        accessible_companies=[
            CompanyAccess(
                company_id=company_id,
                company_name="Test Co",
                role="collaborateur",
                is_primary=True,
            ),
        ],
        active_company_id=company_id,
    )


def _make_bonus_entity(**kwargs):
    defaults = {
        "id": uuid4(),
        "company_id": uuid4(),
        "libelle": "Prime test",
        "type": BonusTypeKind.MONTANT_FIXE,
        "montant": 100.0,
        "seuil_heures": None,
        "soumise_a_cotisations": True,
        "soumise_a_impot": True,
        "prompt_ia": None,
        "created_at": datetime.now(),
        "updated_at": None,
        "created_by": None,
    }
    defaults.update(kwargs)
    return BonusType(**defaults)


class TestBonusTypesUnauthenticated:
    """Sans token : toutes les routes protégées renvoient 401."""

    def test_get_list_returns_401_without_auth(self, client: TestClient):
        response = client.get("/api/bonus-types")
        assert response.status_code == 401

    def test_post_create_returns_401_without_auth(self, client: TestClient):
        response = client.post(
            "/api/bonus-types",
            json={
                "libelle": "Prime",
                "type": "montant_fixe",
                "montant": 100.0,
                "soumise_a_cotisations": True,
                "soumise_a_impot": True,
            },
        )
        assert response.status_code == 401

    def test_put_update_returns_401_without_auth(self, client: TestClient):
        response = client.put(
            "/api/bonus-types/bt-123",
            json={"libelle": "Prime mise à jour"},
        )
        assert response.status_code == 401

    def test_delete_returns_401_without_auth(self, client: TestClient):
        response = client.delete("/api/bonus-types/bt-123")
        assert response.status_code == 401

    def test_calculate_returns_401_without_auth(self, client: TestClient):
        response = client.get(
            "/api/bonus-types/calculate/bt-123",
            params={"employee_id": "emp-1", "year": 2025, "month": 3},
        )
        assert response.status_code == 401


class TestBonusTypesGetList:
    """GET /api/bonus-types."""

    def test_get_list_with_rh_user_returns_200_and_list(
        self, client: TestClient
    ):
        from app.core.security import get_current_user

        mock_svc = MagicMock()
        entity = _make_bonus_entity(libelle="Prime A")
        mock_svc.list_by_company.return_value = [entity]

        app.dependency_overrides[get_current_user] = lambda: _make_rh_user()
        try:
            with patch(
                "app.modules.bonus_types.application.queries.get_bonus_types_service",
                return_value=mock_svc,
            ):
                response = client.get("/api/bonus-types")
        finally:
            app.dependency_overrides.pop(get_current_user, None)

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["libelle"] == "Prime A"
        assert data[0]["type"] == "montant_fixe"
        mock_svc.list_by_company.assert_called_once_with(TEST_COMPANY_ID)

    def test_get_list_without_active_company_returns_400(
        self, client: TestClient
    ):
        from app.core.security import get_current_user

        user = _make_rh_user()
        user.active_company_id = None
        app.dependency_overrides[get_current_user] = lambda: user
        try:
            response = client.get("/api/bonus-types")
        finally:
            app.dependency_overrides.pop(get_current_user, None)

        assert response.status_code == 400
        assert "entreprise active" in response.json().get("detail", "").lower()


class TestBonusTypesPostCreate:
    """POST /api/bonus-types."""

    def test_create_with_rh_user_returns_201(self, client: TestClient):
        from app.core.security import get_current_user

        created = _make_bonus_entity(
            libelle="Nouvelle prime",
            montant=250.0,
            id=uuid4(),
        )
        mock_svc = MagicMock()
        mock_svc.create.return_value = created

        app.dependency_overrides[get_current_user] = lambda: _make_rh_user()
        try:
            with patch(
                "app.modules.bonus_types.application.commands.get_bonus_types_service",
                return_value=mock_svc,
            ):
                response = client.post(
                    "/api/bonus-types",
                    json={
                        "libelle": "Nouvelle prime",
                        "type": "montant_fixe",
                        "montant": 250.0,
                        "soumise_a_cotisations": True,
                        "soumise_a_impot": True,
                    },
                )
        finally:
            app.dependency_overrides.pop(get_current_user, None)

        assert response.status_code == 201
        body = response.json()
        assert body["libelle"] == "Nouvelle prime"
        assert body["montant"] == 250.0
        mock_svc.create.assert_called_once()

    def test_create_with_employee_user_returns_403(self, client: TestClient):
        from app.core.security import get_current_user

        mock_svc = MagicMock()
        from fastapi import HTTPException
        mock_svc.create.side_effect = HTTPException(
            status_code=403,
            detail="Seuls les Admin/RH peuvent créer des primes dans le catalogue",
        )

        app.dependency_overrides[get_current_user] = lambda: _make_employee_user()
        try:
            with patch(
                "app.modules.bonus_types.application.commands.get_bonus_types_service",
                return_value=mock_svc,
            ):
                response = client.post(
                    "/api/bonus-types",
                    json={
                        "libelle": "Prime",
                        "type": "montant_fixe",
                        "montant": 100.0,
                        "soumise_a_cotisations": True,
                        "soumise_a_impot": True,
                    },
                )
        finally:
            app.dependency_overrides.pop(get_current_user, None)

        assert response.status_code == 403

    def test_create_with_invalid_body_returns_422(self, client: TestClient):
        from app.core.security import get_current_user

        app.dependency_overrides[get_current_user] = lambda: _make_rh_user()
        try:
            response = client.post(
                "/api/bonus-types",
                json={
                    "libelle": "",  # min_length=1
                    "type": "montant_fixe",
                    "montant": -1,  # ge=0
                    "soumise_a_cotisations": True,
                    "soumise_a_impot": True,
                },
            )
        finally:
            app.dependency_overrides.pop(get_current_user, None)

        assert response.status_code == 422


class TestBonusTypesPutUpdate:
    """PUT /api/bonus-types/{bonus_type_id}."""

    def test_update_with_rh_user_returns_200(self, client: TestClient):
        from app.core.security import get_current_user

        updated = _make_bonus_entity(
            libelle="Prime mise à jour",
            montant=180.0,
        )
        mock_svc = MagicMock()
        mock_svc.update.return_value = updated

        app.dependency_overrides[get_current_user] = lambda: _make_rh_user()
        try:
            with patch(
                "app.modules.bonus_types.application.commands.get_bonus_types_service",
                return_value=mock_svc,
            ):
                response = client.put(
                    "/api/bonus-types/bt-123",
                    json={"libelle": "Prime mise à jour", "montant": 180.0},
                )
        finally:
            app.dependency_overrides.pop(get_current_user, None)

        assert response.status_code == 200
        assert response.json()["libelle"] == "Prime mise à jour"
        assert response.json()["montant"] == 180.0

    def test_update_without_active_company_returns_400(self, client: TestClient):
        from app.core.security import get_current_user

        user = _make_rh_user()
        user.active_company_id = None
        app.dependency_overrides[get_current_user] = lambda: user
        try:
            response = client.put(
                "/api/bonus-types/bt-123",
                json={"libelle": "X"},
            )
        finally:
            app.dependency_overrides.pop(get_current_user, None)

        assert response.status_code == 400


class TestBonusTypesDelete:
    """DELETE /api/bonus-types/{bonus_type_id}."""

    def test_delete_with_rh_user_returns_200(self, client: TestClient):
        from app.core.security import get_current_user

        mock_svc = MagicMock()
        mock_svc.delete.return_value = True

        app.dependency_overrides[get_current_user] = lambda: _make_rh_user()
        try:
            with patch(
                "app.modules.bonus_types.application.commands.get_bonus_types_service",
                return_value=mock_svc,
            ):
                response = client.delete("/api/bonus-types/bt-123")
        finally:
            app.dependency_overrides.pop(get_current_user, None)

        assert response.status_code == 200
        assert response.json().get("status") == "success"
        assert "supprimée" in response.json().get("message", "").lower()
        mock_svc.delete.assert_called_once()


class TestBonusTypesCalculate:
    """GET /api/bonus-types/calculate/{bonus_type_id}."""

    def test_calculate_returns_200_with_result(self, client: TestClient):
        from app.core.security import get_current_user

        mock_svc = MagicMock()
        mock_svc.calculate_amount.return_value = BonusCalculationResult(
            amount=100.0,
            calculated=True,
            total_hours=None,
            seuil=None,
            condition_met=None,
        )

        app.dependency_overrides[get_current_user] = lambda: _make_rh_user()
        try:
            with patch(
                "app.modules.bonus_types.application.queries.get_bonus_types_service",
                return_value=mock_svc,
            ):
                response = client.get(
                    "/api/bonus-types/calculate/bt-1",
                    params={"employee_id": "emp-1", "year": 2025, "month": 3},
                )
        finally:
            app.dependency_overrides.pop(get_current_user, None)

        assert response.status_code == 200
        data = response.json()
        assert data["amount"] == 100.0
        assert data["calculated"] is True
        mock_svc.calculate_amount.assert_called_once_with(
            "bt-1", TEST_COMPANY_ID, "emp-1", 2025, 3
        )
