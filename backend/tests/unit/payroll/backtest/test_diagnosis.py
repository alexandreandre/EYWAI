"""Tests diagnostic remediation."""

import pytest

from app.modules.payroll.backtest.comparator import compare_bulletins
from app.modules.payroll.backtest.diagnosis import diagnose_reports
from app.modules.payroll.backtest.models import Verdict
from app.modules.payroll.backtest.reference_parser import parse_cegid_block
from tests.unit.payroll.backtest.fixtures import BUGNY_PAGE1, BUGNY_PAGE2

pytestmark = pytest.mark.unit


class TestDiagnosis:
    def test_participation_missing_proposed(self):
        ref = parse_cegid_block("BUGNY", BUGNY_PAGE1 + BUGNY_PAGE2)
        payslip = {"salaire_brut": 2952.34, "net_a_payer": 1000.0, "synthese_net": {}}
        report = compare_bulletins(payslip, ref, employee_name="Michel BUGNY")
        proposals = diagnose_reports([report], {"BUGNY": ref})
        ids = [p.pattern_id for p in proposals]
        assert "participation_missing" in ids or "brut_absences_fictives" in ids

    def test_only_anomaly_reports_diagnosed(self):
        ref = parse_cegid_block("BUGNY", BUGNY_PAGE1 + BUGNY_PAGE2)
        payslip = {
            "salaire_brut": 2952.34,
            "net_a_payer": 5289.12,
            "synthese_net": {
                "net_imposable": 5600.16,
                "montant_net_social": 5479.53,
                "impot_prelevement_a_la_source": {"montant": 190.41, "taux": 3.40},
                "acompte_verse": 1000.0,
            },
            "participations": [{"brut": 3936.59}],
            "calcul_du_brut": [
                {"libelle": "Salaire de base", "montant": 2165.85},
                {"libelle": "Heures supplémentaires 25", "montant": 267.75},
                {"libelle": "Prime exceptionnelle", "montant": 150.0},
                {"libelle": "Prime ancienneté", "montant": 59.40},
            ],
            "pied_de_page": {"cout_total_employeur": 7207.57},
            "primes_non_soumises": [{"libelle": "Remboursement note de frais", "montant": 569.59}],
        }
        report = compare_bulletins(payslip, ref)
        assert report.overall_verdict in (Verdict.PARFAIT, Verdict.OK, Verdict.TOLERE)
        proposals = diagnose_reports([report], {"BUGNY": ref})
        assert len(proposals) == 0
