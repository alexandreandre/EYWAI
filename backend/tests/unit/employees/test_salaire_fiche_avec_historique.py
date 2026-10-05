"""Un salaire tapé dans « Modifier la fiche » n'est pas perdu sans le dire.

À chaque génération, `sync_employee_salaire_actif` remet sur la fiche le salaire
de l'historique daté (salary_history). Dès qu'un salarié a un historique, le
salaire changé dans le formulaire du profil disparaissait donc au bulletin
suivant, sans un mot. Il se change désormais avec une date d'effet
(PUT /salary) ; la modification de la fiche le refuse avec un message qui dit où
aller, et ne refuse rien d'autre (même salaire renvoyé, ou pas d'historique).
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.core.security import get_current_user
from app.main import app
from app.modules.employees.application import commands
from app.modules.users.schemas.responses import CompanyAccess, User

pytestmark = pytest.mark.unit

_SOCIETE = "aaaaaaaa-1111-1111-1111-111111111111"
_FICHE = "cccccccc-3333-3333-3333-333333333333"
_ROUTER = "app.modules.employees.api.router"
_HISTORIQUE = [
    {"effective_date": "2026-01-01", "ancien_salaire": {"valeur": 1900.0},
     "nouveau_salaire": {"valeur": 2000.0}},
]
_RELUE = {
    "id": _FICHE, "employee_folder_name": "X_Y", "username": "xy",
    "first_name": "Xavier", "last_name": "Ygrec", "contract_type": "CDI",
}


def _rh() -> User:
    return User(
        id="dddddddd-4444-4444-4444-444444444444",
        email="rh@societe-a.fr",
        first_name="Rita",
        last_name="Aitch",
        is_platform_admin=False,
        is_group_admin=False,
        accessible_companies=[
            CompanyAccess(company_id=_SOCIETE, company_name="Société A", role="rh", is_primary=True)
        ],
        active_company_id=_SOCIETE,
    )


@pytest.fixture
def fiche():
    """Une fiche à 2 000 € ; l'historique est réglé par chaque test."""
    app.dependency_overrides[get_current_user] = _rh
    etat = {"historique": list(_HISTORIQUE)}
    try:
        with (
            patch(f"{_ROUTER}.assert_can_update_employee"),
            patch(f"{_ROUTER}.queries.get_employee_by_id", return_value=_RELUE),
            patch.object(commands, "update_employee") as ecrire,
            patch.object(commands._employee_repository, "get_by_id",
                         return_value={"id": _FICHE, "salaire_de_base": {"valeur": 2000.0}}),
            patch.object(commands._employee_repository, "get_salary_history",
                         side_effect=lambda *a: etat["historique"]),
        ):
            yield TestClient(app), ecrire, etat
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_un_salaire_change_sur_une_fiche_avec_historique_est_refuse(fiche):
    client, ecrire, _ = fiche
    reponse = client.put(f"/api/employees/{_FICHE}",
                         json={"salaire_de_base": {"valeur": 2100}, "job_title": "Régleur"})

    assert reponse.status_code == 400
    detail = reponse.json()["detail"]
    assert "date d'effet" in detail and "Changer le salaire" in detail
    assert "Rien n'a été enregistré" in detail
    # Moins de 220 caractères : l'écran affiche le message du serveur tel quel.
    assert len(detail) <= 220
    ecrire.assert_not_called()


def test_le_meme_salaire_renvoye_par_le_formulaire_passe(fiche):
    client, ecrire, _ = fiche
    reponse = client.put(f"/api/employees/{_FICHE}",
                         json={"salaire_de_base": {"valeur": 2000.0}, "job_title": "Régleur"})

    assert reponse.status_code == 200, reponse.text
    ecrire.assert_called_once()


def test_sans_historique_le_salaire_de_la_fiche_se_modifie(fiche):
    client, ecrire, etat = fiche
    etat["historique"] = []
    reponse = client.put(f"/api/employees/{_FICHE}", json={"salaire_de_base": {"valeur": 2100}})

    assert reponse.status_code == 200, reponse.text
    ecrire.assert_called_once()


def test_une_fiche_modifiee_sans_salaire_ne_lit_pas_l_historique(fiche):
    client, ecrire, _ = fiche
    with patch.object(commands._employee_repository, "get_salary_history") as historique:
        reponse = client.put(f"/api/employees/{_FICHE}", json={"job_title": "Régleur"})

    assert reponse.status_code == 200, reponse.text
    historique.assert_not_called()
    ecrire.assert_called_once()
