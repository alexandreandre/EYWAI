"""Net imposable négatif : aucun prélèvement à la source (audit du 03/11/2026, D 4a).

Fiche DSN-info n° 1810 : un net fiscal négatif se déclare tel quel, mais
« Montant soumis au PAS » et « Montant de prélèvement à la source » valent 0.00.
Le moteur prenait le net imposable négatif comme assiette et rendait l'impôt au
salarié (-0,16 € sur deux bulletins de février et mars 2026 au filet).
"""

from __future__ import annotations

import pytest

from app.modules.payroll.engine import calcul_net
from tests.unit.payroll.helpers import build_test_contexte

pytestmark = pytest.mark.unit


def _nets(brut, cotisations, taux=13.3):
    contexte = build_test_contexte(taux_pas=taux)
    contexte.year, contexte.month = 2026, 10
    return calcul_net.calculer_net_et_impot(contexte, brut, [], cotisations, [], 0.0)


def test_un_net_imposable_negatif_n_a_ni_assiette_ni_prelevement():
    nets = _nets(0.0, 31.65)
    assert nets["net_imposable"] == pytest.approx(-31.65)
    assert nets["base_pas"] == 0.0
    assert nets["montant_impot_pas"] == 0.0


def test_le_net_a_payer_ne_recoit_pas_d_impot_rendu():
    nets = _nets(0.0, 31.65)
    assert nets["net_a_payer"] == pytest.approx(-31.65)


def test_un_net_imposable_positif_garde_son_assiette():
    nets = _nets(2000.0, 450.0)
    assert nets["base_pas"] == pytest.approx(nets["net_imposable"])
