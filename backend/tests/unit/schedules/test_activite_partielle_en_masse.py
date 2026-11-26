"""Activité partielle posée en masse (26/11, LEWIS : tous les vendredis).

La règle « quels jours passent, lesquels sont laissés et pourquoi », un salarié
en heures et un forfait jours, la garde société, et l'aperçu qui n'écrit rien.
L'enregistrement passe par `calendar_edit.save_calendar`, le chemin du
calendrier d'un salarié.
"""

from __future__ import annotations

from datetime import date
from unittest.mock import Mock

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.core.security import get_current_user
from app.modules.activite_partielle.domain.calendrier import jours_chomes
from app.modules.schedules.api import router as routes
from app.modules.schedules.application import activite_partielle_en_masse as service
from app.modules.schedules.application.exceptions import ScheduleAppError
from app.modules.schedules.domain.activite_partielle_en_masse import (
    RAISON_ABSENCE,
    RAISON_BULLETIN_VALIDE,
    RAISON_DEJA_AP,
    RAISON_ECHEC,
    RAISON_HEURES_SAISIES,
    RAISON_HORS_CONTRAT,
    RAISON_REPOS,
    TYPE_AP,
    ContexteSalarie,
    decompte,
    juger_le_mois,
    raison_de_laisser,
)
from app.modules.users.schemas.responses import CompanyAccess, User

SOCIETE = "11111111-1111-1111-1111-111111111111"
AUTRE_SOCIETE = "99999999-9999-9999-9999-999999999999"
EN_HEURES = "aaaaaaaa-0000-0000-0000-000000000001"
AU_FORFAIT = "aaaaaaaa-0000-0000-0000-000000000002"
REVISION = "00000000-0000-0000-0000-000000000001"

# Décembre 2026 : vendredis 4, 11, 18 et 25 (Noël, férié).
VENDREDIS = [date(2026, 12, 4), date(2026, 12, 11), date(2026, 12, 18), date(2026, 12, 25)]
NOEL = date(2026, 12, 25)


def _travail(jour, heures=7.0):
    return {"jour": jour, "type": "travail", "heures_prevues": heures}


# ----- La règle, jour par jour -----


