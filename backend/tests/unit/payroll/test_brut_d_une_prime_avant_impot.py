"""Le net voulu d'une prime se vise avant impôt sur le revenu (12/10).

Le prélèvement à la source dépend du taux personnel du salarié : viser le net
après impôt faisait varier le brut d'un salarié à l'autre pour la même prime.
On vise donc le « net à payer avant impôt sur le revenu » du bulletin.
"""

from __future__ import annotations

import pytest

from app.modules.payroll.application.prime_nette import chercher_brut_de_prime

pytestmark = pytest.mark.unit


def _bulletins(taux_pas: float):
    def bulletin(montant: float) -> dict:
        avant_impot = round(1800.0 + montant * 0.78, 2)
        return {
            "net_a_payer": round(avant_impot * (1 - taux_pas / 100), 2),
            "pied_de_page": {"cout_total_employeur": round(2700.0 + montant * 1.2, 2)},
            "synthese_net": {
                "net_social_avant_impot": avant_impot,
                "impot_prelevement_a_la_source": {"taux": taux_pas},
            },
        }

    return bulletin


@pytest.mark.parametrize("taux_pas", [0.0, 1.6, 14.0])
def test_le_brut_ne_depend_pas_du_taux_de_prelevement_du_salarie(taux_pas):
    r = chercher_brut_de_prime(100.0, _bulletins(taux_pas))

    assert r["brut_calcule"] == pytest.approx(128.21, abs=0.02)
    assert r["net_obtenu"] == pytest.approx(100.0, abs=0.01)
    assert r["convergence"] is True
    assert r["net_a_payer_sans_prime"] == pytest.approx(1800.0)
