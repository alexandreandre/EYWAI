"""Les heures sup compensées entre semaines se paient même si le contrat finit
avant la fin de la fenêtre des variables.

Fin de CDD au 15/09, fenêtre arrêtée au 20/09 : le solde des heures sup est posé
au 20/09 ; le filtre « rien après la sortie » l'écartait, 12,5 h perdues.
"""

from __future__ import annotations

from datetime import date

import pytest

from app.modules.payroll.engine.calcul_brut import calculer_salaire_brut

from .helpers import build_test_contexte

pytestmark = pytest.mark.unit


def _evenement(jour, type_ev, heures, **extra):
    return {"annee": 2026, "mois": 9, "jour": jour, "date_complete": f"2026-09-{jour:02d}",
            "type": type_ev, "heures": heures, **extra}


def _heures_sup(lignes):
    return {l["libelle"]: l.get("quantite") for l in lignes if "suppl" in str(l.get("libelle", "")).lower()}


def test_le_solde_compense_est_paye_apres_la_sortie_mais_pas_un_travail_apres_la_sortie():
    ctx = build_test_contexte(duree_hebdo=35.0, date_fin_contrat="2026-09-15", type_contrat="CDD")
    calendrier = [
        _evenement(20, "travail_hs25", 8.0, compensation_semaines=True),
        _evenement(20, "travail_hs50", 4.5, compensation_semaines=True),
        _evenement(18, "travail_hs25", 3.0),  # après la sortie, sans compensation : écarté
    ]
    resultat = calculer_salaire_brut(ctx, calendrier, date(2026, 9, 1), date(2026, 9, 30), [])
    assert resultat["total_heures_supp"] == pytest.approx(12.5), _heures_sup(resultat["lignes_composants_brut"])
