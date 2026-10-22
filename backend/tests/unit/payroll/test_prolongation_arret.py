"""Prolongation d'arrêt : pas de nouvelle carence, le maintien continue à son rang.

[F11] (enquête F du 10/10/2026) : chaque demande validée porte son propre début
(`date_debut_arret_reel` = premier jour de la demande). Une prolongation saisie
comme seconde demande repartait donc de zéro : 3 jours de carence de la
Sécurité sociale, 7 jours de carence employeur, et le rang du maintien remis à
un (droits jamais épuisés).

Règles (service-public F3053, vérifiée le 01/06/2026, ouverte le 12/10/2026) :
- « Le délai de carence s'applique à chaque arrêt de travail. […] Il n'y a pas
  de délai de carence en cas de reprise d'activité entre 2 arrêts de travail
  n'ayant pas dépassé 48 heures. » : une seconde demande contiguë, ou qui
  commence au plus tard trois jours après la fin de la précédente (deux jours
  de reprise au plus), prolonge l'arrêt ;
- carence employeur de 7 jours « pour chaque arrêt de travail » : une
  prolongation n'est pas un nouvel arrêt.

[F11-bis] Deux arrêts distincts du même mois étaient fusionnés en un seul, du
premier jour du premier au dernier jour du second : les jours travaillés entre
les deux comptaient comme jours d'arrêt, et la carence payée de la plasturgie
(3 jours par an, Colorplast) était perdue, l'arrêt fusionné n'existant dans
aucun calendrier.

Le pliant « Maintien & subrogation » lit la même chaîne que le bulletin.
"""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pytest

from app.modules.payroll.engine.maintien_salaire_service import calculer_maintien

pytestmark = pytest.mark.unit


def _d(iso: str) -> date:
    return date.fromisoformat(iso)


# --- La chaîne, seule -------------------------------------------------------


def _chainer(debut, fin, type_arret, autres):
    from app.modules.payroll.engine.prolongation_arret import chainer_arret

    return chainer_arret(_d(debut), _d(fin), type_arret, autres)


def _connu(debut, fin, type_arret="maladie_simple"):
    return {"debut": debut, "fin": fin, "type": type_arret}


def test_une_demande_contigue_prolonge_l_arret_et_compte_ses_jours():
    debut, jours = _chainer(
        "2026-10-01", "2026-10-31", "maladie_simple",
        [_connu("2026-08-10", "2026-08-31"), _connu("2026-09-01", "2026-09-30")],
    )
    assert debut == _d("2026-08-10")
    assert jours == 22 + 30


def test_une_reprise_de_48_heures_au_plus_reste_une_prolongation():
    # Fin le mercredi 30/09, reprise jeudi et vendredi, nouvel arrêt samedi 03/10.
    debut, jours = _chainer(
        "2026-10-03", "2026-10-12", "maladie_simple", [_connu("2026-09-01", "2026-09-30")]
    )
    assert debut == _d("2026-09-01")
    assert jours == 30


def test_une_reprise_de_plus_de_48_heures_ouvre_un_nouvel_arret():
    assert _chainer(
        "2026-10-04", "2026-10-12", "maladie_simple", [_connu("2026-09-01", "2026-09-30")]
    ) == (None, 0)


def test_un_accident_du_travail_ne_prolonge_pas_une_maladie():
    assert _chainer(
        "2026-10-01", "2026-10-12", "accident_travail", [_connu("2026-09-01", "2026-09-30")]
    ) == (None, 0)


def test_des_demandes_qui_se_recouvrent_ne_comptent_leurs_jours_qu_une_fois():
    # Cas réel de septembre (Colorplast) : 17/08-03/09 puis 01/09-30/09.
    debut, jours = _chainer(
        "2026-09-01", "2026-09-30", "maladie_simple", [_connu("2026-08-17", "2026-09-03")]
    )
    assert debut == _d("2026-08-17")
    assert jours == 15  # du 17 au 31 août


# --- Dans le calcul du maintien (réglage légal) -----------------------------


def _ctx() -> SimpleNamespace:
    return SimpleNamespace(
        salaire_base_mensuel=2400.0,
        statut_salarie="Non-Cadre",
        baremes={
            "pss": {"annuel": 48060.0},
            "ij_plafonds": {"maladie": 42.97, "maternite_paternite": 104.02,
                            "at_mp": 240.49, "at_mp_majoree": 320.66},
        },
        contrat={"contrat": {"date_entree": "2021-08-01", "statut": "Non-Cadre"}},
    )


