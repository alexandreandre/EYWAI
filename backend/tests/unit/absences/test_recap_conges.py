"""Récapitulatif des congés de la société (lot L21, demande du 27/11).

Une ligne par salarié : jours de la période comptés sur le calendrier de paie
(CP, RTT, absences, arrêts par nature), JTC et repos seniors sur les demandes
validées, soldes CP calculés comme la fiche salarié. Lecture seule de bout en
bout : aucune écriture ne part. Route RH seulement, périmètre d'équipes
respecté, export Excel lisible.
"""

from __future__ import annotations

import io
from datetime import date

import pytest
from fastapi.testclient import TestClient
from openpyxl import load_workbook

from app.core.lecture_seule import ecritures_permises
from app.core.security import get_current_user
from app.main import app
from app.modules.absences.application import recap_conges as app_recap
from app.modules.absences.domain.cp_seniority import CpSenioritySettings
from app.modules.absences.domain.leave_policy import DEFAULT_LEAVE_POLICY
from app.modules.absences.domain.recap_conges import (
    compter_jours_des_demandes,
    compter_jours_du_calendrier,
    construire_recap,
    jours_des_demandes,
    lire_periode,
    mois_de_la_periode,
)
from app.modules.users.schemas.responses import CompanyAccess, User

pytestmark = pytest.mark.unit

SOCIETE = "aaaaaaaa-1111-1111-1111-111111111111"
E1 = "e1000000-0000-0000-0000-000000000001"
E2 = "e2000000-0000-0000-0000-000000000002"
E3 = "e3000000-0000-0000-0000-000000000003"
E4 = "e4000000-0000-0000-0000-000000000004"

NOV = date(2026, 11, 1), date(2026, 11, 30)


def _calendrier(annee: int, mois: int, jours: list[dict]) -> dict:
    return {"periode": {"annee": annee, "mois": mois}, "calendrier_prevu": jours}


def _compter(jours: list[dict], demandes: list[dict] | None = None, periode=NOV) -> dict:
    return compter_jours_du_calendrier(
        _calendrier(2026, 11, jours), *periode, demandes=jours_des_demandes(demandes or [])
    )


def test_le_calendrier_donne_cp_rtt_et_demi_journees():
    jours = _compter(
        [
            {"jour": 2, "type": "conges_payes"},
            {"jour": 3, "type": "conges_payes", "quotite_absence": 0.5},
            {"jour": 4, "type": "rtt"},
            {"jour": 5, "type": "travail", "heures_prevues": 7},
            {"jour": 6, "type": "repos"},
            {"jour": 9, "type": "conge"},
            {"jour": 10, "type": "evenement_familial"},
            {"jour": 12, "type": "activite_partielle"},
            {"jour": 13, "type": "absence_justifiee"},
        ]
    )
    assert jours["cp"] == 1.5
    assert jours["rtt"] == 1.0
    assert jours["repos_recup"] == 1.0
    assert jours["evenement_familial"] == 1.0
    assert jours["activite_partielle"] == 1.0
    assert jours["absence_justifiee"] == 1.0
    # Ni le travail ni le repos hebdomadaire ne sont des absences.
    assert sum(jours.values()) == 6.5


def test_un_mois_sans_periode_est_lu_par_l_annee_et_le_mois_de_la_ligne():
    """132 lignes de calendrier n'ont pas de `periode` (écrites à la validation d'une absence)."""
    sans_periode = {"calendrier_prevu": [{"jour": 2, "type": "conges_payes"}, {"jour": 3, "type": "rtt"}]}
    jours = compter_jours_du_calendrier(sans_periode, *NOV, annee=2026, mois=11)
    assert jours["cp"] == 1.0 and jours["rtt"] == 1.0
    # L'année et le mois de la ligne priment sur une `periode` contraire.
    jours = compter_jours_du_calendrier(_calendrier(2025, 1, [{"jour": 2, "type": "rtt"}]), *NOV, annee=2026, mois=11)
    assert jours["rtt"] == 1.0


