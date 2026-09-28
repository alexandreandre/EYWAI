"""Les heures sup déclarées depuis le bulletin restent lisibles par le générateur.

Le parcours de correction lui-même (déclaration, recalcul) est couvert par
`test_corrections.py`.
"""

import pytest

from app.modules.payslips.domain.heures_sup import (
    LIBELLE_HS_DECLAREES,
    LIBELLE_HS_DECLAREES_50,
)

pytestmark = pytest.mark.unit


class TestLibellesDesSaisiesDeclarees:
    """Les libellés posés doivent rester lisibles par le générateur."""

    def test_reconnus_comme_heures_sup_conjoncturelles(self):
        from app.modules.payroll.documents.payslip_generator import (
            _heures_sup_conjoncturelles_from_monthly_inputs,
        )

        lignes = [
            {"name": LIBELLE_HS_DECLAREES, "payroll_quantity": 13.0},
            {"name": LIBELLE_HS_DECLAREES_50, "payroll_quantity": 3.5},
        ]
        assert _heures_sup_conjoncturelles_from_monthly_inputs(lignes) == (13.0, 3.5)

    def test_le_premier_palier_ne_contient_pas_50(self):
        """« 50 » dans le libellé bascule la ligne sur le second palier."""
        assert "50" not in LIBELLE_HS_DECLAREES
        assert "50" in LIBELLE_HS_DECLAREES_50

    def test_aucun_libelle_ne_dit_structurelle(self):
        """« struct » ferait ignorer la ligne par le générateur."""
        assert "struct" not in LIBELLE_HS_DECLAREES.lower()
        assert "struct" not in LIBELLE_HS_DECLAREES_50.lower()
