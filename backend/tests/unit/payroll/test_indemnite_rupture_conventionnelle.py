"""Indemnité de rupture conventionnelle : du dossier de départ au bulletin.

Le dossier rangeait le montant sous `montant`, alors que le bulletin, le solde
de tout compte et l'écran lisent `montant_negocie` : l'indemnité n'arrivait
jamais au bulletin, donc ni au net, ni à la DSN (bloc 52), ni à l'attestation.
Le montant négocié se saisit sur le départ ; il survit au recalcul du dossier.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.modules.payroll.engine.calcul_indemnites_sortie import (
    calculer_indemnites_sortie,
)
from app.modules.payroll.engine.bulletin import creer_bulletin_sortie
from tests.unit.payroll.helpers import build_test_contexte

pytestmark = pytest.mark.unit

_ICCP = "app.modules.payroll.engine.calcul_indemnites_sortie.calculer_indemnite_conges_restants"


def _salarie() -> dict:
    return {
        "id": "emp-1",
        "hire_date": "2020-01-01",
        "contract_type": "CDI",
        "salaire_de_base": {"valeur": 2400.0},
    }


def _depart(**extra) -> dict:
    return {
        "id": "exit-1",
        "exit_type": "rupture_conventionnelle",
        "last_working_day": "2026-10-31",
        "notice_period_days": 0,
        "notice_indemnity_type": "not_applicable",
        **extra,
    }


def _nets(net: float) -> dict:
    return {
        "net_a_payer": net,
        "net_imposable": net,
        "montant_net_social": net,
        "net_avant_impot": net,
    }


@patch(_ICCP, return_value={"montant": 0.0, "description": "ICCP", "details": {}})
def test_l_indemnite_du_dossier_arrive_au_bulletin_et_au_net(_iccp):
    dossier = calculer_indemnites_sortie(_salarie(), _depart(), MagicMock())
    minimum = dossier["indemnite_rupture_conventionnelle"]["montant_minimum"]
    assert minimum > 0

    bulletin = creer_bulletin_sortie(
        build_test_contexte(salaire_base=2400.0),
        2400.0,
        [],
        [],
        _nets(1900.0),
        [],
        dossier,
        2026,
        10,
    )

    lignes = bulletin["indemnites_sortie"]["lignes_exonerees"]
    assert [(l["libelle"], l["montant"]) for l in lignes] == [
        ("Indemnité de rupture conventionnelle", round(minimum, 2))
    ]
    assert bulletin["net_a_payer"] == round(1900.0 + minimum, 2)


@patch(_ICCP, return_value={"montant": 0.0, "description": "ICCP", "details": {}})
def test_le_montant_negocie_saisi_sur_le_depart_remplace_le_minimum(_iccp):
    dossier = calculer_indemnites_sortie(
        _salarie(), _depart(montant_negocie=15000.0), MagicMock()
    )

    rc = dossier["indemnite_rupture_conventionnelle"]
    assert rc["montant_negocie"] == 15000.0
    assert rc["montant_negocie_saisi"] == 15000.0
    assert rc["montant_minimum"] > 0
    assert dossier["total_gross_indemnities"] == 15000.0


@patch(_ICCP, return_value={"montant": 0.0, "description": "ICCP", "details": {}})
def test_le_montant_saisi_survit_au_recalcul_du_dossier(_iccp):
    premier = calculer_indemnites_sortie(
        _salarie(), _depart(montant_negocie=15000.0), MagicMock()
    )
    # « Calculer les indemnités » relit le départ, dossier précédent compris.
    recalcul = calculer_indemnites_sortie(
        _salarie(), _depart(calculated_indemnities=premier), MagicMock()
    )
    assert recalcul["indemnite_rupture_conventionnelle"]["montant_negocie"] == 15000.0

    # Effacer la saisie revient au minimum.
    efface = calculer_indemnites_sortie(
        _salarie(),
        _depart(calculated_indemnities=premier, montant_negocie=None),
        MagicMock(),
    )
    rc = efface["indemnite_rupture_conventionnelle"]
    assert rc["montant_negocie"] == rc["montant_minimum"]
    assert rc["montant_negocie_saisi"] is None
