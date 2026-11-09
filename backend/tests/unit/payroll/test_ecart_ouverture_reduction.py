"""R-193 : au premier mois calculé après la reprise, un écart d'ouverture se signale.

Le premier mois régularise tout l'écart entre la réduction due d'après les
cumuls repris et celle que l'ancien logiciel a appliquée. Ce n'était visible que
dans la sortie d'un script.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from unittest.mock import patch

import pytest

from app.modules.payroll.engine.calcul_reduction_generale import (
    calculer_coefficient_rgdu,
    ecart_d_ouverture_reduction,
    signaler_ecart_d_ouverture_au_premier_mois,
)
from tests.unit.payroll.test_reduction_generale_point_de_depart import _contexte

pytestmark = pytest.mark.unit

_SMIC = "app.shared.reprise_paie.fin_de_la_reprise_au_premier_mois"
BRUT = 18_900.0  # 9 mois à 2 100 €
HEURES = 1_521.0  # 9 × 169 h


def _due(brut: float = BRUT, heures: float = HEURES) -> float:
    c, _ = calculer_coefficient_rgdu(
        brut, round(heures * 12.02, 2), tmin=0.02, tdelta=0.3781, p=1.75, point_sortie=3.0
    )
    return round(brut * c, 2)


def _cumuls(deja: float) -> dict:
    return {
        "brut_annee_civile": BRUT,
        "heures_remunerees": HEURES,
        "reduction_generale_patronale": -deja,
    }


def _signaler(contexte, fin=date(2026, 9, 30)):
    with patch(_SMIC, return_value=fin):
        signaler_ecart_d_ouverture_au_premier_mois(contexte, "soc", 2026, 10)


def _codes(contexte) -> list[str]:
    return [a["code"] for a in contexte.alertes_baremes]


def test_un_trou_de_reduction_a_l_ouverture_se_signale():
    """Erreur injectée : l'ancien logiciel a appliqué 500 € de moins que la formule."""
    contexte = _contexte(_cumuls(_due() - 500.0), 2026, 10)
    _signaler(contexte)
    alerte = next(a for a in contexte.alertes_baremes if a["code"] == "ecart_ouverture_reduction_generale")
    assert not alerte.get("critique")
    assert "500,00" in alerte["message"]
    assert "30/09/2026" in alerte["message"]
    assert "À vérifier" in alerte["message"]


def test_une_salariee_sans_reduction_de_l_annee_se_signale():
    contexte = _contexte(_cumuls(0.0), 2026, 10)
    _signaler(contexte)
    assert "ecart_ouverture_reduction_generale" in _codes(contexte)


def test_un_ecart_d_arrondi_ne_se_signale_pas():
    """Le palier du script : max(1 €, brut cumulé × 0,0001)."""
    contexte = _contexte(_cumuls(_due() - 1.5), 2026, 10)
    _signaler(contexte)
    assert "ecart_ouverture_reduction_generale" not in _codes(contexte)


def test_les_mois_suivants_ne_se_signalent_pas():
    contexte = _contexte(_cumuls(_due() - 500.0), 2026, 11)
    _signaler(contexte, fin=None)
    assert _codes(contexte) == []


def test_une_ouverture_juste_ne_se_signale_pas():
    assert ecart_d_ouverture_reduction(_contexte(_cumuls(_due()), 2026, 10))["ecart"] == 0.0
    contexte = _contexte(_cumuls(_due()), 2026, 10)
    _signaler(contexte)
    assert _codes(contexte) == []


@pytest.mark.parametrize("module", ["payslip_run_heures", "payslip_run_forfait"])
def test_les_deux_calculs_signalent_l_ecart(module):
    source = (
        Path(__file__).resolve().parents[3] / f"app/modules/payroll/documents/{module}.py"
    ).read_text(encoding="utf-8")
    assert "signaler_ecart_d_ouverture_au_premier_mois(contexte, company_id, year, month)" in source
