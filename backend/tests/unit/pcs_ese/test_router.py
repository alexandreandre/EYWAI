"""Les routes du code PCS-ESE : la liste pour tout compte, la proposition pour la RH."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.security import get_current_user
from app.modules.pcs_ese.api.router import router
from app.modules.pcs_ese.domain.proposition import Proposition
from app.modules.users.schemas.responses import CompanyAccess, User

_SOCIETE = "aaaaaaaa-1111-1111-1111-111111111111"


def _compte(role: str) -> User:
    return User(
        id="dddddddd-4444-4444-4444-444444444444",
        email="compte@societe-a.fr",
        first_name="Rita",
        last_name="Aitch",
        is_platform_admin=False,
        is_group_admin=False,
        accessible_companies=[
            CompanyAccess(company_id=_SOCIETE, company_name="Société A", role=role, is_primary=True)
        ],
        active_company_id=_SOCIETE,
    )


def _client(role: str) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: _compte(role)
    return TestClient(app)


_PROPOSITION = Proposition("674a", True, "raison", "a", 2, (), False)


def test_referentiel_pour_tout_compte():
    r = _client("collaborateur").get("/api/pcs-ese/referentiel")
    assert r.status_code == 200 and len(r.json()) == 430


def test_proposition_pour_la_rh():
    with patch("app.modules.pcs_ese.api.router.queries.proposition_pour", return_value=_PROPOSITION) as q:
        r = _client("rh").get("/api/pcs-ese/proposition", params={"poste": "Soudeur", "statut": "Non-Cadre"})
    assert r.status_code == 200 and r.json()["code"] == "674a"
    q.assert_called_once_with(_SOCIETE, "Soudeur", "Non-Cadre", None)


@pytest.mark.parametrize("role", ["collaborateur"])
def test_proposition_refusee_hors_rh(role):
    r = _client(role).get("/api/pcs-ese/proposition", params={"poste": "x", "statut": "Non-Cadre"})
    assert r.status_code == 403


def test_salarie_d_une_autre_societe():
    with patch(
        "app.modules.pcs_ese.api.router.access_control_service.assert_employee_in_company",
        side_effect=__import__("fastapi").HTTPException(status_code=404, detail="Salarié introuvable"),
    ):
        r = _client("rh").get(
            "/api/pcs-ese/proposition", params={"poste": "x", "statut": "Cadre", "employee_id": "autre"}
        )
    assert r.status_code == 404
