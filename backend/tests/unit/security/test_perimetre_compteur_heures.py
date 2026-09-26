"""
Compteur d'heures (modulation) d'un salarié : périmètre société
(audit du 25/09/2026, E7).

GET /api/modulation/employees/{id}/movements ne contrôlait rien : tout compte
connecté lisait les mouvements du compteur de n'importe quel salarié, les
mouvements étant filtrés sur le seul identifiant du salarié. Le solde
(/balance) vérifiait la société mais pas le salarié. Les deux lectures
exigent désormais le droit RH dans la société et un salarié de cette société.
L'espace salarié n'appelle aucune des deux (seule la page RH « Temps de
travail » lit les mouvements).
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.core.security import get_current_user
from app.main import app
from app.modules.modulation.schemas.requests import (
    ModulationBalanceResponse,
    ModulationMovementSchema,
)
from app.modules.users.schemas.responses import CompanyAccess, User

SOCIETE_A = "aaaaaaaa-1111-1111-1111-111111111111"
SOCIETE_B = "bbbbbbbb-2222-2222-2222-222222222222"
SALARIE = "cccccccc-3333-3333-3333-333333333333"

MOUVEMENTS = f"/api/modulation/employees/{SALARIE}/movements"
SOLDE = f"/api/modulation/employees/{SALARIE}/balance"
LECTURES = [
    (MOUVEMENTS, "list_employee_movements"),
    (SOLDE, "get_employee_account_balance"),
]


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


def _get(user: User, url: str, societe_du_salarie: str | None):
    app.dependency_overrides[get_current_user] = lambda: user
    try:
        with (
            patch(
                "app.modules.modulation.api.router.hour_account_queries"
            ) as hour_queries,
            patch(
                "app.modules.access_control.application.service.providers"
            ) as providers,
        ):
            providers.get_employee_company_id.return_value = societe_du_salarie
            hour_queries.list_employee_movements.return_value = [
                ModulationMovementSchema(
                    id="m-1",
                    employee_id=SALARIE,
                    year=2026,
                    movement_type="opening_balance",
                    hours=12.5,
                    status="validated",
                    source="manual_rh",
                )
            ]
            hour_queries.get_employee_account_balance.return_value = (
                ModulationBalanceResponse(
                    employee_id=SALARIE, year=2026, account_balance_hours=12.5
                )
            )
            reponse = TestClient(app).get(url)
        return reponse, hour_queries
    finally:
        app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.parametrize("url,lecture", LECTURES)
def test_rh_ne_lit_pas_le_compteur_d_un_salarie_d_une_autre_societe(url, lecture):
    reponse, hour_queries = _get(_user("rh"), url, SOCIETE_B)
    # 404, patron de require_employee_access : l'existence n'est pas révélée.
    assert reponse.status_code == 404
    getattr(hour_queries, lecture).assert_not_called()


@pytest.mark.parametrize("url,lecture", LECTURES)
def test_collaborateur_ne_lit_pas_le_compteur_d_un_salarie(url, lecture):
    reponse, hour_queries = _get(_user("collaborateur"), url, SOCIETE_A)
    assert reponse.status_code == 403
    getattr(hour_queries, lecture).assert_not_called()


def test_rh_lit_les_mouvements_d_un_salarie_de_sa_societe():
    reponse, hour_queries = _get(_user("rh"), MOUVEMENTS, SOCIETE_A)
    assert reponse.status_code == 200
    assert reponse.json()[0]["hours"] == 12.5
    hour_queries.list_employee_movements.assert_called_once_with(
        SALARIE, None, limit=100, offset=0
    )


def test_rh_lit_le_solde_d_un_salarie_de_sa_societe():
    reponse, hour_queries = _get(_user("rh"), f"{SOLDE}?year=2026", SOCIETE_A)
    assert reponse.status_code == 200
    assert reponse.json()["account_balance_hours"] == 12.5
    hour_queries.get_employee_account_balance.assert_called_once_with(
        SOCIETE_A, SALARIE, 2026, month=None
    )


@pytest.mark.parametrize("url,lecture", LECTURES)
def test_platform_admin_garde_son_acces_transverse(url, lecture):
    reponse, hour_queries = _get(_user(platform_admin=True), url, SOCIETE_B)
    assert reponse.status_code == 200
    getattr(hour_queries, lecture).assert_called_once()


# ----- écritures manuelles au compteur (solde initial, ajustement) -----
#
# Hors liste de l'audit, même compteur : la RH de la société A inscrivait un
# mouvement au compteur d'un salarié de la société B (le mouvement porte la
# société A, mais le solde se calcule sur le seul identifiant du salarié).

ECRITURES = [
    (
        f"/api/modulation/employees/{SALARIE}/opening-balance",
        {"hours": 12.5},
        "create_opening_balance",
    ),
    (
        "/api/modulation/adjustments",
        {"employee_id": SALARIE, "hours": -3},
        "create_manual_adjustment",
    ),
]


def _post(user: User, url: str, corps: dict, societe_du_salarie: str | None):
    app.dependency_overrides[get_current_user] = lambda: user
    try:
        with (
            patch(
                "app.modules.modulation.api.router.hour_account_commands"
            ) as hour_commands,
            patch(
                "app.modules.access_control.application.service.providers"
            ) as providers,
        ):
            providers.get_employee_company_id.return_value = societe_du_salarie
            mouvement = ModulationMovementSchema(
                id="m-2",
                employee_id=SALARIE,
                year=2026,
                movement_type="adjustment",
                hours=float(corps["hours"]),
                status="validated",
                source="manual_rh",
            )
            hour_commands.create_opening_balance.return_value = mouvement
            hour_commands.create_manual_adjustment.return_value = mouvement
            reponse = TestClient(app).post(url, json=corps)
        return reponse, hour_commands
    finally:
        app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.parametrize("url,corps,commande", ECRITURES)
def test_rh_n_ecrit_pas_au_compteur_d_un_salarie_d_une_autre_societe(
    url, corps, commande
):
    reponse, hour_commands = _post(_user("rh"), url, corps, SOCIETE_B)
    assert reponse.status_code == 404
    getattr(hour_commands, commande).assert_not_called()


@pytest.mark.parametrize("url,corps,commande", ECRITURES)
def test_rh_ecrit_au_compteur_d_un_salarie_de_sa_societe(url, corps, commande):
    reponse, hour_commands = _post(_user("rh"), url, corps, SOCIETE_A)
    assert reponse.status_code == 200
    appel = getattr(hour_commands, commande).call_args
    assert appel.args[0] == SOCIETE_A
    assert appel.args[1] == SALARIE


@pytest.mark.parametrize("url,corps,commande", ECRITURES)
def test_ecriture_reste_reservee_aux_rh(url, corps, commande):
    reponse, hour_commands = _post(_user("collaborateur"), url, corps, SOCIETE_A)
    assert reponse.status_code == 403
    getattr(hour_commands, commande).assert_not_called()