def test_une_absence_de_quelques_heures_compte_sa_part_de_journee():
    jours = _compter(
        [
            {"jour": 2, "type": "travail", "heures_prevues": 7.5},
            {"jour": 3, "type": "travail", "heures_prevues": 7.5},
            {"jour": 4, "type": "absence_non_remuneree", "heures": 3.75, "heures_prevues": 3.75},
            # Journée entière : 0 h retenue au calendrier (sans solde) ou la journée.
            {"jour": 5, "type": "absence_non_remuneree", "heures_prevues": 0},
            {"jour": 6, "type": "absence_non_remuneree", "heures_prevues": 7.5},
            # La quotité posée par le serveur prime.
            {"jour": 9, "type": "absence_justifiee", "heures_prevues": 7.5, "quotite_absence": 0.2},
        ]
    )
    assert jours["absence_non_payee"] == 2.5
    assert jours["absence_justifiee"] == 0.2


def test_les_arrets_sont_comptes_par_nature_sur_les_jours_portes_en_arret():
    jours = _compter(
        [
            {"jour": 2, "type": "arret_maladie", "arret_type": "maladie_simple"},
            {"jour": 7, "type": "weekend", "arret_type": "maladie_simple"},
            {"jour": 8, "type": "repos", "arret_type": "maladie_simple"},
            {"jour": 16, "type": "arret_maladie", "arret_type": "accident_trajet"},
            {"jour": 17, "type": "arret_at"},
            {"jour": 18, "type": "arret_maladie", "arret_type": "maternite"},
            {"jour": 19, "type": "arret_maladie", "arret_type": "paternite"},
            {"jour": 20, "type": "arret_maladie", "arret_type": "maladie_professionnelle"},
        ]
    )
    # Le 2 seulement : le week-end et le repos marqués de l'arrêt ne comptent pas.
    assert jours["arret_maladie"] == 1.0
    assert jours["arret_at"] == 2.0
    assert jours["arret_maternite"] == 1.0
    assert jours["arret_paternite"] == 1.0
    assert jours["arret_maladie_pro"] == 1.0
    assert jours["arret_non_precise"] == 0.0


def test_la_nature_de_l_arret_suit_la_demande_validee_sinon_non_precisee():
    demandes = [
        {"type": "arret_paternite", "arret_type": "adoption", "selected_days": ["2026-11-02"]},
        {"type": "arret_maternite", "arret_type": "conge_supplementaire_naissance", "selected_days": ["2026-11-03"]},
        {"type": "arret_at", "arret_type": None, "selected_days": ["2026-11-04"]},
    ]
    jours = _compter(
        [
            {"jour": 2, "type": "arret_maladie", "arret_type": "adoption"},
            {"jour": 3, "type": "arret_maladie", "arret_type": "conge_supplementaire_naissance"},
            {"jour": 4, "type": "arret_maladie"},
            # Sans demande ni type d'arrêt : la nature n'est pas devinée.
            {"jour": 5, "type": "arret_maladie"},
            {"jour": 6, "type": "arret_maladie", "arret_type": "adoption"},
        ],
        demandes,
    )
    assert jours["arret_paternite"] == 1.0
    assert jours["arret_maternite"] == 1.0
    assert jours["arret_at"] == 1.0
    assert jours["arret_maladie"] == 0.0
    assert jours["arret_non_precise"] == 2.0


def test_absence_non_remuneree_separee_du_sans_solde_et_du_parental():
    jours = _compter(
        [
            {"jour": 2, "type": "absence_non_remuneree"},
            {"jour": 3, "type": "absence_non_remuneree"},
            {"jour": 4, "type": "absence_non_remuneree", "motif_absence": "conge_parental_education"},
        ],
        [{"type": "sans_solde", "selected_days": ["2026-11-03"]}],
    )
    assert jours["absence_non_payee"] == 1.0
    assert jours["parental_sans_solde"] == 2.0


def test_la_recuperation_de_modulation_va_en_repos_et_pas_en_conges_payes():
    jours = _compter(
        [{"jour": 2, "type": "conges_payes"}, {"jour": 3, "type": "conges_payes"}],
        [{"type": "recuperation_modulation", "selected_days": ["2026-11-03"]}],
    )
    assert jours["cp"] == 1.0
    assert jours["repos_recup"] == 1.0


def test_la_periode_borne_les_jours():
    jours = _compter(
        [{"jour": d, "type": "conges_payes"} for d in (2, 15, 30)],
        periode=(date(2026, 11, 10), date(2026, 11, 29)),
    )
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


