"""Un férié qui tombe un samedi ou un dimanche n'est pas chômé : rien n'est retenu.

Sous trois mois d'ancienneté, le jour férié chômé n'est pas payé (L. 3133-3 a contrario) :
le moteur retient la journée. Mais un férié tombé un jour de repos ne fait perdre aucune
journée de travail. Cartol, novembre 2026 au bac à sable : un forfait entré le 07/09 portait
« Abs. jour férié non payé du 01/11/26 », 143,05 €, pour le dimanche de la Toussaint.
Même défaut au générateur des heures (la journée vide valait 7 h) : les deux sont testés.
"""

from __future__ import annotations

from datetime import date

import pytest

from app.modules.payroll.engine.calcul_brut import calculer_salaire_brut
from app.modules.payroll.engine.calcul_brut_forfait import calculer_salaire_brut_forfait

from .helpers import build_test_contexte

pytestmark = pytest.mark.unit

NOVEMBRE = (date(2026, 11, 1), date(2026, 11, 30))


def _contexte():
    # Entré le 07/09/2026 : moins de trois mois d'ancienneté au 01/11 et au 11/11.
    return build_test_contexte(salaire_base=3000.0, date_entree="2026-09-07")


def _feries_retenus(resultat) -> list[str]:
    return [
        l["libelle"] for l in resultat["lignes_composants_brut"]
        if "férié non payé" in str(l.get("libelle") or "")
    ]


CALENDRIER_HEURES = [
    {"date_complete": "2026-11-01", "type": "ferie", "heures": 0.0},
    {"date_complete": "2026-11-11", "type": "ferie", "heures": 7.0},
]
CALENDRIER_FORFAIT = [
    {"date_complete": "2026-11-01", "type": "ferie", "heures": 0.0},
    {"date_complete": "2026-11-11", "type": "ferie", "heures": 0.0},
]


def test_heures_le_dimanche_ferie_n_est_pas_retenu_le_mercredi_l_est():
    resultat = calculer_salaire_brut(_contexte(), CALENDRIER_HEURES, *NOVEMBRE, [])
    assert _feries_retenus(resultat) == ["Abs. jour férié non payé du 11/11/26"]


def test_forfait_le_dimanche_ferie_n_est_pas_retenu_le_mercredi_l_est():
    resultat = calculer_salaire_brut_forfait(_contexte(), CALENDRIER_FORFAIT, *NOVEMBRE, [])
    assert _feries_retenus(resultat) == ["Abs. jour férié non payé du 11/11/26"]


def test_un_samedi_ferie_travaille_au_planning_garde_la_regle():
    """Un samedi férié prévu travaillé (heures au planning) reste soumis à la règle des trois mois."""
    cal = [{"date_complete": "2026-08-15", "type": "ferie", "heures": 7.0}]
    resultat = calculer_salaire_brut(_contexte_aout(), cal, date(2026, 8, 1), date(2026, 8, 31), [])
    assert _feries_retenus(resultat) == ["Abs. jour férié non payé du 15/08/26"]


def _contexte_aout():
    return build_test_contexte(salaire_base=3000.0, date_entree="2026-07-06")
