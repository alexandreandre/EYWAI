"""Récapitulatif des congés de la société (lot L21, demande du 27/11).

Une ligne par salarié : jours de la période comptés sur le calendrier de paie
(CP, RTT, absences, arrêts par nature), JTC et repos seniors sur les demandes
validées, soldes CP repris de l'aperçu des soldes. Route RH seulement,
périmètre d'équipes respecté, export Excel lisible.
"""

from __future__ import annotations

import io
from datetime import date

import pytest
from fastapi.testclient import TestClient
from openpyxl import load_workbook

from app.core.security import get_current_user
from app.main import app
from app.modules.absences.application import recap_conges as app_recap
from app.modules.absences.domain.recap_conges import (
    compter_jours_des_demandes,
    compter_jours_du_calendrier,
    construire_recap,
    lire_periode,
    mois_de_la_periode,
)
from app.modules.users.schemas.responses import CompanyAccess, User

pytestmark = pytest.mark.unit

SOCIETE = "aaaaaaaa-1111-1111-1111-111111111111"
E1 = "e1000000-0000-0000-0000-000000000001"
E2 = "e2000000-0000-0000-0000-000000000002"
E3 = "e3000000-0000-0000-0000-000000000003"

NOV = date(2026, 11, 1), date(2026, 11, 30)


def _calendrier(annee: int, mois: int, jours: list[dict]) -> dict:
    return {"periode": {"annee": annee, "mois": mois}, "calendrier_prevu": jours}


def test_le_calendrier_donne_cp_rtt_et_demi_journees():
    cal = _calendrier(
        2026,
        11,
        [
            {"jour": 2, "type": "conges_payes"},
            {"jour": 3, "type": "conges_payes", "quotite_absence": 0.5},
            {"jour": 4, "type": "rtt"},
            {"jour": 5, "type": "travail"},
            {"jour": 6, "type": "repos"},
            {"jour": 9, "type": "conge"},
            {"jour": 10, "type": "evenement_familial"},
            {"jour": 12, "type": "activite_partielle"},
            {"jour": 13, "type": "absence_justifiee"},
        ],
    )
    jours = compter_jours_du_calendrier(cal, *NOV)
    assert jours["cp"] == 1.5
    assert jours["rtt"] == 1.0
    assert jours["repos_recup"] == 1.0
    assert jours["evenement_familial"] == 1.0
    assert jours["activite_partielle"] == 1.0
    assert jours["absence_justifiee"] == 1.0
    # Ni le travail ni le repos hebdomadaire ne sont des absences.
    assert sum(jours.values()) == 6.5


def test_les_arrets_sont_comptes_par_nature_sur_les_jours_portes_en_arret():
    cal = _calendrier(
        2026,
        11,
        [
            {"jour": 2, "type": "arret_maladie", "arret_type": "maladie_simple"},
            {"jour": 7, "type": "weekend", "arret_type": "maladie_simple"},
            {"jour": 8, "type": "repos", "arret_type": "maladie_simple"},
            {"jour": 16, "type": "arret_maladie", "arret_type": "accident_trajet"},
            {"jour": 17, "type": "arret_at"},
            {"jour": 18, "type": "arret_maladie", "arret_type": "maternite"},
            {"jour": 19, "type": "arret_maladie", "arret_type": "paternite"},
            {"jour": 20, "type": "arret_maladie", "arret_type": "maladie_professionnelle"},
            {"jour": 23, "type": "arret_maladie"},
        ],
    )
    jours = compter_jours_du_calendrier(cal, *NOV)
    # Le 2 et le 23 ; le week-end et le repos marqués de l'arrêt ne comptent pas.
    assert jours["arret_maladie"] == 2.0
    assert jours["arret_at"] == 2.0
    assert jours["arret_maternite"] == 1.0
    assert jours["arret_paternite"] == 1.0
    assert jours["arret_maladie_pro"] == 1.0


def test_absence_non_remuneree_separee_du_sans_solde_et_du_parental():
    cal = _calendrier(
        2026,
        11,
        [
            {"jour": 2, "type": "absence_non_remuneree"},
            {"jour": 3, "type": "absence_non_remuneree"},
            {"jour": 4, "type": "absence_non_remuneree", "motif_absence": "conge_parental_education"},
        ],
    )
    jours = compter_jours_du_calendrier(cal, *NOV, jours_sans_solde={"2026-11-03"})
    assert jours["absence_non_payee"] == 1.0
    assert jours["parental_sans_solde"] == 2.0


