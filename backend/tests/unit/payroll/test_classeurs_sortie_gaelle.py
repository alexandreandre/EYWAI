"""Formules de sortie de Martine rejouées contre les classeurs de la RH (R-384).

Trois classeurs (rupture conventionnelle ou licenciement, départ à la retraite,
fin de CDD), données pseudonymisées, montants relevés dans les classeurs.
"""

from __future__ import annotations

from datetime import date

import pytest

from app.modules.payroll.engine.calcul_indemnites_sortie import (
    anciennete_en_mois,
    calculer_anciennete_annees,
    calculer_indemnite_depart_retraite,
    calculer_indemnite_licenciement,
)
from app.modules.payroll.engine.iccp_fin_contrat import PeriodeConges, indemnite_fin_de_contrat
from app.modules.payroll.engine.indemnites_conventionnelles_branches import (
    indemnite_metallurgie_depart_retraite,
)

pytestmark = pytest.mark.unit


def test_rupture_conventionnelle_meme_formule_a_l_arrondi_d_anciennete_pres():
    """Classeur : 2,294 ans (jours / 365,25) × 1/4 × 2 608,57 = 1 496,02 ; Martine
    compte 2,30 ans (ans + mois + jours / 365, arrondi au centième) : +3,91 €."""
    anciennete = calculer_anciennete_annees(date(2024, 4, 2), date(2026, 7, 19))
    assert anciennete == pytest.approx(2.30)
    assert calculer_indemnite_licenciement(anciennete, 2608.57)["montant"] == pytest.approx(1499.93)


def test_licenciement_entre_dix_et_onze_ans_martine_suit_la_loi():
    """Le classeur compte 1/4 sur toute l'ancienneté de 10 à 11 ans ; R1234-2 :
    1/3 par année au-delà de 10 ans. Martine applique le texte."""
    montant = calculer_indemnite_licenciement(10.5, 3000.0)["montant"]
    assert montant == pytest.approx(3000.0 * 10 / 4 + 3000.0 * 0.5 / 3)


def test_depart_retraite_conforme_au_classeur():
    """Classeur : 11,9 ans, salaire de référence 4 395,39 ; légale 0,5 mois, cadre
    métallurgie 2 mois, le plus favorable retenu."""
    mois = anciennete_en_mois(date(2013, 11, 5), date(2025, 10, 1))
    assert calculer_indemnite_depart_retraite(mois, 4395.39)["montant"] == pytest.approx(2197.70, abs=0.01)
    convention = indemnite_metallurgie_depart_retraite(mois_d_anciennete=mois, salaire_reference=4395.39)
    assert convention["montant"] == pytest.approx(8790.78, abs=0.01)


def test_fin_de_cdd_maintien_le_plus_favorable():
    """Classeur étudiant : dixième 239,08, maintien 3,26 j × 82,87 = 270,16 retenu."""
    r = indemnite_fin_de_contrat(
        [PeriodeConges("en cours", 2390.77, 3.26, 3.26)], taux=0.10, valeur_jour=82.87
    )
    assert r.total == pytest.approx(270.16)


def test_fin_de_cdd_conges_deja_pris_par_periode():
    """Écart signalé (décision du 21/09) : le classeur soustrait les 392 € de congés
    déjà payés du dixième global (308,74 €) ; Martine retient le dixième des jours
    restants (2,03 / 6,03), sans repayer les jours pris."""
    r = indemnite_fin_de_contrat(
        [PeriodeConges("en cours", 7007.35, 6.03, 2.03)], taux=0.10, valeur_jour=98.0
    )
    assert r.total == pytest.approx(235.90)


def test_fin_de_cdd_plancher_du_dixieme_du_contrat():
    """L1242-16 : minimum du dixième du contrat, congés déjà payés déduits."""
    r = indemnite_fin_de_contrat(
        [PeriodeConges("en cours", 7007.35, 6.03, 2.03)],
        taux=0.10,
        valeur_jour=98.0,
        plancher_contrat=True,
    )
    assert r.total_par_periode == pytest.approx(235.90)
    assert r.total == pytest.approx(308.74)
    assert "L1242-16" in r.mention


def test_fin_de_cdd_le_plancher_ne_baisse_jamais_l_indemnite():
    r = indemnite_fin_de_contrat(
        [PeriodeConges("en cours", 2390.77, 3.26, 3.26)],
        taux=0.10,
        valeur_jour=82.87,
        plancher_contrat=True,
    )
    assert r.total == pytest.approx(270.16)


def test_fin_de_cdd_sans_remuneration_connue_pas_de_plancher():
    r = indemnite_fin_de_contrat(
        [PeriodeConges("en cours", None, 3.0, 2.0)],
        taux=0.10,
        valeur_jour=80.0,
        plancher_contrat=True,
    )
    assert r.plancher is None
    assert r.total == pytest.approx(160.0)