class TestRaisonDeLaisser:
    ctx = ContexteSalarie(feries=frozenset({NOEL}))

    def test_un_jour_de_travail_passe(self):
        assert raison_de_laisser(date(2026, 12, 4), _travail(4), None, self.ctx) is None

    def test_un_jour_sans_planning_en_semaine_passe(self):
        assert raison_de_laisser(date(2026, 12, 4), None, None, self.ctx) is None

    def test_un_week_end_sans_planning_est_laisse(self):
        assert raison_de_laisser(date(2026, 12, 5), None, None, self.ctx) == RAISON_REPOS

    def test_un_ferie_est_laisse_meme_type_travail(self):
        assert raison_de_laisser(NOEL, None, None, self.ctx) == RAISON_REPOS
        assert raison_de_laisser(NOEL, _travail(25), None, self.ctx) == RAISON_REPOS

    @pytest.mark.parametrize("type_jour", ["weekend", "repos", "ferie"])
    def test_repos_week_end_ferie_au_planning(self, type_jour):
        prevu = {"jour": 4, "type": type_jour, "heures_prevues": 0}
        assert raison_de_laisser(date(2026, 12, 4), prevu, None, self.ctx) == RAISON_REPOS

    def test_zero_heure_prevue_est_un_repos(self):
        # Temps partiel : le vendredi à 0 h n'avait rien à chômer.
        assert raison_de_laisser(date(2026, 12, 4), _travail(4, 0), None, self.ctx) == RAISON_REPOS

    @pytest.mark.parametrize(
        "type_jour",
        ["arret_maladie", "conges_payes", "rtt", "conge", "absence_non_remuneree", "ecole", "absent_a_typer"],
    )
    def test_une_absence_est_laissee(self, type_jour):
        prevu = {"jour": 4, "type": type_jour, "heures_prevues": None}
        assert raison_de_laisser(date(2026, 12, 4), prevu, None, self.ctx) == RAISON_ABSENCE

    def test_un_jour_issu_d_une_absence_validee_est_laisse(self):
        prevu = {**_travail(4), "origine": "absence"}
        assert raison_de_laisser(date(2026, 12, 4), prevu, None, self.ctx) == RAISON_ABSENCE

    def test_un_jour_couvert_par_un_arret_valide_est_laisse(self):
        ctx = ContexteSalarie(jours_d_arret=frozenset({date(2026, 12, 4)}))
        assert raison_de_laisser(date(2026, 12, 4), _travail(4), None, ctx) == RAISON_ABSENCE

    def test_deja_en_activite_partielle(self):
        prevu = {"jour": 4, "type": TYPE_AP, "heures_prevues": 7}
        assert raison_de_laisser(date(2026, 12, 4), prevu, None, self.ctx) == RAISON_DEJA_AP

    def test_bulletin_du_mois_valide(self):
        ctx = ContexteSalarie(mois_figes=frozenset({(2026, 12)}))
        assert raison_de_laisser(date(2026, 12, 4), _travail(4), None, ctx) == RAISON_BULLETIN_VALIDE

    def test_hors_contrat(self):
        ctx = ContexteSalarie(entree=date(2026, 12, 10), sortie=date(2026, 12, 15))
        assert raison_de_laisser(date(2026, 12, 4), _travail(4), None, ctx) == RAISON_HORS_CONTRAT
        assert raison_de_laisser(date(2026, 12, 18), _travail(18), None, ctx) == RAISON_HORS_CONTRAT
        assert raison_de_laisser(date(2026, 12, 11), _travail(11), None, ctx) is None
        assert raison_de_laisser(date(2026, 12, 15), _travail(15), None, ctx) is None

    def test_des_heures_faites_deja_saisies_ne_sont_jamais_ecrasees(self):
        reel = {"jour": 4, "type": "travail", "heures_faites": 7}
        assert raison_de_laisser(date(2026, 12, 4), _travail(4), reel, self.ctx) == RAISON_HEURES_SAISIES
        assert raison_de_laisser(date(2026, 12, 4), _travail(4), {**reel, "heures_faites": 0}, self.ctx) is None


# ----- Le mois d'un salarié en heures et d'un forfait jours -----


class TestJugerLeMois:
    def test_salarie_en_heures_comme_au_calendrier(self):
        prevu = [_travail(4), _travail(11, 7.5), {"jour": 18, "type": "conges_payes", "heures_prevues": None}]
        reel = [{"jour": 3, "type": "travail", "heures_faites": 7, "debut": "08:00", "fin": "15:00"}]
        res = juger_le_mois(2026, 12, VENDREDIS, prevu, reel, ContexteSalarie(feries=frozenset({NOEL})))

        assert res.passes == [date(2026, 12, 4), date(2026, 12, 11)]
        assert res.laisses == [(date(2026, 12, 18), RAISON_ABSENCE), (NOEL, RAISON_REPOS)]
        # Prévu : les heures prévues restent, ce sont les heures chômées.
        assert res.prevu_a_ecrire == [
            {"jour": 4, "type": TYPE_AP, "heures_prevues": 7.0},
            {"jour": 11, "type": TYPE_AP, "heures_prevues": 7.5},
        ]
        # Réel : le mois entier, le jour d'avant intact (horaires pointés compris).
        assert res.reel_a_ecrire == [
            reel[0],
            {"jour": 4, "type": TYPE_AP, "heures_faites": 0},
            {"jour": 11, "type": TYPE_AP, "heures_faites": 0},
        ]
        # Le bulletin en tire les heures chômées comme d'un jour posé à la main.
        chomes = jours_chomes(res.prevu_a_ecrire, res.reel_a_ecrire, forfait_jours=False, heures_par_jour=7)
        assert [(j.jour, j.heures) for j in chomes] == [(4, 7.0), (11, 7.5)]

    def test_forfait_jours_compte_en_jours(self):
        ctx = ContexteSalarie(forfait_jours=True, feries=frozenset({NOEL}))
        prevu = [{"jour": 4, "type": "travail", "heures_prevues": 1}, {"jour": 11, "type": "travail", "heures_prevues": 0}]
        res = juger_le_mois(2026, 12, VENDREDIS, prevu, [], ctx)

        # Le 18 n'a pas de planning : une journée, comme l'écran l'affiche.
        assert res.passes == [date(2026, 12, 4), date(2026, 12, 18)]
        assert (date(2026, 12, 11), RAISON_REPOS) in res.laisses  # jour non prévu
        assert res.prevu_a_ecrire == [
            {"jour": 4, "type": TYPE_AP, "heures_prevues": 1},
            {"jour": 18, "type": TYPE_AP, "heures_prevues": 1.0},
        ]
        assert [e["heures_faites"] for e in res.reel_a_ecrire] == [0, 0]
        chomes = jours_chomes(res.prevu_a_ecrire, res.reel_a_ecrire, forfait_jours=True, heures_par_jour=7)
        assert [(j.jour, j.heures) for j in chomes] == [(4, 7.0), (18, 7.0)]

    def test_rien_a_ecrire_quand_tout_est_laisse(self):
        ctx = ContexteSalarie(mois_figes=frozenset({(2026, 12)}))
        res = juger_le_mois(2026, 12, VENDREDIS, [], [], ctx)
        assert res.passes == [] and res.prevu_a_ecrire == [] and res.reel_a_ecrire == []
        assert decompte(res.laisses) == {RAISON_BULLETIN_VALIDE: 4}

    def test_seules_les_dates_du_mois_sont_jugees(self):
        res = juger_le_mois(2026, 12, [date(2026, 11, 27), date(2026, 12, 4)], [], [], ContexteSalarie())
        assert res.passes == [date(2026, 12, 4)]


