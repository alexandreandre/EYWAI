"""Bulletin de sortie : l'indemnité compensatrice de congés et sa phrase viennent
du calcul du bulletin, pas de l'estimation du dossier de départ.

Démission fictive d'un CDI au 30/09 (enquête H, [H8]) : la ligne versée vaut
2 867,77 (règle par période, mention « période 2025-2026 … Total 2 867,77 »),
mais la phrase imprimée à côté disait « calculée selon le maintien de salaire
(2 337,29 €), plus favorable que la règle du 1/10e (2 231,94 €) » — montants et
méthode du dossier. Le récapitulatif `indemnites_sortie` portait aussi
2 337,29 « intégrée au brut » alors que le brut portait 2 867,77.
"""

from __future__ import annotations

import pytest

from app.modules.payroll.engine.bulletin import creer_bulletin_sortie
from app.modules.payroll.engine.iccp_fin_contrat import (
    PeriodeConges,
    indemnite_fin_de_contrat,
)
from tests.unit.payroll.helpers import build_test_contexte

pytestmark = pytest.mark.unit

NETS = {"net_imposable": 4500.0, "net_a_payer": 4899.51, "montant_impot_pas": 0.0}

DOSSIER = {
    "indemnite_preavis": {"montant": 0.0},
    "indemnite_conges": {
        "montant": 2337.29,
        "description": "Indemnité compensatrice de congés payés",
        "details": {
            "methode_retenue": "maintien",
            "indemnite_maintien": 2337.29,
            "indemnite_dixieme": 2231.94,
        },
    },
}

DETAIL_DU_BULLETIN = {
    "methode": "par_periode",
    "taux": 0.1,
    "valeur_jour": 108.53,
    "periodes": [
        {"libelle": "2025-2026", "retenu": 1628.25, "methode": "maintien"},
        {"libelle": "2026-2027", "retenu": 1239.52, "methode": "dixieme"},
    ],
    "total": 2867.77,
    "mention": (
        "Indemnité de congés payés de fin de contrat : période 2025-2026 … → 1 628,25 ; "
        "période 2026-2027 … dixième → 1 239,52. Total 2 867,77."
    ),
}

BRUT = [
    {"libelle": "Salaire de base", "quantite": 151.67, "taux": 15.6560, "gain": 2374.55, "perte": None},
    {"libelle": "Indemnité compensatrice de congés payés", "quantite": None, "taux": 0.1, "gain": 2867.77, "perte": None},
]


def _contexte(detail=None):
    contexte = build_test_contexte(salaire_base=2374.55, type_contrat="CDI", date_entree="2021-08-23")
    contexte.year = 2026
    if detail is not None:
        contexte.detail_iccp_fin_contrat = detail
    return contexte


def _bulletin(detail=None, dossier=None):
    return creer_bulletin_sortie(
        _contexte(detail), 5242.32, [dict(l) for l in BRUT], [], NETS, [],
        dossier if dossier is not None else DOSSIER, 2026, 9,
    )


def test_la_phrase_du_dossier_disparait_quand_le_bulletin_a_calcule_par_periode():
    bulletin = _bulletin(DETAIL_DU_BULLETIN)
    assert bulletin["arbitrage_conges"] is None
    assert bulletin["indemnite_cp_fin_contrat"]["mention"].endswith("Total 2 867,77.")


def test_le_recapitulatif_porte_l_indemnite_versee_par_le_bulletin():
    bulletin = _bulletin(DETAIL_DU_BULLETIN)
    lignes = [
        l for l in bulletin["indemnites_sortie"]["lignes_soumises"]
        if "compensatrice de congés" in l["libelle"]
    ]
    assert [l["gain"] for l in lignes] == [2867.77]
    assert bulletin["indemnites_sortie"]["total_soumises"] == 2867.77


def test_sans_jour_restant_le_recapitulatif_n_annonce_aucune_indemnite_de_conges():
    detail = indemnite_fin_de_contrat(
        [PeriodeConges("2026-2027", 3000.0, 2.5, 0.0)], taux=0.1, valeur_jour=100.0
    ).resume()
    bulletin = creer_bulletin_sortie(
        _contexte(detail), 2374.55, [dict(BRUT[0])], [], NETS, [], DOSSIER, 2026, 9,
    )
    assert not any(
        "compensatrice de congés" in l["libelle"]
        for l in bulletin["indemnites_sortie"]["lignes_soumises"]
    )
    assert bulletin["arbitrage_conges"] is None


def test_sans_calcul_du_bulletin_le_dossier_verse_garde_sa_phrase():
    """Repli : sans compteurs, c'est l'estimation du dossier qui entre au brut ;
    sa phrase dit alors ce qui a été versé."""
    brut = [dict(BRUT[0]), {"libelle": "Indemnité compensatrice de congés payés", "gain": 2337.29}]
    bulletin = creer_bulletin_sortie(_contexte(), 4711.84, brut, [], NETS, [], DOSSIER, 2026, 9)
    assert "2 337,29 €" in bulletin["arbitrage_conges"]
    lignes = [
        l for l in bulletin["indemnites_sortie"]["lignes_soumises"]
        if "compensatrice de congés" in l["libelle"]
    ]
    assert [l["gain"] for l in lignes] == [2337.29]


def test_une_mention_sans_periode_ne_s_imprime_pas():
    """Fin de CDD sans jour restant : la mention imprimait « Indemnité de congés
    payés de fin de contrat : . Total 0,00. » (bulletin de septembre 2026)."""
    resultat = indemnite_fin_de_contrat(
        [PeriodeConges("2026-2027", 3000.0, 2.5, 0.0)], taux=0.1, valeur_jour=100.0
    )
    assert resultat.mention == ""
    assert resultat.resume()["mention"] == ""
