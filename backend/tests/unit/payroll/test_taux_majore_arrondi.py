"""Le taux majoré des heures sup s'arrondit comme chez Quadra : 4 décimales, au pair."""

import pytest

from app.modules.payroll.engine.calcul_brut import taux_majore

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    "taux, majoration, attendu",
    [
        (12.689, 0.25, 15.8612),   # 15,86125 → 15,8612 (au pair) ; 17,33 h → 274,87 comme Quadra
        (13.001, 0.25, 16.2512),   # 16,25125 → 16,2512
        (12.31, 0.25, 15.3875),    # exact : inchangé
        (12.31, 0.50, 18.465),
        (12.9492, 0.25, 16.1865),
    ],
)
def test_taux_majore(taux, majoration, attendu):
    assert taux_majore(taux, majoration) == attendu


def test_la_ligne_d_heures_structurelles_redevient_celle_de_quadra():
    assert round(17.33 * taux_majore(12.689, 0.25), 2) == 274.87
