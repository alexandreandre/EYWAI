"""Un prêt retenu ne réduit jamais le montant net social (audit du 03/11/2026, D 1b).

BOSS, « Montant net social », II.A.1 : « L'ensemble des revenus mentionnés sont
pris en compte même en cas de saisies sur salaire » ; un remboursement de prêt
n'est ni une cotisation ni une contribution (R. 844-1 II CSS). L'ancien logiciel
le déduisait dans trois sociétés. Martine retient l'échéance du net à payer,
après le calcul : le montant net social du moteur ne bouge pas. Déjà vrai
avant l'audit ; ce test le garde.
"""

from __future__ import annotations

import pytest

from tests.unit.employee_loans.test_retenue_partielle_dite import _enrichir, _pret

pytestmark = pytest.mark.unit


def test_un_pret_retenu_par_le_module_ne_touche_pas_le_net_social():
    bulletin = {
        "net_a_payer": 1619.54,
        "salaire_brut": 2105.04,
        "synthese_net": {"montant_net_social": 1619.54},
    }
    enrichi, _ = _enrichir(bulletin, [_pret()])

    assert enrichi["net_a_payer"] == pytest.approx(1418.46)
    assert enrichi["synthese_net"]["montant_net_social"] == pytest.approx(1619.54)
