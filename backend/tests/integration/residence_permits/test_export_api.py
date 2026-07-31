"""
Route POST /api/residence-permits/export.

POST et non GET : la liste d'identifiants est de longueur variable et passerait
dans l'URL, dont la longueur est bornée par les navigateurs et les proxys.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.core.security import get_current_user
from app.main import app
from app.modules.residence_permits.application.exports import (
    ResidencePermitExportEmpty,
    ResidencePermitExportTooLarge,
)
from app.modules.users.schemas.responses import CompanyAccess, User

pytestmark = pytest.mark.integration

TEST_COMPANY_ID = "550e8400-e29b-41d4-a716-446655440000"
TEST_USER_ID = "660e8400-e29b-41d4-a716-446655440001"
XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
ROUTE = "/api/residence-permits/export"


def _rh_user(role: str = "rh"):
    return User(
        id=TEST_USER_ID,
        email="rh@test.com",
        accessible_companies=[
            CompanyAccess(
                company_id=TEST_COMPANY_ID,
                company_name="Mont Blanc Composite",
                role=role,
                is_primary=True,
            )
        ],
        active_company_id=TEST_COMPANY_ID,
    )


@pytest.fixture
def client_rh():
    app.dependency_overrides[get_current_user] = lambda: _rh_user()
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def client_collaborateur():
    app.dependency_overrides[get_current_user] = lambda: _rh_user(role="collaborateur")
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_cas_nominal(client_rh):
    with patch(
        "app.modules.residence_permits.api.router.export_residence_permits",
        return_value=(b"PK-faux-xlsx", "titres-de-sejour_test_2026-07-31.xlsx"),
    ) as export:
        response = client_rh.post(ROUTE, json={"employee_ids": ["emp-1", "emp-2"]})

    assert response.status_code == 200
    assert response.headers["content-type"] == XLSX_MIME
    assert (
        response.headers["content-disposition"]
        == 'attachment; filename="titres-de-sejour_test_2026-07-31.xlsx"'
    )
    assert response.content == b"PK-faux-xlsx"
    assert export.call_args.args[0] == TEST_COMPANY_ID
    assert export.call_args.args[1] == "Mont Blanc Composite"
    assert export.call_args.args[2] == ["emp-1", "emp-2"]


def test_sans_acces_rh(client_collaborateur):
    response = client_collaborateur.post(ROUTE, json={"employee_ids": ["emp-1"]})

    assert response.status_code == 403


def test_selection_vide(client_rh):
    with patch(
        "app.modules.residence_permits.api.router.export_residence_permits",
        side_effect=ResidencePermitExportEmpty("Aucun salarié à exporter"),
    ):
        response = client_rh.post(ROUTE, json={"employee_ids": []})

    assert response.status_code == 400
    assert response.json()["detail"] == "Aucun salarié à exporter"


def test_trop_d_identifiants(client_rh):
    with patch(
        "app.modules.residence_permits.api.router.export_residence_permits",
        side_effect=ResidencePermitExportTooLarge(
            "Export limité à 1000 salariés par fichier"
        ),
    ):
        response = client_rh.post(ROUTE, json={"employee_ids": ["emp-1"]})

    assert response.status_code == 400
    assert "1000" in response.json()["detail"]


def test_erreur_inattendue_donne_500(client_rh):
    with patch(
        "app.modules.residence_permits.api.router.export_residence_permits",
        side_effect=RuntimeError("boum"),
    ):
        response = client_rh.post(ROUTE, json={"employee_ids": ["emp-1"]})

    assert response.status_code == 500


def test_corps_absent_rejete(client_rh):
    response = client_rh.post(ROUTE, json={})

    assert response.status_code == 422
