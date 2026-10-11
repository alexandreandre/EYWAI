"""L'avantage en nature d'un prêt suit le mois du bulletin. [D3] [G9]

Relevé à l'écran (vidéo G, 11/10/2026) : un prêt de 2 400 € à 1 %, débutant le
01/10/2026, a donné « Avantages en nature 4,62 € » au bulletin de septembre, où
aucune échéance n'est prélevée. Le calcul prenait les prêts actifs du jour et
leur capital restant du jour, quel que soit le mois du bulletin : septembre
recevait l'avantage d'un prêt pas encore versé, et un mois régénéré après le
prélèvement de son échéance perdait la part de capital qu'elle remboursait.

Règle : l'avantage ne compte qu'à partir du mois du premier versement du prêt
(sa date de début), sur le capital restant dû au début du mois du bulletin —
le prêt moins le capital remboursé les mois d'avant.
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import patch

import pytest

from app.modules.employee_loans.domain.rules import capital_du_au_debut_du_mois
from app.modules.employee_loans.infrastructure import payroll_queries

pytestmark = pytest.mark.unit

PRET = {
    "id": "pret-1",
    "principal_amount": 2400.0,
    "annual_interest_rate": 0.01,
    "start_date": "2026-10-01",
    "status": "active",
    "remaining_capital": 2200.92,
}
#: L'échéance d'octobre prélevée sur le bulletin d'octobre.
ECHEANCE_OCTOBRE = {"loan_id": "pret-1", "year": 2026, "month": 10, "capital_amount": 199.08}


class TestCapitalDuAuDebutDuMois:
    def test_rien_avant_le_mois_du_premier_versement(self):
        assert capital_du_au_debut_du_mois(PRET, [], 2026, 9) == Decimal("0")

    def test_le_prêt_entier_le_mois_du_premier_versement(self):
        assert capital_du_au_debut_du_mois(PRET, [], 2026, 10) == Decimal("2400.00")

    def test_l_echeance_du_mois_ne_baisse_pas_le_capital_de_ce_mois(self):
        assert capital_du_au_debut_du_mois(PRET, [ECHEANCE_OCTOBRE], 2026, 10) == Decimal("2400.00")

    def test_le_mois_suivant_part_du_capital_rembourse(self):
        assert capital_du_au_debut_du_mois(PRET, [ECHEANCE_OCTOBRE], 2026, 11) == Decimal("2200.92")

    def test_jamais_negatif(self):
        rembourse = [{"year": 2026, "month": 10, "capital_amount": 2500.0}]
        assert capital_du_au_debut_du_mois(PRET, rembourse, 2026, 12) == Decimal("0")


def _avantage(mois: int, remboursements=(ECHEANCE_OCTOBRE,), prets=(PRET,)) -> float:
    with patch.object(payroll_queries, "get_legal_interest_rate", return_value=Decimal("0.0352")), patch.object(
        payroll_queries, "get_loans_for_benefit_in_kind", return_value=list(prets)
    ), patch.object(
        payroll_queries, "get_capital_repayments", return_value=list(remboursements)
    ):
        return payroll_queries.compute_total_loan_benefit_in_kind("emp-1", 2026, mois)


class TestAvantageDuBulletin:
    def test_septembre_n_a_pas_d_avantage_pour_un_pret_d_octobre(self):
        assert _avantage(9) == 0.0

    def test_octobre_sur_le_pret_entier_meme_apres_son_echeance(self):
        # (3,52 % − 1 %) × 2 400 ÷ 12
        assert _avantage(10) == pytest.approx(5.04)

    def test_novembre_sur_le_capital_restant_au_1er_novembre(self):
        # (3,52 % − 1 %) × 2 200,92 ÷ 12
        assert _avantage(11) == pytest.approx(4.62)

    def test_un_pret_solde_depuis_ne_compte_plus(self):
        solde = {**PRET, "status": "repaid", "remaining_capital": 0}
        tout = [{"loan_id": "pret-1", "year": 2026, "month": 10, "capital_amount": 2400.0}]
        assert _avantage(11, remboursements=tout, prets=[solde]) == 0.0
        # Mais octobre, régénéré, garde l'avantage de son mois.
        assert _avantage(10, remboursements=tout, prets=[solde]) == pytest.approx(5.04)