# ----- Le service : garde société, aperçu sans écriture, enregistrement -----


SALARIES = {
    EN_HEURES: {"id": EN_HEURES, "first_name": "A", "last_name": "Heures", "statut": "Non-Cadre",
                "is_forfait_jour": False, "hire_date": "2020-01-01", "company_id": SOCIETE},
    AU_FORFAIT: {"id": AU_FORFAIT, "first_name": "B", "last_name": "Forfait", "statut": "Cadre",
                 "is_forfait_jour": True, "hire_date": "2020-01-01", "company_id": SOCIETE},
}

PLANNINGS = {
    EN_HEURES: {"planned_calendar": {"calendrier_prevu": [_travail(4), _travail(11)]},
                "actual_hours": {"calendrier_reel": [{"jour": 11, "type": "travail", "heures_faites": 4}]}},
    AU_FORFAIT: {"planned_calendar": {"calendrier_prevu": [{"jour": 4, "type": "travail", "heures_prevues": 1}]},
                 "actual_hours": {"calendrier_reel": []}},
}


@pytest.fixture
def lectures(monkeypatch):
    """Toutes les lectures du service, en mémoire ; toute écriture est tracée."""
    etat = {"saves": [], "figes": {}, "actif": True}

    def salaries_de_la_societe(company_id, ids):
        return {i: SALARIES[i] for i in ids if i in SALARIES and company_id == SOCIETE}

    monkeypatch.setattr(service.lectures, "salaries_de_la_societe", salaries_de_la_societe)
    monkeypatch.setattr(service.lectures, "mois_figes", lambda ids, mois: etat["figes"])
    monkeypatch.setattr(service.arrets_valides_reader, "par_salarie", lambda ids, d, f: {})
    monkeypatch.setattr(service, "observed_holiday_dates_for_month", lambda a, m, c: {NOEL} if m == 12 else set())
    monkeypatch.setattr(service, "_sortie", lambda e: None)
    monkeypatch.setattr(
        service.schedule_repository, "list_schedules_for_employees",
        lambda ids, a, m: {i: PLANNINGS[i] for i in ids} if (a, m) == (2026, 12) else {},
    )
    monkeypatch.setattr(service, "_reglage_actif", lambda cid: _reglage(etat))

    def snapshot(eid, cid, a, m):
        p = PLANNINGS[eid] if (a, m) == (2026, 12) else {}
        return {"revision": REVISION, "busy": False,
                "calendrier_prevu": (p.get("planned_calendar") or {}).get("calendrier_prevu", []),
                "calendrier_reel": (p.get("actual_hours") or {}).get("calendrier_reel", [])}

    monkeypatch.setattr(service.calendar_edit, "get_snapshot", snapshot)
    monkeypatch.setattr(
        service.calendar_edit, "save_calendar",
        Mock(side_effect=lambda eid, cid, payload: etat["saves"].append((eid, cid, payload)) or {}),
    )
    return etat


