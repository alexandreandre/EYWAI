"""Un jour férié non payé se déduit sur la référence journalière légale.

Sous trois mois d'ancienneté, le jour férié chômé n'est pas maintenu (art.
L3133-3). La retenue vaut alors une journée entière : 7 h de base, plus la
quote-part d'heures sup structurelles de la journée, retirée séparément.

Le moteur déduisait les heures planifiées — 7,80 h sur un contrat de 39 h —
ce qui retirait deux fois la part structurelle. C'était la seule branche
d'absence à ne pas passer par la référence légale ; l'arrêt maladie et le congé
pour événement familial le faisaient déjà.

Référence : Demory et Fuckar (Colorplast, mai 2026), fériés du 8 et du 14 mai.
Le cabinet déduit 7,00 h à 12,20 € (85,40 €) par férié, et 1,60 h structurelles
pour les deux jours réunis.
"""

from __future__ import annotations

from datetime import date

import pytest

from app.modules.payroll.engine.calcul_brut import calculer_salaire_brut

from .helpers import build_test_contexte

pytestmark = pytest.mark.unit


def _resultat(jours):
    contexte = build_test_contexte(
        salaire_base=1850.37,
        duree_hebdo=39.0,
        date_entree="2026-03-23",
        specificites_extra={
            "salaire_hors_hs_structurelles": True,
            "jours_feries_anciennete_min_mois": 3,
        },
    )
    calendrier = [
        {"date_complete": j, "type": "ferie", "heures": 7.8} for j in jours
    ]
    return calculer_salaire_brut(
        contexte, calendrier, date(2026, 5, 1), date(2026, 5, 31), [],
        date_debut_variables=date(2026, 4, 20), date_fin_variables=date(2026, 5, 24),
    )


def _pertes(resultat, fragment):
    return [
        (l["quantite"], l["perte"])
        for l in resultat["lignes_composants_brut"]
        if fragment in l["libelle"]
    ]


def test_la_retenue_vaut_sept_heures_et_non_l_horaire_du_jour():
    pertes = _pertes(_resultat(["2026-05-08", "2026-05-14"]), "jour férié non payé")
    assert pertes == [(7.0, 85.40), (7.0, 85.40)]


def test_la_quote_part_structurelle_suit_la_journee_entiere():
    """Deux journées pleines : 2 × 0,80 h, et non 2 × 0,89."""
    pertes = _pertes(_resultat(["2026-05-08", "2026-05-14"]), "Réduction HS structurelles")
    assert pertes == [(1.6, 24.40)]


def test_un_ferie_paye_ne_retire_rien():
    """Avec l'ancienneté requise, le férié reste maintenu."""
    contexte = build_test_contexte(
        salaire_base=1850.37, duree_hebdo=39.0, date_entree="2022-01-01",
        specificites_extra={"salaire_hors_hs_structurelles": True,
                            "jours_feries_anciennete_min_mois": 3},
    )
    resultat = calculer_salaire_brut(
        contexte, [{"date_complete": "2026-05-08", "type": "ferie", "heures": 7.8}],
        date(2026, 5, 1), date(2026, 5, 31), [],
        date_debut_variables=date(2026, 4, 20), date_fin_variables=date(2026, 5, 24),
    )
    assert _pertes(resultat, "jour férié non payé") == []
