"""La note d'arbitrage des congés écrit ses montants à la française.

Relevé à l'écran : « L'indemnité de congés payés a été calculée selon la règle
du maintien de salaire (193.84 €), plus favorable que la règle du 1/10ème. »
Le bulletin écrit partout ailleurs 193,84 € ; la note aussi, dans ses deux
phrases (maintien ou dixième plus favorable), et celles du bulletin de sortie.
"""

from __future__ import annotations

import pytest

from app.modules.payroll.engine.bulletin import creer_bulletin_final, creer_bulletin_sortie
from tests.unit.payroll.helpers import build_test_contexte

pytestmark = pytest.mark.unit

NETS = {"net_imposable": 1500.0, "net_a_payer": 1200.0, "montant_impot_pas": 0.0}


def _ligne(libelle: str, *, gain: float | None = None, perte: float | None = None) -> dict:
    return {"libelle": libelle, "gain": gain, "perte": perte, "taux": None, "quantite": None}


def _contexte():
    contexte = build_test_contexte(salaire_base=1850.37)
    contexte.year = 2026
    return contexte


def _arbitrage(details_brut):
    return creer_bulletin_final(_contexte(), 2000.0, details_brut, [], NETS, [], 2026, 7)[
        "arbitrage_conges"
    ]


def test_maintien_plus_favorable():
    texte = _arbitrage([
        _ligne("Absence congés payés (2 jours : 13/07, 14/07)", perte=193.84),
        _ligne("Indemnité de congés payés (partie base)", gain=193.84),
    ])
    assert texte == (
        "L'indemnité de congés payés a été calculée selon la règle du maintien de "
        "salaire (193,84 €), plus favorable que la règle du 1/10ème."
    )


def test_dixieme_plus_favorable_avec_milliers():
    texte = _arbitrage([
        _ligne("Absence congés payés (10 jours)", perte=1193.84),
        _ligne("Indemnité de congés payés (partie base)", gain=1210.00),
        _ligne("Indemnité de congés payés (partie HS 25%)", gain=15.50),
    ])
    assert texte == (
        "L'indemnité de congés payés a été calculée selon la règle du 1/10ème "
        "(soit 1 225,50 €), plus favorable que le maintien de salaire (1 193,84 €)."
    )


@pytest.mark.parametrize("methode, attendu", [
    ("dixieme",
     "L'indemnité compensatrice de congés payés a été calculée selon la règle du "
     "1/10e (1 234,56 €), plus favorable que le maintien de salaire (1 100,10 €)."),
    ("maintien",
     "L'indemnité compensatrice de congés payés a été calculée selon le maintien "
     "de salaire (1 234,56 €), plus favorable que la règle du 1/10e (1 200,20 €)."),
    ("l1243_8",
     "L'indemnité compensatrice de congés payés (CDD) retenue : 1 234,56 € "
     "(règle des 10 % de la rémunération totale du contrat)."),
])
def test_bulletin_de_sortie(methode, attendu):
    indemnites = {
        "indemnite_conges": {
            "montant": 1234.56,
            "description": "ICCP",
            "details": {
                "methode_retenue": methode,
                "indemnite_maintien": 1100.10 if methode == "dixieme" else 1234.56,
                "indemnite_dixieme": 1200.20 if methode == "maintien" else 1234.56,
            },
        }
    }
    bulletin = creer_bulletin_sortie(_contexte(), 2000.0, [], [], NETS, [], indemnites, 2026, 10)
    assert bulletin["arbitrage_conges"] == attendu
