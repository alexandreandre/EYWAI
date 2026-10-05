"""Comptes du net et du PAS : jamais faux en silence."""

from unittest.mock import patch

import pytest

from app.modules.exports.infrastructure import export_acomptes, export_saisies
from app.modules.exports.infrastructure import export_ecritures_comptables as od_module

pytestmark = pytest.mark.unit


class _BaseEnPanne:
    def table(self, nom):
        raise RuntimeError("base injoignable")


def test_defauts_codes_alignes_sur_la_base():
    """La migration du 05/08 a corrigé la base (421, 442) ; le code gardait
    425000 pour le net et 425100 pour le PAS."""
    assert od_module.DEFAULT_MAPPINGS["net_a_payer"]["compte_comptable"] == "421000"
    assert od_module.DEFAULT_MAPPINGS["pas"]["compte_comptable"] == "442000"


def test_plan_comptable_illisible_bloque_l_export():
    """Sans le plan de la société, l'OD sortirait aux comptes par défaut."""
    with patch.object(od_module, "supabase", _BaseEnPanne()), pytest.raises(RuntimeError):
        od_module.get_accounting_mappings("societe")


@pytest.mark.parametrize(
    ("module", "generer", "donnees"),
    [
        (
            export_acomptes,
            lambda m: m.generate_acomptes_ecritures(
                "societe", "2026-09", [],
                [{"accounting_account": "4251", "amount_repaid": 800.0, "employee_name": "Salarié"}],
            ),
            None,
        ),
        (
            export_saisies,
            lambda m: m.generate_saisies_ecritures(
                "societe", "2026-09",
                [{"accounting_account": "4271", "deducted_amount": 46.49, "employee_name": "Salarié"}],
            ),
            None,
        ),
    ],
)
def test_retenue_de_detail_au_compte_du_net_de_la_societe(module, generer, donnees):
    with patch.object(
        od_module,
        "get_accounting_mappings",
        return_value={"net_a_payer": {"compte_comptable": "42100000"}},
    ):
        ecritures = generer(module)
    assert ecritures[0]["compte_comptable"] == "42100000"
    assert ecritures[0]["debit"] > 0
