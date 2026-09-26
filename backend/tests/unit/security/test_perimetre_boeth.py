"""
Historique BOETH d'un salarié : périmètre société (audit du 25/09/2026, E6).

GET /api/oeth-settings/employees/{id}/boeth/history (donnée de santé) était
lisible par tout compte connecté, pour n'importe quel salarié de n'importe
quelle société : seule l'existence d'une société active était vérifiée.
La route exige désormais le droit RH dans la société active et un salarié
de cette société.
"""

from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from app.core.security import get_current_user
from app.main import app
from app.modules.users.schemas.responses import CompanyAccess, User

SOCIETE_A = "aaaaaaaa-1111-1111-1111-111111111111"
SOCIETE_B = "bbbbbbbb-2222-2222-2222-222222222222"
SALARIE = "cccccccc-3333-3333-3333-333333333333"
URL = f"/api/oeth-settings/employees/{SALARIE}/boeth/history"


def _user(role: str = "rh", *, platform_admin: bool = False) -> User:
    return User(
        id="dddddddd-4444-4444-4444-444444444444",
        email="compte@societe-a.fr",
        first_name="Rita",
        last_name="Aitch",
        is_platform_admin=platform_admin,
        is_group_admin=False,
        accessible_companies=[
            CompanyAccess(
                company_id=SOCIETE_A,
                company_name="Société A",
                role=role,
                is_primary=True,
            ),
        ],
        active_company_id=SOCIETE_A,
    )


def _get(user: User, societe_du_salarie: str | None):
    app.dependency_overrides[get_current_user] = lambda: user
    try:
        with (
            patch("app.modules.oeth_settings.api.router.queries") as queries,
            patch(
                "app.modules.access_control.application.service.providers"
            ) as providers,
        ):
            providers.get_employee_company_id.return_value = societe_du_salarie
            queries.get_employee_boeth_history.return_value = [
                {
                    "id": "h-1",
                    "previous_boeth_code": None,
                    "new_boeth_code": "01",
                    "changed_at": "2026-03-01",
                    "changed_in_period": "2026-03",
                }
            ]
            reponse = TestClient(app).get(URL)
        return reponse, queries
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_rh_ne_lit_pas_l_historique_d_un_salarie_d_une_autre_societe():
    reponse, queries = _get(_user("rh"), SOCIETE_B)
    assert reponse.status_code == 404
    queries.get_employee_boeth_history.assert_not_called()


def test_salarie_introuvable_refuse():
    reponse, queries = _get(_user("rh"), None)
    assert reponse.status_code == 404
    queries.get_employee_boeth_history.assert_not_called()


def test_collaborateur_ne_lit_pas_une_donnee_de_sante():
    reponse, queries = _get(_user("collaborateur"), SOCIETE_A)
    assert reponse.status_code == 403
    queries.get_employee_boeth_history.assert_not_called()


def test_rh_lit_l_historique_d_un_salarie_de_sa_societe():
    reponse, queries = _get(_user("rh"), SOCIETE_A)
    assert reponse.status_code == 200
    assert reponse.json()[0]["new_boeth_code"] == "01"
    queries.get_employee_boeth_history.assert_called_once_with(SALARIE)


def test_platform_admin_garde_son_acces_transverse():
    reponse, queries = _get(_user(platform_admin=True), SOCIETE_B)
    assert reponse.status_code == 200
    queries.get_employee_boeth_history.assert_called_once_with(SALARIE)