LEGAL = {
    "apply_legal_maintenance": True,
    "min_seniority_months": 12,
    "employer_waiting_days": 7,
    "no_seniority_condition": False,
    "custom_duration_days": None,
}


def _maintien(debut, fin, periode, *, arrets_connus=None, settings=LEGAL, ctx=None, **extra):
    arret = {
        "arret_type": "maladie_simple",
        "date_debut": debut,
        "date_fin": fin,
        "subrogation_active": False,
        "nombre_enfants": 0,
        "salaire_periode_reelle": 0.0,
        **extra,
    }
    if arrets_connus is not None:
        arret["arrets_connus"] = arrets_connus
    return calculer_maintien(arret, ctx or _ctx(), dict(settings), _d(periode[0]), _d(periode[1]))


SEPTEMBRE = ("2026-09-01", "2026-09-30")
OCTOBRE = ("2026-10-01", "2026-10-31")


def _chiffres(r: dict) -> tuple:
    return (
        r["ijss"]["ijss_theorique"],
        r["ijss"]["nb_jours_indemnises"],
        r["maintien"]["maintien_cible"],
        r["maintien"]["nb_jours_maintien"],
    )


def test_la_prolongation_de_septembre_se_calcule_comme_l_arret_entier():
    prolongation = _maintien(
        "2026-09-01", "2026-09-30", SEPTEMBRE,
        arrets_connus=[_connu("2026-08-10", "2026-08-31")],
    )
    arret_entier = _maintien("2026-08-10", "2026-09-30", SEPTEMBRE)
    assert _chiffres(prolongation) == _chiffres(arret_entier)
    assert prolongation["ijss"]["nb_jours_indemnises"] == 30


def test_en_octobre_les_droits_s_epuisent_a_leur_rang():
    prolongation = _maintien(
        "2026-10-01", "2026-10-31", OCTOBRE,
        arrets_connus=[_connu("2026-08-10", "2026-08-31"), _connu("2026-09-01", "2026-09-30")],
    )
    arret_entier = _maintien("2026-08-10", "2026-10-31", OCTOBRE)
    assert _chiffres(prolongation) == _chiffres(arret_entier)
    assert prolongation["nb_jours_arret_total"] == arret_entier["nb_jours_arret_total"]


def test_la_prolongation_dit_qu_elle_n_a_pas_de_nouvelle_carence():
    r = _maintien(
        "2026-09-01", "2026-09-30", SEPTEMBRE,
        arrets_connus=[_connu("2026-08-10", "2026-08-31")],
    )
    carence = r["carence"]
    assert carence["carence_ss_jours"] == 0
    assert carence["carence_employeur_jours"] == 0
    assert carence["est_continuite"] is True
    assert carence["motif_carence"] == (
        "Prolongation de l'arrêt commencé le 10/08/2026 : pas de nouvelle carence."
    )


def test_apres_une_reprise_d_un_jour_ni_carence_ni_jour_de_reprise_compte():
    r = _maintien(
        "2026-10-02", "2026-10-12", OCTOBRE,
        arrets_connus=[_connu("2026-09-01", "2026-09-30")],
    )
    assert r["carence"]["carence_ss_jours"] == 0
    assert r["carence"]["carence_employeur_jours"] == 0
    assert r["ijss"]["nb_jours_indemnises"] == 11
    assert r["maintien"]["nb_jours_maintien"] == 11


def test_la_carence_d_un_arret_court_se_poursuit_sur_sa_prolongation():
    # Arrêt d'un jour (01/09) prolongé du 02 au 10/09 : il reste 2 jours de
    # carence de la Sécurité sociale et 6 de carence employeur.
    r = _maintien(
        "2026-09-02", "2026-09-10", SEPTEMBRE,
        arrets_connus=[_connu("2026-09-01", "2026-09-01")],
    )
    assert r["carence"]["carence_ss_jours"] == 2
    assert r["carence"]["carence_employeur_jours"] == 6
    assert r["ijss"]["nb_jours_indemnises"] == 7
    assert r["carence"]["motif_carence"] == (
        "Prolongation de l'arrêt commencé le 01/09/2026 : sa carence se poursuit "
        "(2 jours de Sécurité sociale, 6 jours employeur)."
    )