def _ligne_cal(eid: str, jours: list[dict]) -> dict:
    return {"employee_id": eid, "year": 2026, "month": 11, "planned_calendar": _calendrier(2026, 11, jours)}


def _recap():
    return construire_recap(
        debut=NOV[0],
        fin=NOV[1],
        employes=[
            {"id": E1, "first_name": "Ana", "last_name": "Zed", "matricule": "001", "employment_status": "actif"},
            {"id": E2, "first_name": "Bob", "last_name": "Naissance", "nom_usage": "Usage", "employment_status": "actif"},
            # Parti sans aucun jour sur la période : pas de ligne.
            {"id": E3, "first_name": "Cid", "last_name": "Parti", "employment_status": "parti"},
            # En sortie : présent, même sans jour (solde de tout compte).
            {"id": E4, "first_name": "Dan", "last_name": "Sortant", "employment_status": "en_sortie"},
        ],
        calendriers=[
            _ligne_cal(E1, [{"jour": 2, "type": "conges_payes"}]),
            _ligne_cal(E3, [{"jour": 2, "type": "travail"}]),
        ],
        demandes_validees=[],
        soldes={E1: {"cp_n1": 3.0, "cp_n": 12.5}, E4: {"cp_n1": 0.0, "cp_n": 4.0}},
        date_des_soldes=date(2026, 11, 28),
        reprises={E2: date(2026, 11, 15), E1: date(2026, 6, 30)},
    )


def test_une_ligne_par_salarie_avec_ses_soldes():
    recap = _recap()
    assert [s["nom"] for s in recap["salaries"]] == ["Sortant", "Usage", "Zed"]
    ana = recap["salaries"][2]
    assert ana["jours"]["cp"] == 1.0 and ana["total_jours"] == 1.0
    assert (ana["solde_cp_n1"], ana["solde_cp_n"]) == (3.0, 12.5)
    assert recap["salaries"][0]["solde_cp_n"] == 4.0
    # Sans solde calculé (pas de date d'entrée), le solde est dit absent, pas 0.
    assert recap["salaries"][1]["solde_cp_n1"] is None
    assert recap["totaux"]["cp"] == 1.0
    assert recap["aucun_jour"] is False
    assert all(c["source"] for c in recap["colonnes"])


def test_une_reprise_dans_la_periode_est_signalee_sur_la_ligne():
    recap = _recap()
    par_nom = {s["nom"]: s for s in recap["salaries"]}
    assert par_nom["Usage"]["reprise_au"] == "2026-11-15"
    # Une reprise avant la période ne touche pas ses chiffres.
    assert par_nom["Zed"]["reprise_au"] is None
    assert "solde repris" in recap["note_reprise"]


def test_le_fichier_excel_a_une_ligne_par_salarie_un_total_et_ses_sources():
    contenu = app_recap.recap_en_xlsx(_recap())
    classeur = load_workbook(io.BytesIO(contenu))
    assert classeur.sheetnames == ["Récapitulatif", "Sources"]
    feuille = classeur["Récapitulatif"]
    entetes = [c.value for c in feuille[1]]
    assert entetes[:4] == ["Matricule", "Nom", "Prénom", "Congés payés (j)"]
    assert entetes[-3:] == ["Solde CP N-1 (j)", "Solde CP N (j)", "Reprise dans Martine"]
    lignes = list(feuille.iter_rows(min_row=2, values_only=True))
    assert [l[1] for l in lignes] == ["SORTANT", "USAGE", "ZED", "TOTAL"]
    assert lignes[2][3] == 1.0 and lignes[2][-2] == 12.5
    assert lignes[1][-1] == "2026-11-15"
    assert classeur["Sources"].max_row >= 15


# ----- Lecture seule -----


