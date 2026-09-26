"""
Modification d'une fiche salarié : périmètre société (constat du 26/09/2026).

PUT /api/employees/{id} n'avait aucune garde : tout compte connecté, même un
simple collaborateur, modifiait la fiche (RIB et e-mail compris) de n'importe
quel salarié de n'importe quelle société ; l'écriture précédait le contrôle.
Désormais : RH de la société active sur un salarié de cette société, ou le
salarié sur sa propre fiche (accueil). Rien n'est écrit en cas de refus.
"""

from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from app.core.security import get_current_user
from app.main import app
from app.modules.users.schemas.responses import CompanyAccess, User

SOCIETE_A = "aaaaaaaa-1111-1111-1111-111111111111"
SOCIETE_B = "bbbbbbbb-2222-2222-2222-222222222222"
COMPTE = "dddddddd-4444-4444-4444-444444444444"
SALARIE = "cccccccc-3333-3333-3333-333333333333"


def _user(role: str = "rh", *, platform_admin: bool = False) -> User:
    return User(
        id=COMPTE,
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


def _put(user: User, employee_id: str, societe_du_salarie: str | None, fiche_du_compte=None):
    app.dependency_overrides[get_current_user] = lambda: user
    try:
        with (
            patch("app.modules.employees.api.router.commands") as commands,
            patch("app.modules.employees.api.router.queries") as queries,
            patch(
                "app.modules.access_control.application.service.providers"
            ) as providers,
            patch(
                "app.modules.employees.api.deps.resolve_employee_id_for_user_account",
                return_value=fiche_du_compte,
            ),
        ):
            providers.get_employee_company_id.return_value = societe_du_salarie
            queries.get_employee_by_id.return_value = None
            reponse = TestClient(app).put(
                f"/api/employees/{employee_id}", json={"first_name": "Nouveau"}
            )
        return reponse, commands
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_rh_ne_modifie_pas_un_salarie_d_une_autre_societe():
    reponse, commands = _put(_user("rh"), SALARIE, SOCIETE_B)
    assert reponse.status_code == 404
    commands.update_employee.assert_not_called()


def test_salarie_inconnu_refuse_sans_ecrire():
    reponse, commands = _put(_user("rh"), SALARIE, None)
    assert reponse.status_code == 404
    commands.update_employee.assert_not_called()


def test_collaborateur_ne_modifie_pas_la_fiche_d_un_collegue():
    reponse, commands = _put(_user("collaborateur"), SALARIE, SOCIETE_A)
    assert reponse.status_code == 403
    commands.update_employee.assert_not_called()


def test_rh_modifie_un_salarie_de_sa_societe():
    reponse, commands = _put(_user("rh"), SALARIE, SOCIETE_A)
    commands.update_employee.assert_called_once_with(SALARIE, {"first_name": "Nouveau"})
    # La relecture simulée ne trouve rien : 404 après écriture, comme avant.
    assert reponse.status_code == 404


def test_le_salarie_modifie_sa_propre_fiche():
    reponse, commands = _put(
        _user("collaborateur"), SALARIE, SOCIETE_A, fiche_du_compte=SALARIE
    )
    commands.update_employee.assert_called_once_with(SALARIE, {"first_name": "Nouveau"})


def test_platform_admin_garde_son_acces_transverse():
    reponse, commands = _put(_user(platform_admin=True), SALARIE, SOCIETE_B)
    commands.update_employee.assert_called_once()
