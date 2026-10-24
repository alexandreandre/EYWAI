"""Sous le barème, la ligne de maintien dit ses paliers, son garanti et ses IJSS
(conception du 24/10/2026)."""

from __future__ import annotations

import pytest

from app.modules.payroll.domain.explications_lignes import poser_explications

pytestmark = pytest.mark.unit

LIGNE = {"libelle": "Maintien de salaire employeur", "quantite": None, "taux": None,
         "gain": 445.23, "perte": None, "is_maintien_employeur": True}
JUILLET = {
    "maintien_cible": 1722.12, "maintien_verse": 445.23,
    "ijss_deduites": 1276.89, "ijss_deduites_source": "validees",
    "bareme": "plasturgie_0292", "regle_retenue": "convention",
    "bareme_detail": "Plasturgie (IDCC 0292), non-cadres, 5 ans et plus",
    "paliers_en_jours_ouvres": True,
    "paliers": [
        {"taux": 1.0, "du": "2026-07-01", "au": "2026-07-02", "jours": 2, "garanti": 194.04},
        {"taux": 0.75, "du": "2026-07-03", "au": "2026-07-31", "jours": 21, "garanti": 1528.08},
    ],
}


def _bulletin(maintien):
    return {
        "en_tete": {"annee": 2026, "mois": 7},
        "calcul_du_brut": [dict(LIGNE)],
        "bloc_maintien": {"maintien": maintien},
    }


def test_la_ligne_de_maintien_dit_les_paliers_le_garanti_et_les_ijss():
    b = poser_explications(_bulletin(JUILLET))
    assert b["calcul_du_brut"][0]["explication"] == (
        "Plasturgie (IDCC 0292), non-cadres, 5 ans et plus : 2 jours ouvrés à 100 % et "
        "21 jours ouvrés à 75 %, salaire garanti 1 722,12 € moins 1 276,89 € d'IJSS "
        "versées par la CPAM au salarié (montant validé dans le suivi IJSS)"
    )


def test_quand_le_legal_l_emporte_la_ligne_le_dit():
    legal = {**JUILLET, "regle_retenue": "legal", "maintien_cible": 1781.95,
             "ijss_deduites_source": "estimees", "paliers": [
                 {"taux": 0.9, "jours": 13}, {"taux": 0.6667, "jours": 10}]}
    texte = poser_explications(_bulletin(legal))["calcul_du_brut"][0]["explication"]
    assert texte.startswith(
        "Maintien légal, plus favorable ce mois-ci que le barème Plasturgie (IDCC 0292) : "
        "13 jours ouvrés à 90 % et 10 jours ouvrés à 66,67 %, salaire garanti 1 781,95 €"
    )


def test_avec_subrogation_pas_de_mention_d_ijss_versees_au_salarie():
    subroge = {k: v for k, v in JUILLET.items() if not k.startswith("ijss_deduites")}
    texte = poser_explications(_bulletin(subroge))["calcul_du_brut"][0]["explication"]
    assert texte.endswith("salaire garanti 1 722,12 €")


def test_sans_bareme_l_explication_d_avant():
    sans = {"maintien_cible": 665.68, "maintien_verse": 295.82,
            "ijss_deduites": 369.86, "ijss_deduites_source": "estimees"}
    assert poser_explications(_bulletin(sans))["calcul_du_brut"][0]["explication"].startswith(
        "Complément employeur : salaire garanti 665,68 €"
    )
