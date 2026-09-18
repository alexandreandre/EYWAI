"""Génération en bac à sable : le passé vient de l'appelant, rien n'est écrit.

Un rejeu d'audit (Colorplast, janvier à juin rejoués à la régulière) ne doit
jamais écrire dans la chaîne de paie : ni `payslips`, ni les cumuls, ni le
storage — c'est ce qui a fait casser janvier trois fois. Le bac à sable donne
au générateur ses cumuls précédents en mémoire et lui interdit toute
persistance ; le bulletin calculé est rendu à l'appelant, qui chaîne lui-même
ses mois.
"""

from __future__ import annotations

import pytest

from app.modules.payroll.documents.bac_a_sable import BacASable, cumuls_de_depart

pytestmark = pytest.mark.unit


def test_sans_cumuls_injectes_on_part_de_zero_comme_un_premier_bulletin():
    depart = cumuls_de_depart(BacASable(), 2026)

    assert depart["periode"] == {"annee_en_cours": 2026, "dernier_mois_calcule": 0}
    assert depart["cumuls"] == {
        "brut_total": 0.0,
        "heures_remunerees": 0.0,
        "reduction_generale_patronale": 0.0,
        "net_imposable": 0.0,
        "impot_preleve_a_la_source": 0.0,
        "heures_supplementaires_remunerees": 0.0,
    }


def test_les_cumuls_injectes_sont_le_point_de_depart():
    precedents = {
        "periode": {"annee_en_cours": 2026, "dernier_mois_calcule": 3},
        "cumuls": {"brut_total": 7500.0, "heures_remunerees": 507.0},
    }

    depart = cumuls_de_depart(BacASable(cumuls_precedents=precedents), 2026)

    assert depart == precedents


def test_le_point_de_depart_est_une_copie():
    """Le générateur écrit ses fichiers depuis ce dictionnaire ; l'appelant garde
    sa chaîne intacte."""
    precedents = {"periode": {}, "cumuls": {"brut_total": 1.0}}

    depart = cumuls_de_depart(BacASable(cumuls_precedents=precedents), 2026)
    depart["cumuls"]["brut_total"] = 999.0

    assert precedents["cumuls"]["brut_total"] == 1.0