def _reglage(etat):
    if not etat["actif"]:
        raise ScheduleAppError("validation", "L'activité partielle n'est pas activée pour cette société (Paramètres, Paie).", 400)
    return {"active": True, "date_debut": "2026-12-01", "date_fin": "2026-12-31"}


class TestService:
    def test_garde_societe_un_salarie_d_ailleurs_refuse_tout(self, lectures):
        with pytest.raises(ScheduleAppError) as exc:
            service.apercu(SOCIETE, [EN_HEURES, "bbbbbbbb-0000-0000-0000-000000000009"], VENDREDIS)
        assert exc.value.status_code == 404
        with pytest.raises(ScheduleAppError):
            service.appliquer(AUTRE_SOCIETE, [EN_HEURES], VENDREDIS)
        assert lectures["saves"] == []

    def test_l_apercu_n_ecrit_rien_et_compte(self, lectures):
        res = service.apercu(SOCIETE, [EN_HEURES, AU_FORFAIT], VENDREDIS)

        assert lectures["saves"] == []
        assert res["enregistre"] is False
        # En heures : 4 passe, 11 a des heures faites, 18 sans planning passe, 25 férié.
        # Forfait : 4, 11 et 18 passent, 25 férié.
        assert res["total_passes"] == 5
        assert res["laisses_par_raison"] == {RAISON_REPOS: 2, RAISON_HEURES_SAISIES: 1}
        par_id = {s["employee_id"]: s for s in res["salaries"]}
        assert par_id[EN_HEURES]["passes"] == ["2026-12-04", "2026-12-18"]
        assert par_id[AU_FORFAIT]["forfait_jours"] is True
        assert res["avertissement"] is None

    def test_l_enregistrement_passe_par_le_calendrier_du_salarie(self, lectures):
        res = service.appliquer(SOCIETE, [EN_HEURES, AU_FORFAIT], VENDREDIS)

        assert res["enregistre"] is True and res["total_passes"] == 5
        sauves = {eid: payload for eid, _, payload in lectures["saves"]}
        assert set(sauves) == {EN_HEURES, AU_FORFAIT}
        heures = sauves[EN_HEURES]
        assert (heures.year, heures.month, str(heures.expected_revision)) == (2026, 12, REVISION)
        assert heures.recalculate_payroll is True
        assert [(e.jour, e.type, e.heures_prevues) for e in heures.calendrier_prevu] == [
            (4, TYPE_AP, 7.0), (18, TYPE_AP, None)]
        # Le jour 11 aux heures faites reste tel quel dans le réel renvoyé.
        assert [(e.jour, e.type, e.heures_faites) for e in heures.calendrier_reel] == [
            (4, TYPE_AP, 0), (11, "travail", 4), (18, TYPE_AP, 0)]
        forfait = sauves[AU_FORFAIT]
        assert [(e.jour, e.heures_prevues) for e in forfait.calendrier_prevu] == [(4, 1), (11, 1.0), (18, 1.0)]

    def test_un_mois_au_bulletin_valide_n_est_pas_ecrit(self, lectures):
        lectures["figes"] = {EN_HEURES: {(2026, 12)}}
        res = service.appliquer(SOCIETE, [EN_HEURES], VENDREDIS)
        assert lectures["saves"] == []
        assert res["total_passes"] == 0
        assert res["laisses_par_raison"] == {RAISON_BULLETIN_VALIDE: 4}

    def test_un_echec_laisse_les_jours_du_mois_et_le_dit(self, lectures, monkeypatch):
        def refuse(eid, cid, payload):
            raise ScheduleAppError("calendar_busy", "Une saisie est en cours.", 409)

        monkeypatch.setattr(service.calendar_edit, "save_calendar", refuse)
        res = service.appliquer(SOCIETE, [EN_HEURES], VENDREDIS)
        assert res["total_passes"] == 0
        assert res["laisses_par_raison"][RAISON_ECHEC] == 2
        assert res["salaries"][0]["erreurs"] == ["12/2026 : Une saisie est en cours."]

    def test_activite_partielle_non_activee(self, lectures):
        lectures["actif"] = False
        with pytest.raises(ScheduleAppError) as exc:
            service.apercu(SOCIETE, [EN_HEURES], VENDREDIS)
        assert exc.value.status_code == 400