@pytest.fixture
def lectures(monkeypatch):
    vu: dict = {"ecritures_permises": []}

    def note():
        vu["ecritures_permises"].append(ecritures_permises())

    def employes(cid):
        note()
        vu["societe"] = cid
        return [
            {"id": E1, "first_name": "Ana", "last_name": "Zed", "employment_status": "actif", "hire_date": "2024-01-01"},
            {"id": E2, "first_name": "Bob", "last_name": "Yod", "employment_status": "en_sortie", "hire_date": "2023-05-01"},
            {"id": E3, "first_name": "Cid", "last_name": "Parti", "employment_status": "parti", "hire_date": "2020-01-01"},
        ]

    def calendriers(ids, d0, d1):
        note()
        vu["ids"] = list(ids)
        return [_ligne_cal(E1, [{"jour": 3, "type": "rtt"}])]

    def demandes(ids):
        note()
        vu["ids_soldes"] = list(ids)
        return []

    def politique(cid):
        note()
        return DEFAULT_LEAVE_POLICY

    def ajustements(ids, annee):
        note()
        vu["ids_ajustements"] = list(ids)
        return {}

    def interdit(*_a, **_k):
        raise AssertionError("le récapitulatif ne doit rien écrire ni passer par l'aperçu qui écrit")

    monkeypatch.setattr(app_recap, "lire_employes", employes)
    monkeypatch.setattr(app_recap, "lire_calendriers", calendriers)
    monkeypatch.setattr(app_recap, "lire_demandes_validees", demandes)
    monkeypatch.setattr(app_recap, "lire_reprises", lambda ids: (note(), {})[1])
    monkeypatch.setattr(app_recap, "get_leave_policy", politique)
    # Ancienneté active : l'ancien chemin aurait enregistré le droit de chaque salarié.
    monkeypatch.setattr(app_recap, "get_cp_seniority_settings", lambda cid: (note(), CpSenioritySettings(enabled=True))[1])
    monkeypatch.setattr(app_recap, "get_applicable_adjustments_by_employees", ajustements)

    from app.modules.absences.application import cp_seniority_queries, leave_settings_queries
    from app.modules.absences.infrastructure import cp_seniority_repository

    monkeypatch.setattr(cp_seniority_repository, "upsert_cp_seniority_grant", interdit)
    monkeypatch.setattr(cp_seniority_queries, "compute_and_persist_grant", interdit)
    monkeypatch.setattr(leave_settings_queries, "get_leave_balances_overview", interdit)
    return vu


def test_le_recap_lit_tout_en_lecture_seule_et_n_enregistre_aucun_droit(lectures):
    recap = app_recap.get_recap_conges(SOCIETE, *NOV, None)
    assert lectures["ecritures_permises"] and not any(lectures["ecritures_permises"])
    assert {s["employee_id"] for s in recap["salaries"]} == {E1, E2}
    # Soldes calculés pour les présents du périmètre, en sortie compris ; pas pour un parti.
    assert set(lectures["ids_ajustements"]) == {E1, E2}
    assert all(s["solde_cp_n"] is not None for s in recap["salaries"])


def test_les_soldes_suivent_le_perimetre(lectures):
    recap = app_recap.get_recap_conges(SOCIETE, *NOV, {E1})
    assert [s["employee_id"] for s in recap["salaries"]] == [E1]
    assert lectures["ids"] == [E1]
    assert lectures["ids_ajustements"] == [E1]


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


def _client(user: User):
    app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture(autouse=True)
def _nettoyer():
    yield
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def sans_equipes(monkeypatch):
    from app.modules.access_control.application.service import access_control_service

    monkeypatch.setattr(access_control_service, "filter_allowed_employee_ids", lambda *a, **k: [])


def test_la_rh_lit_le_recap_de_sa_societe(lectures, sans_equipes):
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


def test_periode_invalide_dite(lectures, sans_equipes):
    reponse = _client(_utilisateur("rh")).get(
        "/api/absences/recap-societe", params={"debut": "2026-11-30", "fin": "2026-11-01"}
    )
    assert reponse.status_code == 400
    assert "précède" in reponse.json()["detail"]


def test_une_erreur_de_calcul_n_est_pas_deguisee_en_periode_invalide(lectures, sans_equipes, monkeypatch):
    def casse(*_a, **_k):
        raise ValueError("valeur illisible en base")

    monkeypatch.setattr(app_recap, "lire_calendriers", casse)
    reponse = _client(_utilisateur("rh")).get(
        "/api/absences/recap-societe", params={"debut": "2026-11-01", "fin": "2026-11-30"}
    )
    assert reponse.status_code == 500


def test_l_export_excel_se_telecharge(lectures, sans_equipes):
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
