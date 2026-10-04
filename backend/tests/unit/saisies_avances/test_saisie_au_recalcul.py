"""Recalculer un bulletin garde la retenue de saisie sur salaire.

Corriger un bulletin le recalcule en entier, sur la même ligne `payslips` (même
id). La retenue était sautée dès qu'une déduction existait déjà pour ce
bulletin : le bulletin corrigé n'avait plus la ligne, et son net à payer
rendait au salarié la somme due au créancier. L'historique, lui, gardait la
déduction du premier calcul.
"""

from __future__ import annotations

from contextlib import contextmanager
from unittest.mock import patch

import pytest

from app.modules.saisies_avances.application import service

pytestmark = pytest.mark.unit

SAISIE = {
    "id": "saisie-1",
    "type": "saisie_arret",
    "calculation_mode": "fixe",
    "amount": 46.49,
    "priority": 4,
    "start_date": "2026-07-01",
    "creditor_name": "Créancier",
    "reference_legale": None,
}


class _Historique:
    """`salary_seizure_deductions`, en mémoire."""

    def __init__(self):
        self.lignes: list[dict] = []

    def inserer(self, seizure_id, payslip_id, year, month, brut, net, saisissable, preleve):
        self.lignes.append(
            {"seizure_id": seizure_id, "payslip_id": payslip_id, "deducted_amount": preleve}
        )

    def supprimer_du_bulletin(self, payslip_id):
        self.lignes = [l for l in self.lignes if l["payslip_id"] != payslip_id]


@contextmanager
def _base(historique: _Historique):
    with (
        patch.object(service, "get_seizures_for_period", return_value=[dict(SAISIE)]),
        patch.object(service, "get_advances_to_repay", return_value=[]),
        patch.object(service, "insert_seizure_deduction", side_effect=historique.inserer),
        patch.object(
            service,
            "supprimer_deductions_du_bulletin",
            side_effect=historique.supprimer_du_bulletin,
            create=True,
        ),
    ):
        yield


def _calcul(net: float) -> dict:
    return service.enrich_payslip(
        {"net_a_payer": net, "salaire_brut": 2088.9}, "e1", 2026, 7, payslip_id="bulletin-1"
    )


def test_le_premier_calcul_retient_la_saisie():
    historique = _Historique()
    with _base(historique):
        bulletin = _calcul(1616.01)
    assert bulletin["retenues_saisies"]["total_preleve"] == 46.49
    assert bulletin["net_a_payer"] == pytest.approx(1569.52)
    assert [l["deducted_amount"] for l in historique.lignes] == [46.49]


def test_le_recalcul_garde_la_retenue_et_une_seule_ligne_d_historique():
    historique = _Historique()
    with _base(historique):
        _calcul(1616.01)
        recalcule = _calcul(1616.01)
    assert recalcule["retenues_saisies"]["total_preleve"] == 46.49
    assert recalcule["net_a_payer"] == pytest.approx(1569.52)
    assert [l["deducted_amount"] for l in historique.lignes] == [46.49]


def test_un_recalcul_sans_rien_de_saisissable_efface_la_deduction_du_premier_calcul():
    """Une correction fait tomber le net sous le seuil : plus de retenue ce mois,
    et l'historique ne garde pas celle de l'ancien calcul."""
    historique = _Historique()
    with _base(historique):
        _calcul(1616.01)
        recalcule = _calcul(400.0)
    assert recalcule["retenues_saisies"]["total_preleve"] == 0
    assert historique.lignes == []
