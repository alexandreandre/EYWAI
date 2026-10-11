"""Accident de trajet : la carence employeur s'applique, comme pour la maladie.

Source : Code du travail, art. D1226-3 (Légifrance, section D1226-1 à
D1226-8-1) : « Lors de chaque arrêt de travail, les durées d'indemnisation
courent à compter du premier jour d'absence si celle-ci est consécutive à un
accident du travail ou à une maladie professionnelle, à l'exclusion des
accidents de trajet. » Les autres arrêts, accident de trajet compris, courent
après le délai de carence de sept jours (D1226-3, premier alinéa ;
service-public F3053).

Côté Sécurité sociale, l'accident de trajet reste indemnisé comme un accident
du travail (CSS L411-2) : pas de carence, IJ à 60 % puis 80 %. Le moteur
rangeait le trajet avec l'accident du travail pour tout : carence employeur
à 0, environ 497 € de maintien versés à tort sur un mois (enquête, réglage
légal, 2 400 €).
"""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pytest

from app.modules.payroll.engine.maintien_salaire_service import (
    _calculer_carence,
    _qualifier_arret,
    calculer_maintien,
)

pytestmark = pytest.mark.unit

SEPTEMBRE = (date(2026, 9, 1), date(2026, 9, 30))


def _ctx() -> SimpleNamespace:
    return SimpleNamespace(
        salaire_base_mensuel=2400.0,
        statut_salarie="Non-Cadre",
        baremes={
            "pss": {"annuel": 48060.0},
            "ij_plafonds": {"maladie": 42.97, "at_mp": 240.49, "at_mp_majoree": 320.66},
        },
        contrat={"contrat": {"date_entree": "2021-03-01", "statut": "Non-Cadre"}},
    )


REGLAGE_LEGAL = {
    "apply_legal_maintenance": True,
    "min_seniority_months": 12,
    "employer_waiting_days": 7,
    "no_seniority_condition": False,
}


def _arret(arret_type: str) -> dict:
    return {
        "arret_type": arret_type,
        "date_debut": "2026-09-01",
        "date_fin": "2026-09-30",
        "subrogation_active": False,
        "nombre_enfants": 0,
        "salaire_periode_reelle": 0.0,
    }


def test_accident_de_trajet_a_la_carence_employeur_de_sept_jours():
    carence = _calculer_carence(
        {"arret_type": "accident_trajet"},
        _qualifier_arret("accident_trajet"),
        REGLAGE_LEGAL,
        date(2026, 9, 1),
        [],
    )
    assert carence["carence_employeur_jours"] == 7
    assert carence["carence_ss_jours"] == 0


def test_accident_du_travail_reste_sans_carence_employeur():
    carence = _calculer_carence(
        {"arret_type": "accident_travail"},
        _qualifier_arret("accident_travail"),
        REGLAGE_LEGAL,
        date(2026, 9, 1),
        [],
    )
    assert carence["carence_employeur_jours"] == 0


def test_le_maintien_d_un_trajet_commence_apres_la_carence():
    trajet = calculer_maintien(_arret("accident_trajet"), _ctx(), REGLAGE_LEGAL, *SEPTEMBRE)
    at = calculer_maintien(_arret("accident_travail"), _ctx(), REGLAGE_LEGAL, *SEPTEMBRE)
    assert at["maintien"]["nb_jours_maintien"] == 30
    assert trajet["maintien"]["nb_jours_maintien"] == 23
    assert trajet["maintien"]["maintien_verse"] < at["maintien"]["maintien_verse"]


def test_les_ij_d_un_trajet_restent_celles_d_un_accident_du_travail():
    trajet = calculer_maintien(_arret("accident_trajet"), _ctx(), REGLAGE_LEGAL, *SEPTEMBRE)
    at = calculer_maintien(_arret("accident_travail"), _ctx(), REGLAGE_LEGAL, *SEPTEMBRE)
    assert trajet["ijss"] == at["ijss"]
