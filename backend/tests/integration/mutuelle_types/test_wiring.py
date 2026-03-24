"""
Tests de câblage (wiring) du module mutuelle_types.

Vérifient que l'injection des dépendances et le flux de bout en bout
(router -> application commands/queries -> service -> repository) fonctionnent.
"""
from datetime import datetime
from uuid import UUID, uuid4
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.modules.mutuelle_types.domain.entities import MutuelleType
from app.modules.users.schemas.responses import User, CompanyAccess


pytestmark = pytest.mark.integration

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


class TestMutuelleTypesWiringList:
    """Flux GET /api/mutuelle-types : router -> query -> service -> repository."""

    def test_list_flow_uses_repository_and_returns_formatted_list(
        self, client: TestClient
    ):
        from app.core.security import get_current_user

        entity = MutuelleType(
            id=uuid4(),
            company_id=uuid4(),
            libelle="Formule wiring",
            montant_salarial=50.0,
            montant_patronal=30.0,
            part_patronale_soumise_a_csg=True,
            is_active=True,
            created_at=datetime.now(),
            updated_at=None,
            created_by=uuid4(),
        )
        mock_repo = MagicMock()
        mock_repo.list_by_company.return_value = [entity]
        mock_repo.list_employee_ids.return_value = ["emp-1"]

        app.dependency_overrides[get_current_user] = lambda: _rh_user()
        try:
            with patch(
                "app.modules.mutuelle_types.application.queries.SupabaseMutuelleTypeRepository",
                return_value=mock_repo,
            ):
                response = client.get("/api/mutuelle-types")
        finally:
            app.dependency_overrides.pop(get_current_user, None)

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["libelle"] == "Formule wiring"
        assert data[0]["montant_salarial"] == 50.0
        assert "id" in data[0]
        assert "company_id" in data[0]
        assert data[0]["employee_ids"] == ["emp-1"]
        mock_repo.list_by_company.assert_called_once_with(TEST_COMPANY_ID)


class TestMutuelleTypesWiringCreate:
    """Flux POST /api/mutuelle-types : router -> command -> service -> repository."""

    def test_create_flow_calls_service_and_returns_created_dict(
        self, client: TestClient
    ):
        from app.core.security import get_current_user

        created = MutuelleType(
            id=uuid4(),
            company_id=uuid4(),
            libelle="Nouvelle formule wiring",
            montant_salarial=60.0,
            montant_patronal=40.0,
            part_patronale_soumise_a_csg=True,
            is_active=True,
            created_at=datetime.now(),
            updated_at=None,
            created_by=uuid4(),
        )
        mock_repo = MagicMock()
        mock_repo.find_by_company_and_libelle.return_value = None
        mock_repo.create.return_value = created
        mock_repo.validate_employee_ids_belong_to_company.return_value = []
        mock_repo.set_employee_associations.return_value = None

        app.dependency_overrides[get_current_user] = lambda: _rh_user()
        try:
            with patch(
                "app.modules.mutuelle_types.application.commands.SupabaseMutuelleTypeRepository",
                return_value=mock_repo,
            ):
                response = client.post(
                    "/api/mutuelle-types",
                    json={
                        "libelle": "Nouvelle formule wiring",
                        "montant_salarial": 60.0,
                        "montant_patronal": 40.0,
                        "part_patronale_soumise_a_csg": True,
                        "is_active": True,
                        "employee_ids": [],
                    },
                )
        finally:
            app.dependency_overrides.pop(get_current_user, None)

        assert response.status_code == 201
        body = response.json()
        assert body["libelle"] == "Nouvelle formule wiring"
        assert body["montant_salarial"] == 60.0
        mock_repo.find_by_company_and_libelle.assert_called_once_with(
            TEST_COMPANY_ID, "Nouvelle formule wiring"
        )
        mock_repo.create.assert_called_once()


class TestMutuelleTypesWiringDelete:
    """Flux DELETE : router -> command -> service -> repository."""

    def test_delete_flow_calls_service_and_repository(self, client: TestClient):
        from app.core.security import get_current_user

        mutuelle_id = str(uuid4())
        existing = MutuelleType(
            id=uuid4(),
            company_id=UUID(TEST_COMPANY_ID),
            libelle="À supprimer",
            montant_salarial=50.0,
            montant_patronal=30.0,
            part_patronale_soumise_a_csg=True,
            is_active=True,
            created_at=None,
            updated_at=None,
            created_by=None,
        )
        mock_repo = MagicMock()
        mock_repo.get_by_id.return_value = existing
        mock_repo.list_employee_ids.return_value = []
        mock_repo.remove_employee_associations_and_sync_specificites.return_value = None
        mock_repo.delete.return_value = True

        app.dependency_overrides[get_current_user] = lambda: _rh_user()
        try:
            with patch(
                "app.modules.mutuelle_types.application.commands.SupabaseMutuelleTypeRepository",
                return_value=mock_repo,
            ):
                response = client.delete(f"/api/mutuelle-types/{mutuelle_id}")
        finally:
            app.dependency_overrides.pop(get_current_user, None)

        assert response.status_code == 200
        assert response.json().get("status") == "success"
        mock_repo.get_by_id.assert_called_once_with(mutuelle_id, TEST_COMPANY_ID)
        mock_repo.delete.assert_called_once_with(mutuelle_id)
