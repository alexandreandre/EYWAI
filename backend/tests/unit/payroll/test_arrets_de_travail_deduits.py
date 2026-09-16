"""Tous les arrêts de travail se déduisent, pas seulement la maladie.

La retenue est la même quelle que soit la nature de l'arrêt : une journée vaut
la référence journalière légale (7 h), et la quote-part d'heures sup
structurelles est retirée séparément. Ce qui distingue les natures, c'est le
maintien de salaire, qui se joue ailleurs à partir de `arret_type`.

Le moteur ne reconnaissait que `arret_maladie` : un accident du travail, un
congé maternité ou paternité passaient à travers sans aucune retenue.

Référence : Demory (Colorplast, mai 2026), accident du travail du 23 au 29 mai.
Le cabinet déduit 28,00 h à 12,20 € (341,60 €) et 3,20 h structurelles
(48,80 €) — 390,40 € que nous laissions au brut.
"""

from __future__ import annotations

from datetime import date

import pytest

from app.modules.payroll.engine.calcul_brut import calculer_salaire_brut

from .helpers import build_test_contexte

pytestmark = pytest.mark.unit

JOURS_OUVRES = (26, 27, 28, 29)


def _pertes(type_arret):
    contexte = build_test_contexte(
        salaire_base=1850.37, duree_hebdo=39.0, date_entree="2026-03-23",
        specificites_extra={"salaire_hors_hs_structurelles": True},
    )
    calendrier = [
        {"date_complete": f"2026-05-{j:02d}", "type": type_arret, "heures": 8.5}
        for j in JOURS_OUVRES
    ]
    resultat = calculer_salaire_brut(
        contexte, calendrier, date(2026, 5, 1), date(2026, 5, 31), [],
        date_debut_variables=date(2026, 4, 20), date_fin_variables=date(2026, 5, 24),
    )
    return [(l["libelle"], l["quantite"], l["perte"])
            for l in resultat["lignes_composants_brut"] if l.get("perte")]


@pytest.mark.parametrize("type_arret, libelle", [
    ("arret_maladie", "Absence arrêt maladie (jours déduction)"),
    ("arret_at", "Absence accident du travail (jours déduction)"),
    ("arret_maternite", "Absence congé maternité (jours déduction)"),
    ("arret_paternite", "Absence congé paternité (jours déduction)"),
])
def test_chaque_nature_d_arret_est_deduite(type_arret, libelle):
    pertes = _pertes(type_arret)
    jours = [p for p in pertes if "jours déduction" in p[0]]
    assert len(jours) == len(JOURS_OUVRES)
    assert all(p[0] == libelle and p[1] == 7.0 and p[2] == 85.40 for p in jours)


def test_la_quote_part_structurelle_est_retiree_une_fois():
    """Quatre journées : 3,20 h structurelles, comme le cabinet."""
    structurelles = [p for p in _pertes("arret_at") if "Réduction HS" in p[0]]
    assert structurelles == [("Réduction HS structurelles (jours d'absence)", 3.2, 48.80)]
