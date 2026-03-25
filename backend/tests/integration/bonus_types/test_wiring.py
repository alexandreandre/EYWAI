"""
Tests de câblage (wiring) du module bonus_types.

Vérifient que l'injection des dépendances et le flux de bout en bout
(router -> application -> service -> repository / provider) fonctionnent.
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
TEST_USER_ID = "660e8400-e29b-41d4-a716-446655440001"


def _rh_user():
    """Utilisateur RH avec active_company_id et droits RH."""
    return User(
        id=TEST_USER_ID,
        email="rh@wiring.com",
        first_name="RH",
        last_name="Wiring",
        is_super_admin=False,
        is_group_admin=False,
        accessible_companies=[
            CompanyAccess(
                company_id=TEST_COMPANY_ID,
                company_name="Wiring Co",
                role="rh",
                is_primary=True,
            ),
        ],
        active_company_id=TEST_COMPANY_ID,
    )


class TestBonusTypesWiringList:
    """Flux GET /api/bonus-types : router -> query -> service -> repository."""

    def test_list_flow_uses_service_and_returns_formatted_list(
        self, client: TestClient
    ):
        from app.core.security import get_current_user

        mock_svc = MagicMock()
        entity = BonusType(
            id=uuid4(),
            company_id=uuid4(),
            libelle="Prime wiring",
            type=BonusTypeKind.MONTANT_FIXE,
            montant=100.0,
            seuil_heures=None,
            soumise_a_cotisations=True,
            soumise_a_impot=True,
            prompt_ia=None,
            created_at=datetime.now(),
            updated_at=None,
            created_by=uuid4(),
        )
        mock_svc.list_by_company.return_value = [entity]

        app.dependency_overrides[get_current_user] = lambda: _rh_user()
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
        assert data[0]["libelle"] == "Prime wiring"
        assert data[0]["type"] == "montant_fixe"
        assert "id" in data[0]
        assert "company_id" in data[0]
        mock_svc.list_by_company.assert_called_once_with(TEST_COMPANY_ID)


class TestBonusTypesWiringCreate:
    """Flux POST /api/bonus-types : router -> build_create_input -> command -> service -> repository."""

    def test_create_flow_builds_input_and_calls_service(self, client: TestClient):
        from app.core.security import get_current_user

        created = BonusType(
            id=uuid4(),
            company_id=uuid4(),
            libelle="Nouvelle prime wiring",
            type=BonusTypeKind.MONTANT_FIXE,
            montant=300.0,
            seuil_heures=None,
            soumise_a_cotisations=True,
            soumise_a_impot=True,
            prompt_ia=None,
            created_at=datetime.now(),
            updated_at=None,
            created_by=uuid4(),
        )
        mock_svc = MagicMock()
        mock_svc.create.return_value = created

        app.dependency_overrides[get_current_user] = lambda: _rh_user()
        try:
            with patch(
                "app.modules.bonus_types.application.commands.get_bonus_types_service",
                return_value=mock_svc,
            ):
                response = client.post(
                    "/api/bonus-types",
                    json={
                        "libelle": "Nouvelle prime wiring",
                        "type": "montant_fixe",
                        "montant": 300.0,
                        "soumise_a_cotisations": True,
                        "soumise_a_impot": True,
                    },
                )
        finally:
            app.dependency_overrides.pop(get_current_user, None)

        assert response.status_code == 201
        body = response.json()
        assert body["libelle"] == "Nouvelle prime wiring"
        assert body["montant"] == 300.0
        mock_svc.create.assert_called_once()
        call_args = mock_svc.create.call_args[0]
        assert call_args[1] is True  # has_rh_access
        assert call_args[0].libelle == "Nouvelle prime wiring"
        assert call_args[0].company_id is not None


class TestBonusTypesWiringCalculate:
    """Flux GET /api/bonus-types/calculate/{id} : router -> query -> service (rules + hours provider)."""

    def test_calculate_flow_returns_result_dict(self, client: TestClient):
        from app.core.security import get_current_user

        mock_svc = MagicMock()
        mock_svc.calculate_amount.return_value = BonusCalculationResult(
            amount=80.0,
            calculated=True,
            total_hours=160.0,
            seuil=151.67,
            condition_met=True,
        )

        app.dependency_overrides[get_current_user] = lambda: _rh_user()
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
        assert data["amount"] == 80.0
        assert data["calculated"] is True
        assert data["total_hours"] == 160.0
        assert data["seuil"] == 151.67
        assert data["condition_met"] is True
        mock_svc.calculate_amount.assert_called_once_with(
            "bt-1", TEST_COMPANY_ID, "emp-1", 2025, 3
        )


class TestBonusTypesWiringDelete:
    """Flux DELETE : router -> command -> service -> repository."""

    def test_delete_flow_calls_service_with_context(self, client: TestClient):
        from app.core.security import get_current_user

        mock_svc = MagicMock()
        mock_svc.delete.return_value = True

        app.dependency_overrides[get_current_user] = lambda: _rh_user()
        try:
            with patch(
                "app.modules.bonus_types.application.commands.get_bonus_types_service",
                return_value=mock_svc,
            ):
                response = client.delete("/api/bonus-types/bt-delete-me")
        finally:
            app.dependency_overrides.pop(get_current_user, None)

        assert response.status_code == 200
        mock_svc.delete.assert_called_once_with(
            "bt-delete-me", TEST_COMPANY_ID, False, True
        )