def test_avertissement_des_dates_hors_periode():
    reglage = {"date_debut": "2026-12-05", "date_fin": None}
    phrase = service.avertissement_periode(reglage, VENDREDIS)
    assert phrase is not None and phrase.startswith("1 date est hors")
    assert "à partir du 05/12/2026" in phrase
    assert service.avertissement_periode({"date_debut": None, "date_fin": None}, VENDREDIS) is None


# ----- Les routes : profil RH, garde de chaque salarié -----


def _utilisateur(role: str) -> User:
    return User(
        id="22222222-2222-2222-2222-222222222222",
        email="rh@entreprise.fr",
        first_name="R",
        last_name="H",
        is_platform_admin=False,
        is_group_admin=False,
        accessible_companies=[CompanyAccess(company_id=SOCIETE, company_name="Entreprise", role=role, is_primary=True)],
        active_company_id=SOCIETE,
    )


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(routes.router_rh)
    yield app
    app.dependency_overrides.clear()


CORPS = {"employee_ids": [EN_HEURES], "dates": ["2026-12-04"]}


@pytest.mark.parametrize("chemin", ["/api/schedules/activite-partielle-en-masse/apercu",
                                    "/api/schedules/activite-partielle-en-masse"])
def test_un_collaborateur_est_refuse(client, chemin, monkeypatch):
    client.dependency_overrides[get_current_user] = lambda: _utilisateur("collaborateur")
    appel = Mock()
    monkeypatch.setattr(routes.activite_partielle_en_masse, "apercu", appel)
    monkeypatch.setattr(routes.activite_partielle_en_masse, "appliquer", appel)
    assert TestClient(client).post(chemin, json=CORPS).status_code == 403
    appel.assert_not_called()


def test_la_garde_de_chaque_salarie_est_celle_du_calendrier(client, monkeypatch):
    client.dependency_overrides[get_current_user] = lambda: _utilisateur("rh")
    vus = []

    def garde(user, company_id, permission, employee_id):
        vus.append((company_id, permission, employee_id))
        raise HTTPException(status_code=404, detail="Ressource introuvable")

    monkeypatch.setattr(routes.access_control_service, "require_employee_access", garde)
    appel = Mock()
    monkeypatch.setattr(routes.activite_partielle_en_masse, "appliquer", appel)
    reponse = TestClient(client).post("/api/schedules/activite-partielle-en-masse", json=CORPS)
    assert reponse.status_code == 404
    assert vus == [(SOCIETE, "schedules.update", EN_HEURES)]
    appel.assert_not_called()


def test_l_apercu_rend_le_decompte(client, monkeypatch):
    client.dependency_overrides[get_current_user] = lambda: _utilisateur("rh")
    monkeypatch.setattr(routes.access_control_service, "require_employee_access", lambda *a, **k: None)
    monkeypatch.setattr(
        routes.activite_partielle_en_masse, "apercu",
        lambda cid, ids, dates: {"enregistre": False, "total_passes": len(dates), "ids": ids, "societe": cid},
    )
    reponse = TestClient(client).post("/api/schedules/activite-partielle-en-masse/apercu", json=CORPS)
    assert reponse.status_code == 200
    assert reponse.json() == {"enregistre": False, "total_passes": 1, "ids": [EN_HEURES], "societe": SOCIETE}
