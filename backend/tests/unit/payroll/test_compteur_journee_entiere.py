"""Une journée non payée coûte 7,80 h au compteur, pas 7,00.

Sur un contrat de 39 h, une journée de travail vaut 7,80 h payées : 7,00 h de
base plus la quote-part d'heure supplémentaire structurelle du jour (17,33 h
réparties sur les jours ouvrés du mois). Le brut retirait bien les deux — la
ligne « Réduction HS structurelles » est là pour ça — mais les compteurs ne
voyaient que la base : la part structurelle des jours fériés non payés et des
jours d'arrêt revenait au compteur d'heures et au SMIC de référence comme si
elle avait été payée.

Colorplast, mai 2026 : Demory affichait 338,70 h au compteur là où le cabinet
imprime 333,90 — six journées non payées, 0,80 h de trop chacune.

Les absences fractionnées, elles, étaient déjà justes : leur part structurelle
entre directement dans `heures_absence_non_payees` (Cotte, janvier 2026 :
3,50 h retirées pour une absence de 3,50 h, dont 0,36 de structurel).
"""

from __future__ import annotations

from datetime import date

import pytest

from app.modules.payroll.engine.calcul_brut import calculer_salaire_brut

from .helpers import build_test_contexte

pytestmark = pytest.mark.unit

MAI = (date(2026, 5, 1), date(2026, 5, 31))
VARIABLES = {"date_debut_variables": date(2026, 4, 20),
             "date_fin_variables": date(2026, 5, 24)}
#: 17,33 h structurelles sur 151,67 / 7 = 21,667 jours ouvrés légaux.
QUOTE_PART_JOUR = 0.80


def _contexte(date_entree="2026-03-23"):
    return build_test_contexte(
        salaire_base=1850.37, duree_hebdo=39.0, date_entree=date_entree,
        prior_service_months=0,
        specificites_extra={"salaire_hors_hs_structurelles": True,
                            "jours_feries_anciennete_min_mois": 3},
    )


def _brut(calendrier, contexte=None):
    return calculer_salaire_brut(
        contexte or _contexte(), calendrier, *MAI, [], **VARIABLES
    )


def test_un_ferie_non_paye_retire_sa_part_structurelle_du_compteur():
    cal = [{"date_complete": j, "type": "ferie", "heures": 7.8}
           for j in ("2026-05-08", "2026-05-14")]
    res = _brut(cal)
    assert res["heures_absence_non_payees"] == pytest.approx(
        2 * (7.0 + QUOTE_PART_JOUR), abs=0.01
    )


def test_un_jour_d_arret_retire_sa_part_structurelle_du_compteur():
    """Demory, accident du travail du 26 au 29/05 : 4 × 7,80 = 31,20 h."""
    cal = [{"date_complete": f"2026-05-{d:02d}", "type": "arret_at", "heures": 8.5,
            "arret_type": "accident_travail",
            "date_debut_arret_reel": "2026-05-23",
            "date_fin_arret_reel": "2026-05-29"}
           for d in (26, 27, 28, 29)]
    res = _brut(cal)
    assert res["heures_arret_deduites"] == pytest.approx(
        4 * (7.0 + QUOTE_PART_JOUR), abs=0.01
    )


def test_le_brut_ne_bouge_pas():
    """La part structurelle était déjà retirée du brut : rien ne doit changer."""
    cal = [{"date_complete": "2026-05-08", "type": "ferie", "heures": 7.8}]
    res = _brut(cal)
    pertes = {l["libelle"]: (l["quantite"], l["perte"])
              for l in res["lignes_composants_brut"] if l.get("perte")}
    assert pertes["Abs. jour férié non payé du 08/05/26"] == (7.0, 85.40)
    assert pertes["Réduction HS structurelles (jours d'absence)"] == (0.8, 12.20)


def test_une_absence_fractionnee_n_est_pas_comptee_deux_fois():
    """Cotte, janvier : 3,50 h d'absence, 3,50 h retirées — base ET structurel."""
    contexte = build_test_contexte(
        salaire_base=2138.00, duree_hebdo=39.0, date_entree="2020-01-01",
        specificites_extra={"salaire_hors_hs_structurelles": True},
    )
    cal = [{"date_complete": "2026-05-21", "type": "absence_non_remuneree",
            "heures": 3.5}]
    res = _brut(cal, contexte)
    assert res["heures_absence_non_payees"] == pytest.approx(3.50, abs=0.01)


def test_sans_heures_structurelles_rien_ne_change():
    """Contrat à 35 h : la quote-part est nulle, le compteur perd 7,00 h."""
    contexte = build_test_contexte(
        salaire_base=1801.80, duree_hebdo=35.0, date_entree="2026-03-23",
        prior_service_months=0,
        specificites_extra={"jours_feries_anciennete_min_mois": 3},
    )
    cal = [{"date_complete": "2026-05-08", "type": "ferie", "heures": 7.0}]
    res = _brut(cal, contexte)
    assert res["heures_absence_non_payees"] == pytest.approx(7.00, abs=0.01)
