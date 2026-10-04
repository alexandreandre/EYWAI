"""Une avance se retient une seule fois du net à payer, par l'enrichissement.

Audit du 04/10/2026, vérifié en bac à sable sur un bulletin réel de septembre :
une avance de 800 € faisait baisser le net de 1 600 €. Le générateur heures la
retirait déjà dans le moteur (ligne « Remboursement prêt salarié »), puis
l'enrichissement d'après enregistrement la retirait encore. Le générateur ne la
retire plus : seul l'enrichissement le fait, comme au forfait jours.

Il la retenait aussi « à moitié » : dès qu'un acompte était saisi en variable
du mois (`acompte_verse`), il ne retirait plus l'avance du net, tout en la
marquant remboursée.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.modules.saisies_avances.application import service

pytestmark = pytest.mark.unit

AVANCE = {
    "id": "avance-1",
    "status": "paid",
    "advance_type": "acompte_salaire",
    "accounting_account": "4251",
    "approved_amount": 800.0,
    "remaining_amount": 800.0,
    "repayment_mode": "single",
    "repayment_months": 1,
    "requested_date": "2026-09-10",
}


def _enrichir(bulletin: dict) -> tuple[dict, MagicMock]:
    ecritures = MagicMock()
    with (
        patch.object(service, "get_seizures_for_period", return_value=[]),
        patch.object(service, "get_advances_to_repay", return_value=[dict(AVANCE)]),
        patch.object(service, "get_existing_repayment", return_value=None),
        patch.object(service, "supprimer_deductions_du_bulletin"),
        patch.object(service, "insert_advance_repayment", ecritures.insert),
        patch.object(service, "advance_repository", ecritures.depot),
    ):
        return service.enrich_payslip(bulletin, "e1", 2026, 9, payslip_id="bulletin-1"), ecritures


def test_l_avance_est_retenue_une_fois():
    bulletin, ecritures = _enrichir({"net_a_payer": 2130.50})

    assert bulletin["net_a_payer"] == pytest.approx(1330.50)
    assert bulletin["remboursements_avances"]["total_rembourse"] == 800.0
    assert [c.args[4] for c in ecritures.insert.call_args_list] == [800.0]


def test_un_acompte_du_mois_n_empeche_pas_de_retenir_l_avance():
    """300 € d'acompte saisis en variable sont déjà dans le net du moteur ;
    l'avance de 800 € du module « Avances » s'y ajoute, une fois."""
    bulletin, ecritures = _enrichir(
        {"net_a_payer": 1830.50, "synthese_net": {"acompte_verse": 300.0}}
    )

    assert bulletin["net_a_payer"] == pytest.approx(1030.50)
    assert [c.args[4] for c in ecritures.insert.call_args_list] == [800.0]
