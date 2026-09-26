"""
Périodes d'essai : périmètre société (audit du 25/09/2026, E5).

Modification, confirmation et renouvellement ne contrôlaient que le rôle RH,
puis écrivaient par l'identifiant seul : une RH de la société A agissait sur
la période d'essai d'un salarié de la société B. La période doit désormais
appartenir à la société active, et son salarié aussi. La création vérifie de
même le salarié reçu dans le corps de la requête.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.core.security import get_current_user
from app.main import app
from app.modules.users.schemas.responses import CompanyAccess, User

SOCIETE_A = "aaaaaaaa-1111-1111-1111-111111111111"
SOCIETE_B = "bbbbbbbb-2222-2222-2222-222222222222"
PERIODE = "eeeeeeee-5555-5555-5555-555555555555"
SALARIE = "cccccccc-3333-3333-3333-333333333333"


def _user(role: str = "rh", *, platform_admin: bool = False) -> User:
    return User(
        id="dddddddd-4444-4444-4444-444444444444",
        email="rh@societe-a.fr",
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


def _periode(company_id: str) -> dict:
    return {
        "id": PERIODE,
        "company_id": company_id,
        "employee_id": SALARIE,
        "status": "en_cours",
    }


# (méthode, suffixe, corps, commande)
MUTATIONS = [
    ("patch", "", {"duration_value": 3}, "update_trial_period"),
    ("post", "/confirm", None, "confirm_trial_period"),
    (
        "post",
        "/renew",
        {"renewed_at": "2026-09-01", "duration_value": 2, "duration_unit": "mois"},
        "renew_trial_period",
    ),
]


def _appeler(
    user: User,
    methode: str,
    suffixe: str,
    corps,
    *,
    periode: dict | None,
    societe_du_salarie: str | None,
):
    app.dependency_overrides[get_current_user] = lambda: user
    try:
        with (
            patch(
                "app.modules.trial_periods.api.access.queries.get_trial_period",
                return_value=periode,
            ),
            patch(
                "app.modules.access_control.application.service.providers"
            ) as providers,
            patch("app.modules.trial_periods.api.router.commands") as commands,
        ):
            providers.get_employee_company_id.return_value = societe_du_salarie
            for nom in (
                "update_trial_period",
                "confirm_trial_period",
                "renew_trial_period",
                "create_trial_period",
            ):
                getattr(commands, nom).return_value = {"id": PERIODE}
            client = TestClient(app)
            url = f"/api/trial-periods{suffixe}"
            if corps is None:
                reponse = getattr(client, methode)(url)
            else:
                reponse = getattr(client, methode)(url, json=corps)
        return reponse, commands
    finally:
        app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.parametrize("methode,suffixe,corps,commande", MUTATIONS)
def test_periode_d_une_autre_societe_refusee(methode, suffixe, corps, commande):
    reponse, commands = _appeler(
        _user(),
        methode,
        f"/{PERIODE}{suffixe}",
        corps,
        periode=_periode(SOCIETE_B),
        societe_du_salarie=SOCIETE_B,
    )
    # 404 : l'existence de la période n'est pas révélée.
    assert reponse.status_code == 404
    getattr(commands, commande).assert_not_called()


@pytest.mark.parametrize("methode,suffixe,corps,commande", MUTATIONS)
def test_salarie_d_une_autre_societe_refuse(methode, suffixe, corps, commande):
    """Période rangée dans ma société, mais salarié d'une autre : refusé."""
    reponse, commands = _appeler(
        _user(),
        methode,
        f"/{PERIODE}{suffixe}",
        corps,
        periode=_periode(SOCIETE_A),
        societe_du_salarie=SOCIETE_B,
    )
    assert reponse.status_code == 404
    getattr(commands, commande).assert_not_called()


@pytest.mark.parametrize("methode,suffixe,corps,commande", MUTATIONS)
def test_periode_introuvable_refusee(methode, suffixe, corps, commande):
    reponse, commands = _appeler(
        _user(),
        methode,
        f"/{PERIODE}{suffixe}",
        corps,
        periode=None,
        societe_du_salarie=None,
    )
    assert reponse.status_code == 404
    getattr(commands, commande).assert_not_called()


@pytest.mark.parametrize("methode,suffixe,corps,commande", MUTATIONS)
def test_periode_de_ma_societe_autorisee_comme_avant(methode, suffixe, corps, commande):
    reponse, commands = _appeler(
        _user(),
        methode,
        f"/{PERIODE}{suffixe}",
        corps,
        periode=_periode(SOCIETE_A),
        societe_du_salarie=SOCIETE_A,
    )
    assert reponse.status_code == 200
    assert reponse.json() == {"id": PERIODE}
    getattr(commands, commande).assert_called_once()
    assert getattr(commands, commande).call_args.args[0] == PERIODE


@pytest.mark.parametrize("methode,suffixe,corps,commande", MUTATIONS)
def test_reste_reserve_aux_rh(methode, suffixe, corps, commande):
    reponse, commands = _appeler(
        _user("collaborateur"),
        methode,
        f"/{PERIODE}{suffixe}",
        corps,
        periode=_periode(SOCIETE_A),
        societe_du_salarie=SOCIETE_A,
    )
    assert reponse.status_code == 403
    getattr(commands, commande).assert_not_called()


@pytest.mark.parametrize("methode,suffixe,corps,commande", MUTATIONS)
def test_platform_admin_garde_son_acces_transverse(methode, suffixe, corps, commande):
    reponse, commands = _appeler(
        _user(platform_admin=True),
        methode,
        f"/{PERIODE}{suffixe}",
        corps,
        periode=_periode(SOCIETE_B),
        societe_du_salarie=SOCIETE_B,
    )
    assert reponse.status_code == 200
    getattr(commands, commande).assert_called_once()


# ----- création : le salarié du corps de la requête -----

CREATION = {"employee_id": SALARIE, "start_date": "2026-09-01", "duration_value": 2}


def test_creation_pour_un_salarie_d_une_autre_societe_refusee():
    reponse, commands = _appeler(
        _user(), "post", "", CREATION, periode=None, societe_du_salarie=SOCIETE_B
    )
    assert reponse.status_code == 404
    commands.create_trial_period.assert_not_called()


def test_creation_pour_un_salarie_de_ma_societe_autorisee():
    reponse, commands = _appeler(
        _user(), "post", "", CREATION, periode=None, societe_du_salarie=SOCIETE_A
    )
    assert reponse.status_code == 200
    kwargs = commands.create_trial_period.call_args.kwargs
    assert kwargs["company_id"] == SOCIETE_A
    assert kwargs["employee_id"] == SALARIE
