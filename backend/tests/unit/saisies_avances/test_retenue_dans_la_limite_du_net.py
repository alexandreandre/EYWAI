"""Une retenue d'avance ou de saisie ne prend que ce que le net permet. [G8]

L'enrichissement annonçait la retenue entière, soldait l'avance et enregistrait
la saisie entière, puis ramenait le net à 0 : la différence n'était ni retenue
ni reportée. Un net de 50 € et une avance de 90,90 € donnaient un net de 0 et
une avance soldée, 40,90 € disparaissaient. Un net négatif était effacé, et son
report n'était plus proposé.

Désormais :
- on retient au plus le net disponible, et le reste dû de l'avance baisse du
  montant réellement retenu ;
- rien n'est retenu sur un net nul ou négatif : l'avance reste due, le net
  négatif reste tel quel et son report reste proposé ;
- la saisie passe d'abord (l'employeur en répond envers le créancier), l'avance
  prend ce qui reste.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.modules.saisies_avances.application import service

from .test_quotite_saisissable_legale import BAREME

pytestmark = pytest.mark.unit


def _avance(montant: float) -> dict:
    return {
        "id": "avance-1",
        "status": "paid",
        "advance_type": "avance_salaire",
        "accounting_account": "4251",
        "approved_amount": montant,
        "remaining_amount": montant,
        "repayment_mode": "single",
        "repayment_months": 1,
        "requested_date": "2026-09-01",
        "payment_date": "2026-09-02",
    }


SAISIE_FIXE_50 = {
    "id": "saisie-1",
    "type": "saisie_arret",
    "calculation_mode": "fixe",
    "amount": 50.0,
    "priority": 4,
    "creditor_name": "Créancier",
}


def _enrichir(net: float, avances: list, saisies: list | None = None):
    ecritures = MagicMock()
    with (
        patch.object(service, "get_seizures_for_period", return_value=list(saisies or [])),
        patch.object(service, "get_bareme_quotite_saisissable", return_value=BAREME, create=True),
        patch.object(service, "get_advances_to_repay", return_value=[dict(a) for a in avances]),
        patch.object(service, "get_existing_repayment", return_value=None),
        patch.object(service, "supprimer_deductions_du_bulletin"),
        patch.object(service, "insert_advance_repayment", ecritures.remboursement),
        patch.object(service, "insert_seizure_deduction", ecritures.saisie),
        patch.object(service, "advance_repository", ecritures.depot),
    ):
        bulletin = service.enrich_payslip(
            {"net_a_payer": net, "salaire_brut": 2000.0},
            "e1",
            2026,
            9,
            payslip_id="bulletin-1",
        )
    return bulletin, ecritures


def test_net_insuffisant_on_retient_le_net_et_l_avance_reste_due_du_reste():
    bulletin, ecritures = _enrichir(50.0, [_avance(90.90)])

    assert bulletin["net_a_payer"] == pytest.approx(0.0)
    assert bulletin["remboursements_avances"]["total_rembourse"] == pytest.approx(50.0)
    avance = bulletin["remboursements_avances"]["avances"][0]
    assert avance["montant"] == pytest.approx(50.0)
    assert avance["reste_apres"] == pytest.approx(40.90)
    # Historique et reste dû : le montant réellement retenu, pas l'avance entière.
    (args,) = [c.args for c in ecritures.remboursement.call_args_list]
    assert args[4] == pytest.approx(50.0)
    assert args[5] == pytest.approx(40.90)
    (maj,) = [c.args[1] for c in ecritures.depot.update.call_args_list]
    assert maj["remaining_amount"] == pytest.approx(40.90)


@pytest.mark.parametrize("net", [0.0, -88.30])
def test_rien_n_est_retenu_sur_un_net_nul_ou_negatif(net):
    bulletin, ecritures = _enrichir(net, [_avance(90.90)], [SAISIE_FIXE_50])

    # Le net négatif reste : c'est lui que le report du mois suivant reprend.
    assert bulletin["net_a_payer"] == pytest.approx(net)
    assert bulletin["remboursements_avances"]["total_rembourse"] == 0.0
    assert bulletin["remboursements_avances"]["avances"] == []
    assert bulletin["retenues_saisies"]["total_preleve"] == 0.0
    ecritures.remboursement.assert_not_called()
    ecritures.saisie.assert_not_called()
    ecritures.depot.update.assert_not_called()


def test_saisie_puis_avance_jamais_plus_que_le_net():
    bulletin, ecritures = _enrichir(1000.0, [_avance(990.0)], [SAISIE_FIXE_50])

    assert bulletin["retenues_saisies"]["total_preleve"] == pytest.approx(50.0)
    assert bulletin["remboursements_avances"]["total_rembourse"] == pytest.approx(950.0)
    assert bulletin["net_a_payer"] == pytest.approx(0.0)
    (maj,) = [c.args[1] for c in ecritures.depot.update.call_args_list]
    assert maj["remaining_amount"] == pytest.approx(40.0)


def test_net_suffisant_l_avance_est_retenue_en_entier():
    bulletin, _ = _enrichir(1000.0, [_avance(90.90)])

    assert bulletin["net_a_payer"] == pytest.approx(909.10)
    assert bulletin["remboursements_avances"]["avances"][0]["reste_apres"] == 0.0
