"""La retenue d'une avance sur salaire ne dépasse pas le dixième du salaire (L3251-3).

Les acomptes sur un travail en cours ne sont pas des avances : ils restent retenus
en entier. Ce qui dépasse le dixième reste dû pour les bulletins suivants, et le
bulletin le dit.
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from app.modules.saisies_avances.application import service
from app.modules.saisies_avances.domain import rules

pytestmark = pytest.mark.unit


def _avance(id_="a1", type_="avance_salaire", reste=800.0, **champs):
    return {
        "id": id_,
        "status": "paid",
        "advance_type": type_,
        "approved_amount": reste,
        "remaining_amount": reste,
        "repayment_mode": "single",
        "repayment_months": 1,
        "requested_date": "2026-09-10",
        **champs,
    }


def _enrichir(net, avances, existant=None):
    ecritures = MagicMock()
    with (
        patch.object(service, "get_seizures_for_period", return_value=[]),
        patch.object(service, "get_advances_to_repay", return_value=avances),
        patch.object(service, "get_existing_repayment", return_value=existant),
        patch.object(service, "supprimer_deductions_du_bulletin"),
        patch.object(service, "insert_advance_repayment", ecritures.insert),
        patch.object(service, "advance_repository", ecritures.depot),
    ):
        return service.enrich_payslip({"net_a_payer": net}, "e1", 2026, 10, payslip_id="b1"), ecritures


def _codes(bulletin):
    return [a["code"] for a in bulletin.get("alertes_baremes") or []]


def test_dixieme_arrondi_au_centime_inferieur():
    assert rules.dixieme_du_salaire(Decimal("1999.99")) == Decimal("199.99")
    assert rules.dixieme_du_salaire(Decimal("-5")) == Decimal("0")


def test_une_avance_en_une_fois_est_plafonnee_et_le_reste_reste_du():
    bulletin, ecritures = _enrichir(2000.0, [_avance()])

    assert bulletin["net_a_payer"] == pytest.approx(1800.0)
    assert bulletin["remboursements_avances"]["total_rembourse"] == 200.0
    appel = ecritures.insert.call_args_list[0].args
    assert appel[4] == 200.0 and appel[5] == 600.0
    assert ecritures.depot.update.call_args.args[1]["remaining_amount"] == 600.0
    assert _codes(bulletin) == ["avance_retenue_au_dixieme"]


def test_le_message_dit_ce_qui_reste():
    bulletin, _ = _enrichir(2000.0, [_avance()])
    message = bulletin["alertes_baremes"][0]["message"]
    assert "200,00 €" in message and "600,00 €" in message and "L3251-3" in message


def test_sous_le_dixieme_rien_ne_change():
    bulletin, ecritures = _enrichir(2000.0, [_avance(reste=150.0)])

    assert bulletin["net_a_payer"] == pytest.approx(1850.0)
    assert ecritures.insert.call_args_list[0].args[4] == 150.0
    assert _codes(bulletin) == []


def test_le_dixieme_vaut_pour_toutes_les_avances_du_mois():
    bulletin, ecritures = _enrichir(2000.0, [_avance("a1", reste=150.0), _avance("a2", reste=150.0)])

    assert [c.args[4] for c in ecritures.insert.call_args_list] == [150.0, 50.0]
    assert bulletin["net_a_payer"] == pytest.approx(1800.0)
    assert _codes(bulletin) == ["avance_retenue_au_dixieme"]


def test_mensualite_plafonnee():
    bulletin, ecritures = _enrichir(
        1000.0, [_avance(reste=600.0, repayment_mode="multiple", repayment_months=2)]
    )

    assert ecritures.insert.call_args_list[0].args[4] == 100.0
    assert bulletin["net_a_payer"] == pytest.approx(900.0)


@pytest.mark.parametrize("type_", ["acompte_salaire", "acompte_prime"])
def test_un_acompte_n_est_pas_une_avance(type_):
    bulletin, ecritures = _enrichir(2000.0, [_avance(type_=type_)])

    assert ecritures.insert.call_args_list[0].args[4] == 800.0
    assert bulletin["net_a_payer"] == pytest.approx(1200.0)
    assert _codes(bulletin) == []


def test_un_acompte_ne_consomme_pas_le_dixieme():
    _, ecritures = _enrichir(
        2000.0, [_avance("a1", type_="acompte_salaire", reste=500.0), _avance("a2", reste=300.0)]
    )

    assert [c.args[4] for c in ecritures.insert.call_args_list] == [500.0, 200.0]


def test_au_recalcul_la_retenue_deja_faite_compte():
    bulletin, ecritures = _enrichir(
        2000.0,
        [_avance("a1", reste=0.01), _avance("a2", reste=300.0)],
        existant={"repayment_amount": 150.0, "remaining_after": 0.0},
    )

    assert bulletin["remboursements_avances"]["total_rembourse"] == 300.0
    assert ecritures.insert.call_args_list == []