def test_un_arret_sans_arret_connu_avant_garde_sa_carence():
    r = _maintien(
        "2026-10-04", "2026-10-12", OCTOBRE,
        arrets_connus=[_connu("2026-09-01", "2026-09-30")],
    )
    assert r["carence"]["carence_ss_jours"] == 3
    assert r["carence"]["carence_employeur_jours"] == 7
    assert r["carence"]["est_continuite"] is False


# --- Deux arrêts distincts dans le même mois (bulletin) ---------------------


from app.modules.payroll.documents.payslip_run_heures import (  # noqa: E402
    _extraire_arret_pour_maintien,
)

from .helpers import build_test_contexte  # noqa: E402

REGLAGES_PLASTURGIE = {
    "apply_legal_maintenance": False,
    "min_seniority_months": 10,
    "employer_waiting_days": 3,
    "subrogation_mode": "never",
    "paid_waiting_days_per_year": 3,
    "paid_waiting_min_seniority_months": 12,
    "maintain_working_days": True,
}


def _jour(iso, debut, fin, type_jour="arret_maladie"):
    return {
        "date_complete": iso,
        "type": type_jour,
        "arret_type": "maladie_simple",
        "date_debut_arret_reel": debut,
        "date_fin_arret_reel": fin,
    }


def _calendrier(*arrets):
    jours = []
    for debut, fin in arrets:
        d = _d(debut)
        while d <= _d(fin):
            jours.append(
                _jour(d.isoformat(), debut, fin, "weekend" if d.weekday() >= 5 else "arret_maladie")
            )
            d = date.fromordinal(d.toordinal() + 1)
    return jours


def _bulletin_de_septembre(*arrets):
    contexte = build_test_contexte(
        salaire_base=1963.99, duree_hebdo=39.0, date_entree="2021-09-13",
        specificites_extra={"salaire_hors_hs_structurelles": True},
    )
    arret = _extraire_arret_pour_maintien(
        _calendrier(*arrets), contexte, _d("2026-09-01"), _d("2026-09-30")
    )
    arret["arrets_annee"] = [{"debut": d, "fin": f, "type": "maladie_simple"} for d, f in arrets]
    arret["arrets_connus"] = list(arret["arrets_annee"])
    return calculer_maintien(
        arret, contexte, dict(REGLAGES_PLASTURGIE), _d("2026-09-01"), _d("2026-09-30")
    )


def test_deux_arrets_distincts_du_mois_gardent_chacun_leur_carence_payee():
    # 03-05/09 puis 22-26/09 : jeudi et vendredi payés, puis le mardi 22.
    r = _bulletin_de_septembre(("2026-09-03", "2026-09-05"), ("2026-09-22", "2026-09-26"))
    assert r["carence"]["carence_payee_dates"] == ["2026-09-03", "2026-09-04", "2026-09-22"]
    assert r["maintien"]["maintien_verse"] == pytest.approx(310.78, abs=0.01)
    # Les jours travaillés entre les deux arrêts ne sont pas des jours d'arrêt.
    assert r["ijss"]["nb_jours_indemnises"] == 2


def test_une_prolongation_dans_le_mois_garde_la_carence_payee_du_premier_arret():
    r = _bulletin_de_septembre(("2026-09-01", "2026-09-15"), ("2026-09-16", "2026-09-30"))
    assert r["carence"]["carence_payee_dates"] == ["2026-09-01", "2026-09-02", "2026-09-03"]
    assert r["maintien"]["maintien_verse"] == pytest.approx(310.78, abs=0.01)
    assert r["ijss"]["nb_jours_indemnises"] == 27


# --- Le pliant « Maintien & subrogation » lit la même chaîne ----------------


