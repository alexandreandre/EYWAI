"""Un arrêt se retient sur ses jours ouvrés, en une ligne par période.

Colorplast, août 2026 : un arrêt maladie du 17 au 31/08 saisi à l'écran type
aussi les samedis et dimanches au calendrier. Le moteur retenait 7 h pour
chacun des 15 jours (1 380,00 €) ; le cabinet retient les 11 jours ouvrés,
en une ligne « Absence maladie 170826-310826 », 77,00 h à 13,1430 = 1 012,01 €,
arrondie une fois sur la période. Le bulletin portait 15 lignes, une par jour.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from app.modules.payroll.engine.calcul_brut import calculer_salaire_brut

from .helpers import build_test_contexte

pytestmark = pytest.mark.unit


def _jours(debut: date, fin: date, type_ev: str = "arret_maladie", heures: float = 0.0):
    jour, jours = debut, []
    while jour <= fin:
        jours.append({"date_complete": jour.isoformat(), "type": type_ev, "heures": heures})
        jour += timedelta(days=1)
    return jours


def _lignes(calendrier, salaire_base=1993.40):
    contexte = build_test_contexte(
        salaire_base=salaire_base, duree_hebdo=39.0, date_entree="2021-09-13",
        specificites_extra={"salaire_hors_hs_structurelles": True},
    )
    resultat = calculer_salaire_brut(
        contexte, calendrier, date(2026, 8, 1), date(2026, 8, 31), [],
        date_debut_variables=date(2026, 7, 27), date_fin_variables=date(2026, 8, 23),
    )
    return resultat["lignes_composants_brut"]


def _arrets(lignes):
    return [l for l in lignes if l.get("is_arret_maladie")]


def test_les_week_ends_d_un_arret_ne_sont_pas_retenus():
    lignes = _lignes(_jours(date(2026, 8, 17), date(2026, 8, 31)))
    (arret,) = _arrets(lignes)
    assert arret["quantite"] == 77.0


def test_une_seule_ligne_par_periode_arrondie_une_fois_comme_le_cabinet():
    lignes = _lignes(_jours(date(2026, 8, 17), date(2026, 8, 31)))
    assert _arrets(lignes) == [
        {
            "libelle": "Absence arrêt maladie du 17/08 au 31/08",
            "quantite": 77.0,
            "taux": 13.143,
            "gain": None,
            "perte": 1012.01,
            "is_arret_maladie": True,
        }
    ]


def test_la_quote_part_structurelle_suit_les_jours_ouvres():
    """11 journées : 8,80 h structurelles (le cabinet en imprime 8,90 avec les
    0,10 h de l'absence du 31/07, absente de ce test)."""
    lignes = _lignes(_jours(date(2026, 8, 17), date(2026, 8, 31)))
    (reduction,) = [l for l in lignes if l.get("is_reduction_hs")]
    assert reduction["quantite"] == 8.8


def test_un_samedi_prevu_travaille_reste_retenu():
    calendrier = _jours(date(2026, 8, 17), date(2026, 8, 21)) + [
        {"date_complete": "2026-08-22", "type": "arret_maladie", "heures": 7.0}
    ]
    (arret,) = _arrets(_lignes(calendrier))
    assert arret["quantite"] == 42.0
    assert arret["libelle"] == "Absence arrêt maladie du 17/08 au 22/08"


def test_deux_arrets_separes_par_un_jour_travaille_font_deux_lignes():
    calendrier = (
        _jours(date(2026, 8, 3), date(2026, 8, 5))
        + [{"date_complete": "2026-08-06", "type": "travail_base", "heures": 7.8}]
        + _jours(date(2026, 8, 7), date(2026, 8, 11))
    )
    arrets = _arrets(_lignes(calendrier))
    assert [(a["libelle"], a["quantite"]) for a in arrets] == [
        ("Absence arrêt maladie du 03/08 au 05/08", 21.0),
        ("Absence arrêt maladie du 07/08 au 11/08", 21.0),
    ]


def test_un_arret_d_un_jour_dit_sa_date():
    (arret,) = _arrets(_lignes(_jours(date(2026, 8, 18), date(2026, 8, 18))))
    assert arret["libelle"] == "Absence arrêt maladie du 18/08"


def test_deux_natures_d_arret_ne_se_melangent_pas():
    calendrier = _jours(date(2026, 8, 17), date(2026, 8, 19)) + _jours(
        date(2026, 8, 20), date(2026, 8, 21), "arret_at"
    )
    arrets = _arrets(_lignes(calendrier))
    assert [a["libelle"] for a in arrets] == [
        "Absence arrêt maladie du 17/08 au 19/08",
        "Absence accident du travail du 20/08 au 21/08",
    ]