def test_la_periode_borne_les_jours():
    cal = _calendrier(2026, 11, [{"jour": d, "type": "conges_payes"} for d in (2, 15, 30)])
    jours = compter_jours_du_calendrier(cal, date(2026, 11, 10), date(2026, 11, 29))
    assert jours["cp"] == 1.0


def test_jtc_et_repos_seniors_viennent_des_demandes_validees():
    demandes = [
        {"type": "jtc", "selected_days": ["2026-11-02", "2026-11-03"], "demi_journees": {"2026-11-03": "matin"}},
        {"type": "repos_senior", "selected_days": ["2026-10-30", "2026-11-05"]},
        # Un CP validé n'est pas recompté : il est déjà au calendrier.
        {"type": "conge_paye", "selected_days": ["2026-11-06"]},
    ]
    jours = compter_jours_des_demandes(demandes, *NOV)
    assert jours["jtc_repos_seniors"] == 2.5
    assert jours["cp"] == 0.0


def test_periode_illisible_inversee_ou_trop_longue():
    with pytest.raises(ValueError):
        lire_periode(None, "2026-11-30")
    with pytest.raises(ValueError):
        lire_periode("2026-11-30", "2026-11-01")
    with pytest.raises(ValueError):
        lire_periode("2025-01-01", "2026-11-30")
    assert lire_periode("2026-11-01", "2026-11-30") == NOV
    assert mois_de_la_periode(date(2026, 11, 15), date(2027, 1, 10)) == [(2026, 11), (2026, 12), (2027, 1)]


def _recap():
    return construire_recap(
        debut=NOV[0],
        fin=NOV[1],
        employes=[
            {"id": E1, "first_name": "Ana", "last_name": "Zed", "matricule": "001", "employment_status": "actif"},
            {"id": E2, "first_name": "Bob", "last_name": "Naissance", "nom_usage": "Usage", "employment_status": "actif"},
            # Sorti sans aucun jour sur la période : pas de ligne.
            {"id": E3, "first_name": "Cid", "last_name": "Parti", "employment_status": "sorti"},
        ],
        calendriers=[
            {"employee_id": E1, "planned_calendar": _calendrier(2026, 11, [{"jour": 2, "type": "conges_payes"}])},
            {"employee_id": E3, "planned_calendar": _calendrier(2026, 11, [{"jour": 2, "type": "travail"}])},
        ],
        demandes_validees=[],
        soldes={E1: {"cp_n1": 3.0, "cp_n": 12.5}},
        date_des_soldes=date(2026, 11, 28),
    )


def test_une_ligne_par_salarie_avec_ses_soldes():
    recap = _recap()
    assert [s["nom"] for s in recap["salaries"]] == ["Usage", "Zed"]
    ana = recap["salaries"][1]
    assert ana["jours"]["cp"] == 1.0 and ana["total_jours"] == 1.0
    assert (ana["solde_cp_n1"], ana["solde_cp_n"]) == (3.0, 12.5)
    # Sans solde calculé (pas de date d'entrée), le solde est dit absent, pas 0.
    assert recap["salaries"][0]["solde_cp_n1"] is None
    assert recap["totaux"]["cp"] == 1.0
    assert recap["aucun_jour"] is False
    assert all(c["source"] for c in recap["colonnes"])


def test_le_fichier_excel_a_une_ligne_par_salarie_un_total_et_ses_sources():
    contenu = app_recap.recap_en_xlsx(_recap())
    classeur = load_workbook(io.BytesIO(contenu))
    assert classeur.sheetnames == ["Récapitulatif", "Sources"]
    feuille = classeur["Récapitulatif"]
    entetes = [c.value for c in feuille[1]]
    assert entetes[:4] == ["Matricule", "Nom", "Prénom", "Congés payés (j)"]
    assert entetes[-2:] == ["Solde CP N-1 (j)", "Solde CP N (j)"]
    lignes = list(feuille.iter_rows(min_row=2, values_only=True))
    assert [l[1] for l in lignes] == ["USAGE", "ZED", "TOTAL"]
    assert lignes[1][3] == 1.0 and lignes[1][-1] == 12.5
    assert classeur["Sources"].max_row >= 15


# ----- Route -----


def _utilisateur(role: str) -> User:
    return User(
        id="dddddddd-4444-4444-4444-444444444444",
        email="rh@societe-a.fr",
        first_name="Rita",
        last_name="Aitch",
        is_platform_admin=False,
        is_group_admin=False,
        accessible_companies=[
            CompanyAccess(company_id=SOCIETE, company_name="Société A", role=role, is_primary=True)
        ],
        active_company_id=SOCIETE,
    )