def test_l_apercu_d_une_demande_lit_les_arrets_connus_comme_le_bulletin(monkeypatch):
    from app.modules.absences.application import queries as q

    absence = {
        "id": "abs-2",
        "employee_id": "emp-1",
        "arret_type": "maladie_simple",
        "selected_days": ["2026-10-01", "2026-10-31"],
    }
    connus = [_connu("2026-09-01", "2026-09-30")]
    recu: dict = {}

    class _Table:
        def __init__(self, data):
            self._data = data

        def __getattr__(self, _nom):
            return lambda *a, **k: self

        def execute(self):
            return SimpleNamespace(data=self._data)

    lignes = {"employees": {"id": "emp-1", "company_id": "soc-1"}, "companies": {"id": "soc-1"}}
    monkeypatch.setattr(q.absence_repository, "get_by_id", lambda _id: absence)
    monkeypatch.setattr(q.supabase, "table", lambda nom: _Table(lignes.get(nom)))
    monkeypatch.setattr(q, "resolve_employee_id_for_user", lambda *_a: "emp-1")
    monkeypatch.setattr(
        q, "get_maintenance_settings",
        lambda _cid: SimpleNamespace(model_dump=lambda **_k: dict(REGLAGES_PLASTURGIE)),
    )
    monkeypatch.setattr(q, "compute_subrogation_for_absence", lambda *a, **k: False)
    monkeypatch.setattr(q, "resolve_nombre_enfants_employee", lambda _e: 0)
    monkeypatch.setattr(q, "build_historique_arrets_annee", lambda *a, **k: [])
    monkeypatch.setattr(q, "poser_salaires_de_reference", lambda *a, **k: None)
    monkeypatch.setattr(q, "ChargerContexte", lambda *a, **k: _ctx())
    monkeypatch.setattr(q, "arrets_connus_du_salarie", lambda eid, annee, mois: connus)

    def _calculer(arret, *_a, **_k):
        recu.update(arret)
        return {"carence": {}, "ijss": {}, "maintien": {}, "anciennete_mois": 60}

    monkeypatch.setattr(q, "calculer_maintien", _calculer)
    user = SimpleNamespace(
        active_company_id="soc-1", id="u-1", is_platform_admin=False,
        has_rh_access_in_company=lambda _c: True,
    )

    q.get_absence_maintenance_preview("abs-2", user)

    assert recu["arrets_connus"] == connus
    # La carence payée de la plasturgie s'y lit aussi, comme au bulletin.
    assert recu["arrets_annee"] == connus


def test_l_apercu_affiche_la_subrogation_eteinte_par_le_moteur(monkeypatch):
    from app.modules.absences.application import queries as q

    absence = {
        "id": "abs-mat",
        "employee_id": "emp-1",
        "arret_type": "maternite",
        "type": "arret_maternite",
        "selected_days": ["2026-12-07", "2026-12-08", "2026-12-09"],
    }

    class _Table:
        def __init__(self, data):
            self._data = data

        def __getattr__(self, _nom):
            return lambda *a, **k: self

        def execute(self):
            return SimpleNamespace(data=self._data)

    lignes = {"employees": {"id": "emp-1", "company_id": "soc-1"}, "companies": {"id": "soc-1"}}
    monkeypatch.setattr(q.absence_repository, "get_by_id", lambda _id: absence)
    monkeypatch.setattr(q.supabase, "table", lambda nom: _Table(lignes.get(nom)))
    monkeypatch.setattr(q, "resolve_employee_id_for_user", lambda *_a: "emp-1")
    monkeypatch.setattr(
        q, "get_maintenance_settings",
        lambda _cid: SimpleNamespace(model_dump=lambda **_k: {"subrogation_mode": "when_maintien"}),
    )
    monkeypatch.setattr(q, "compute_subrogation_for_absence", lambda *a, **k: True)
    monkeypatch.setattr(q, "resolve_nombre_enfants_employee", lambda _e: 0)
    monkeypatch.setattr(q, "build_historique_arrets_annee", lambda *a, **k: [])
    monkeypatch.setattr(q, "poser_salaires_de_reference", lambda *a, **k: None)
    monkeypatch.setattr(q, "ChargerContexte", lambda *a, **k: object())
    monkeypatch.setattr(q, "arrets_connus_du_salarie", lambda *a, **k: [])
    monkeypatch.setattr(
        q, "calculer_maintien",
        lambda *a, **k: {"subrogation_active": False, "maintien": {}, "alertes": []},
    )
    user = SimpleNamespace(
        active_company_id="soc-1", id="u-1", is_platform_admin=False,
        has_rh_access_in_company=lambda _c: True,
    )

    apercu = q.get_absence_maintenance_preview("abs-mat", user)
    assert apercu["subrogation_active"] is False
