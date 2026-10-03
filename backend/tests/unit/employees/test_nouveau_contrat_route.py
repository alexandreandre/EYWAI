"""Routes « Nouveau contrat » : réservées à la RH, chaque enregistrement est tracé.

Un refus garde son message (400), une fiche modifiée entre-temps rend 409, une
écriture ratée rend 500 avec l'état laissé ; aucun des trois n'est tracé comme fait.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.core.security import get_current_user
from app.main import app
from app.modules.employees.application import nouveau_contrat as service
from app.modules.users.schemas.responses import CompanyAccess, User

pytestmark = pytest.mark.unit

_SOCIETE = "aaaaaaaa-1111-1111-1111-111111111111"
_FICHE = "cccccccc-3333-3333-3333-333333333333"
_ROUTER = "app.modules.employees.api.router"
_CORPS = {
    "date_debut": "2026-09-01",
    "contract_type": "CDD",
    "date_fin": "2026-12-18",
    "duree_hebdomadaire": 39,
    "salaire_mensuel": 2017.22,
    "job_title": "Opératrice polyvalente",
    "reprendre_anciennete": False,
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
def client():
    app.dependency_overrides[get_current_user] = _rh
    try:
        with patch(f"{_ROUTER}._rh_employee", return_value=_SOCIETE) as garde:
            client = TestClient(app)
            client.garde = garde
            yield client
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_l_apercu_passe_par_la_garde_rh(client):
    apercu = {"possible": True, "raison": None}
    with patch(f"{_ROUTER}.nouveau_contrat.apercu", return_value=apercu) as lire:
        reponse = client.get(f"/api/employees/{_FICHE}/new-contract")
    assert reponse.status_code == 200
    assert reponse.json() == apercu
    client.garde.assert_called_once()
    lire.assert_called_once_with(_FICHE, _SOCIETE)


def test_l_enregistrement_est_trace(client):
    resultat = {
        "message": "Nouveau contrat enregistré : CDD du 01/09/2026 au 18/12/2026.",
        "avertissements": [],
        "contrat_precedent": {"id": "p-1", "contract_type": "CDD", "date_debut": "2026-01-19", "date_fin": "2026-05-31"},
        "date_anciennete": "2026-09-01",
        "employee": {"id": _FICHE},
    }
    with patch(f"{_ROUTER}.nouveau_contrat.creer", return_value=resultat), patch(
        f"{_ROUTER}.log_audit_event"
    ) as audit:
        reponse = client.post(f"/api/employees/{_FICHE}/new-contract", json=_CORPS)
    assert reponse.status_code == 201
    assert reponse.json() == resultat
    audit.assert_called_once()
    kwargs = audit.call_args.kwargs
    assert kwargs["action"] == "employee.contract.new"
    assert kwargs["resource_id"] == _FICHE
    assert kwargs["details"] == {
        "contrat_precedent": {"contract_type": "CDD", "date_debut": "2026-01-19", "date_fin": "2026-05-31"},
        "nouveau_contrat": {
            "contract_type": "CDD",
            "date_debut": "2026-09-01",
            "date_fin": "2026-12-18",
            "duree_hebdomadaire": 39.0,
            "salaire_mensuel": 2017.22,
            "job_title": "Opératrice polyvalente",
        },
        "reprendre_anciennete": False,
        "date_anciennete": "2026-09-01",
        "avertissements": [],
    }


@pytest.mark.parametrize(
    "erreur, statut",
    [
        (service.NouveauContratRefuse("Indiquez la date de fin du CDD."), 400),
        (service.FicheModifiee("La fiche a changé pendant la saisie."), 409),
        (service.NonEnregistre("Le nouveau contrat n'a pas été enregistré."), 500),
    ],
)
def test_un_echec_garde_son_message_et_n_est_pas_trace(client, erreur, statut):
    with patch(f"{_ROUTER}.nouveau_contrat.creer", side_effect=erreur), patch(
        f"{_ROUTER}.log_audit_event"
    ) as audit:
        reponse = client.post(f"/api/employees/{_FICHE}/new-contract", json=_CORPS)
    assert reponse.status_code == statut
    assert reponse.json()["detail"] == str(erreur)
    audit.assert_not_called()


def test_un_corps_incomplet_est_refuse_avant_tout(client):
    with patch(f"{_ROUTER}.nouveau_contrat.creer") as creer:
        reponse = client.post(f"/api/employees/{_FICHE}/new-contract", json={"date_debut": "2026-09-01"})
    assert reponse.status_code == 422
    creer.assert_not_called()
