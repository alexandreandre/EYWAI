"""Arrêt maladie d'un salarié en FORFAIT JOUR.

Le chemin forfait-jour est un chemin de code distinct du chemin horaire : les
correctifs validés côté « heures » ne s'y appliquent jamais d'office. Deux trous
y rendaient l'arrêt maladie totalement invisible en paie (cadres MBC, janvier à
mars 2026) :

  1. `analyser_jours_forfait_du_mois` filtrait tout événement agrégé à 0
     (`if v > 0`) — or un jour d'arrêt est posé `heures_prevues=0`. L'événement
     n'atteignait donc jamais le calcul du brut, et ses métadonnées d'arrêt
     (`arret_type`, `subrogation_active`) étaient de toute façon perdues par
     l'agrégation, ce qui empêchait aussi le moteur de maintien de qualifier
     l'arrêt.
  2. `calculer_salaire_brut_forfait` n'avait pas de branche `arret_maladie` :
     même parvenu jusqu'à lui, le jour n'était pas déduit — brut = forfait plein.
"""

from datetime import date

import pytest

from app.modules.payroll.engine.analyser_jours_forfait import (
    analyser_jours_forfait_du_mois,
)
from app.modules.payroll.engine.calcul_brut_forfait import (
    calculer_salaire_brut_forfait,
)
from tests.unit.payroll.helpers import build_test_contexte

pytestmark = pytest.mark.unit

JOURS_OUVRES_MOYENS_MOIS = 21.67


def _ctx_forfait(salaire_base: float = 5411.69):
    return build_test_contexte(statut="Cadre", salaire_base=salaire_base)


def _jour_arret(jour: int, mois: int = 2, annee: int = 2026):
    """Jour d'arrêt tel que posé en base : `heures_prevues=0` + métadonnées."""
    return {
        "jour": jour,
        "mois": mois,
        "annee": annee,
        "type": "arret_maladie",
        "heures_prevues": 0,
        "arret_type": "maladie_simple",
        "subrogation_active": True,
    }


def test_analyzer_forfait_conserve_les_jours_arret_a_zero_heure():
    """Un jour d'arrêt posé à 0 h survit à l'agrégation (sinon jamais déduit)."""
    evenements = analyser_jours_forfait_du_mois(
        [_jour_arret(2), _jour_arret(3)], [], 2026, 2, "TEST"
    )
    arrets = [e for e in evenements if e.get("type") == "arret_maladie"]
    assert sorted(e["jour"] for e in arrets) == [2, 3]


def test_analyzer_forfait_preserve_les_metadonnees_arret():
    """`arret_type`/`subrogation_active` survivent à l'agrégation : le moteur de
    maintien en dépend pour qualifier l'arrêt."""
    evenements = analyser_jours_forfait_du_mois([_jour_arret(2)], [], 2026, 2, "TEST")
    arret = next(e for e in evenements if e.get("type") == "arret_maladie")
    assert arret["arret_type"] == "maladie_simple"
    assert arret["subrogation_active"] is True


def test_arret_maladie_forfait_deduit_une_journee_de_forfait():
    """Chaque jour d'arrêt retire une journée de forfait du brut."""
    ctx = _ctx_forfait()
    cal = [
        {"date_complete": "2026-02-02", "type": "arret_maladie", "heures": 0,
         "arret_type": "maladie_simple"},
        {"date_complete": "2026-02-03", "type": "arret_maladie", "heures": 0,
         "arret_type": "maladie_simple"},
    ]
    result = calculer_salaire_brut_forfait(
        ctx, cal, date(2026, 2, 1), date(2026, 2, 28)
    )
    journalier = 5411.69 / JOURS_OUVRES_MOYENS_MOIS
    lignes = [
        l for l in result["lignes_composants_brut"]
        if "Absence maladie" in l["libelle"]
    ]
    assert len(lignes) == 2
    assert all(l["quantite"] == 1.0 for l in lignes)
    # Le maintien employeur est réinjecté en aval (payslip_run_forfait), pas ici :
    # à ce stade le brut ne porte que la retenue.
    assert result["salaire_brut_total"] == round(5411.69 - 2 * round(journalier, 2), 2)


def test_arret_maladie_forfait_jamais_plus_d_une_journee_par_jour():
    """Une quantité saisie en heures (template horaire 7,5) ne peut pas coûter
    7,5 journées de forfait : un jour calendaire vaut au plus une journée."""
    ctx = _ctx_forfait()
    cal = [
        {"date_complete": "2026-02-02", "type": "arret_maladie", "heures": 7.5,
         "arret_type": "maladie_simple"},
    ]
    result = calculer_salaire_brut_forfait(
        ctx, cal, date(2026, 2, 1), date(2026, 2, 28)
    )
    ligne = next(
        l for l in result["lignes_composants_brut"] if "Absence maladie" in l["libelle"]
    )
    assert ligne["quantite"] == 1.0
    assert ligne["perte"] == round(5411.69 / JOURS_OUVRES_MOYENS_MOIS, 2)


def test_arret_maladie_forfait_demi_journee_preservee():
    """Un arrêt fractionnaire (< 1 jour) garde sa quotité réelle."""
    ctx = _ctx_forfait()
    cal = [
        {"date_complete": "2026-02-02", "type": "arret_maladie", "heures": 0.5,
         "arret_type": "maladie_simple"},
    ]
    result = calculer_salaire_brut_forfait(
        ctx, cal, date(2026, 2, 1), date(2026, 2, 28)
    )
    ligne = next(
        l for l in result["lignes_composants_brut"] if "Absence maladie" in l["libelle"]
    )
    assert ligne["quantite"] == 0.5
    assert ligne["perte"] == round(0.5 * (5411.69 / JOURS_OUVRES_MOYENS_MOIS), 2)
