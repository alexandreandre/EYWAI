"""[H12] Forfait jours : le départ appartient au bulletin du mois civil.

Le moteur des heures, le bandeau de la Paie, le reçu et le contrôle des
documents rattachent un départ au mois civil de son dernier jour ; le moteur
du forfait jours le rattachait à la période de paie de la société. Chez une
société à arrêté glissant (période close à l'avant-dernier vendredi), un cadre
au forfait parti entre le 21 et la fin du mois avait son solde sur le bulletin
du mois suivant, que l'écran ne cherche pas (bac à sable du 11/10/2026 :
départ au 25/09, septembre sans indemnité, octobre avec). Quadra rattache au
mois civil (« Salaire de base 1er au 15-09 » sur le bulletin de septembre).

La période de la société reste celle des variables (absences, jours) ; seuls
le départ et ce qui en dépend suivent le mois civil : indemnités du dossier,
précarité et congés de fin de contrat, prorata des jours après la sortie.
"""

from __future__ import annotations

from datetime import date
from unittest.mock import patch

import pytest

from app.modules.payroll.documents import payslip_run_forfait
from app.modules.payroll.engine.calcul_brut_forfait import calculer_salaire_brut_forfait
from app.modules.payroll.engine.period_forfait import bornes_periode_de_paie

from .helpers import build_test_contexte

pytestmark = pytest.mark.unit

#: Septembre 2026 d'une société close à l'avant-dernier vendredi : 24/08 → 20/09.
PERIODE_SOCIETE_SEPTEMBRE = bornes_periode_de_paie(2026, 9, 4, -2)


def test_la_periode_de_la_societe_ne_contient_pas_la_fin_de_septembre():
    assert PERIODE_SOCIETE_SEPTEMBRE == (date(2026, 8, 24), date(2026, 9, 20))


def test_le_depart_du_forfait_se_cherche_dans_le_mois_civil():
    contexte = build_test_contexte(statut="Cadre", specificites_extra={"is_forfait_jour": True})
    with patch(
        "app.modules.payroll.documents.payslip_run_heures.resolve_exit_state_for_payslip",
        return_value=({"indemnite_conges": {"montant": 0.0}}, False),
    ) as resoudre, patch(
        "app.modules.payroll.documents.payslip_run_heures.cp_fin_de_contrat", return_value=None
    ):
        payslip_run_forfait.poser_le_depart_du_forfait(contexte, "emp-1", 2026, 9)

    bornes = resoudre.call_args.kwargs
    assert (bornes["date_debut_periode"], bornes["date_fin_periode"]) == (
        date(2026, 9, 1),
        date(2026, 9, 30),
    )
    assert contexte.bornes_du_depart == (date(2026, 9, 1), date(2026, 9, 30))
    assert contexte.depart_du_mois is True


def _cdd_au_forfait_fini_le_25_septembre():
    contexte = build_test_contexte(
        statut="Cadre",
        salaire_base=3000.0,
        type_contrat="CDD",
        date_entree="2025-10-01",
        date_fin_contrat="2026-09-25",
        cumuls={"brut_total": 18000.0},
        specificites_extra={"is_forfait_jour": True},
    )
    contexte.bornes_du_depart = (date(2026, 9, 1), date(2026, 9, 30))
    return contexte


def test_la_fin_de_contrat_du_25_septembre_est_sur_le_bulletin_de_septembre():
    contexte = _cdd_au_forfait_fini_le_25_septembre()
    res = calculer_salaire_brut_forfait(contexte, [], *PERIODE_SOCIETE_SEPTEMBRE, [])

    lignes = {l["libelle"]: l for l in res["lignes_composants_brut"]}
    assert "Prime de précarité (CDD)" in lignes
    # Les jours ouvrés du mois civil après le 25/09 : 28, 29 et 30 septembre,
    # sur les 22 jours ouvrés de septembre 2026.
    sortie = lignes["Absence pour entrée ou sortie"]
    assert sortie["quantite"] == 3.0
    assert sortie["perte"] == round(3 * 3000.0 / 22, 2)


def test_un_mois_sans_depart_garde_la_periode_de_la_societe():
    contexte = build_test_contexte(
        statut="Cadre",
        salaire_base=3000.0,
        date_entree="2020-01-01",
        specificites_extra={"is_forfait_jour": True},
    )
    contexte.bornes_du_depart = (date(2026, 9, 1), date(2026, 9, 30))
    res = calculer_salaire_brut_forfait(contexte, [], *PERIODE_SOCIETE_SEPTEMBRE, [])

    libelles = [l["libelle"] for l in res["lignes_composants_brut"]]
    assert "Absence pour entrée ou sortie" not in libelles
    assert res["salaire_brut_total"] == 3000.0
