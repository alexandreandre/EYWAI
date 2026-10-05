"""Export « Prêts employeur » : des écritures équilibrées, au compte du net de la société."""

from unittest.mock import patch

import pytest

from app.modules.exports.infrastructure import export_prets_employeur as module

pytestmark = pytest.mark.unit

LIGNES_DU_REGISTRE = [
    {"date_ecriture": "2026-09-30", "journal": "PAI", "compte_comptable": "274000",
     "libelle": "Remboursement prêt employeur Septembre 2026", "debit": 0.0, "credit": 200.0,
     "reference_export": "OD_PAIE_2026-09", "periode_paie": "2026-09"},
    {"date_ecriture": "2026-09-30", "journal": "PAI", "compte_comptable": "762400",
     "libelle": "Intérêts prêt employeur Septembre 2026", "debit": 0.0, "credit": 12.5,
     "reference_export": "OD_PAIE_2026-09", "periode_paie": "2026-09"},
    {"date_ecriture": "2026-09-30", "journal": "PAI", "compte_comptable": "425100",
     "libelle": "Acomptes Septembre 2026", "debit": 0.0, "credit": 800.0,
     "reference_export": "OD_PAIE_2026-09", "periode_paie": "2026-09"},
]


def test_ecritures_de_pret_equilibrees_par_le_net():
    """Seules des lignes au crédit (274, intérêts) : l'écriture ne
    s'équilibrait pas. La retenue a pour contrepartie le net à payer."""
    with patch.object(
        module, "build_payroll_ledger", return_value=(LIGNES_DU_REGISTRE, {}, {})
    ), patch.object(module, "compte_du_net_a_payer", return_value="42100000"):
        ecritures = module.generate_prets_ecritures("societe", "2026-09")

    assert {e["compte_comptable"] for e in ecritures} == {"274000", "762400", "42100000"}
    assert round(sum(e["debit"] for e in ecritures), 2) == round(
        sum(e["credit"] for e in ecritures), 2
    ) == 212.5
    contrepartie = next(e for e in ecritures if e["compte_comptable"] == "42100000")
    assert contrepartie["journal"] == "PAI"
    assert contrepartie["debit"] == 212.5


def test_sans_pret_pas_d_ecriture():
    with patch.object(
        module, "build_payroll_ledger", return_value=(LIGNES_DU_REGISTRE[2:], {}, {})
    ), patch.object(module, "compte_du_net_a_payer", return_value="42100000"):
        assert module.generate_prets_ecritures("societe", "2026-09") == []