@pytest.fixture
def lectures(monkeypatch):
    vu: dict = {}

    def employes(cid):
        vu["societe"] = cid
        return [
            {"id": E1, "first_name": "Ana", "last_name": "Zed", "employment_status": "actif"},
            {"id": E2, "first_name": "Bob", "last_name": "Yod", "employment_status": "actif"},
        ]

    def calendriers(ids, d0, d1):
        vu["ids"] = list(ids)
        return [{"employee_id": E1, "planned_calendar": _calendrier(2026, 11, [{"jour": 3, "type": "rtt"}])}]

    monkeypatch.setattr(app_recap, "lire_employes", employes)
    monkeypatch.setattr(app_recap, "lire_calendriers", calendriers)
    monkeypatch.setattr(app_recap, "lire_demandes_validees", lambda ids: [])
    monkeypatch.setattr(app_recap, "lire_soldes_cp", lambda cid: {E1: {"cp_n1": 1.0, "cp_n": 2.0}})
    return vu


def _client(user: User):
    app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(app)


@pytest.fixture(autouse=True)
def _nettoyer():
    yield
    app.dependency_overrides.pop(get_current_user, None)


def test_la_rh_lit_le_recap_de_sa_societe(lectures, monkeypatch):
    from app.modules.access_control.application.service import access_control_service

    monkeypatch.setattr(access_control_service, "filter_allowed_employee_ids", lambda *a, **k: [])
    reponse = _client(_utilisateur("rh")).get(
        "/api/absences/recap-societe", params={"debut": "2026-11-01", "fin": "2026-11-30"}
    )
    assert reponse.status_code == 200, reponse.text
    corps = reponse.json()
    assert lectures["societe"] == SOCIETE
    assert [s["nom"] for s in corps["salaries"]] == ["Yod", "Zed"]
    assert corps["totaux"]["rtt"] == 1.0


def test_un_perimetre_d_equipe_ne_montre_que_ses_salaries(lectures, monkeypatch):
    from app.modules.access_control.application.service import access_control_service

    monkeypatch.setattr(access_control_service, "filter_allowed_employee_ids", lambda *a, **k: [E1])
    reponse = _client(_utilisateur("rh")).get(
        "/api/absences/recap-societe", params={"debut": "2026-11-01", "fin": "2026-11-30"}
    )
    assert reponse.status_code == 200, reponse.text
    assert [s["employee_id"] for s in reponse.json()["salaries"]] == [E1]
    assert lectures["ids"] == [E1]


def test_un_salarie_n_a_pas_acces_au_recap(lectures):
    reponse = _client(_utilisateur("collaborateur")).get(
        "/api/absences/recap-societe", params={"debut": "2026-11-01", "fin": "2026-11-30"}
    )
    assert reponse.status_code == 403


def test_periode_invalide_dite(lectures, monkeypatch):
    from app.modules.access_control.application.service import access_control_service

    monkeypatch.setattr(access_control_service, "filter_allowed_employee_ids", lambda *a, **k: [])
    reponse = _client(_utilisateur("rh")).get(
        "/api/absences/recap-societe", params={"debut": "2026-11-30", "fin": "2026-11-01"}
    )
    assert reponse.status_code == 400
    assert "précède" in reponse.json()["detail"]


def test_l_export_excel_se_telecharge(lectures, monkeypatch):
    from app.modules.access_control.application.service import access_control_service

    monkeypatch.setattr(access_control_service, "filter_allowed_employee_ids", lambda *a, **k: [])
    reponse = _client(_utilisateur("rh")).get(
        "/api/absences/recap-societe/excel", params={"debut": "2026-11-01", "fin": "2026-11-30"}
    )
    assert reponse.status_code == 200, reponse.text
    assert "recap-conges-2026-11-01-2026-11-30.xlsx" in reponse.headers["content-disposition"]
    classeur = load_workbook(io.BytesIO(reponse.content))
    assert classeur["Récapitulatif"].max_row == 4  # en-tête, 2 salariés, total


def test_les_routes_du_recap_passent_avant_la_route_generique():
    from app.modules.absences.api.router import router

    chemins = [r.path for r in router.routes if "GET" in getattr(r, "methods", set())]
    generique = chemins.index("/api/absences/{absence_id}")
    assert chemins.index("/api/absences/recap-societe") < generique
    assert chemins.index("/api/absences/recap-societe/excel") < generique
