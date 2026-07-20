"""Tests comparateur multi-tiers."""

import pytest

from app.modules.payroll.backtest.comparator import compare_bulletins, detect_systemic_deltas
from app.modules.payroll.backtest.models import ReferenceBulletin, Verdict
from app.modules.payroll.backtest.reference_parser import parse_cegid_block
from app.modules.payroll.backtest.thresholds import default_thresholds
from tests.unit.payroll.backtest.fixtures import BUGNY_PAGE1, BUGNY_PAGE2

pytestmark = pytest.mark.unit


def _bugny_ref() -> ReferenceBulletin:
    return parse_cegid_block("BUGNY", BUGNY_PAGE1 + BUGNY_PAGE2)


def _bugny_payslip() -> dict:
    return {
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
        "structure_cotisations": {"total_salarial": 740.91, "total_patronal": 749.05},
        "pied_de_page": {"cout_total_employeur": 7207.57},
        "primes_non_soumises": [
            {"libelle": "Remboursement note de frais", "montant": 569.59},
        ],
    }


class TestComparator:
    def test_perfect_match(self):
        report = compare_bulletins(_bugny_payslip(), _bugny_ref())
        assert report.overall_verdict in (Verdict.PARFAIT, Verdict.OK)
        assert not report.has_tier_s_anomaly

    def test_brut_anomaly_detected(self):
        payslip = _bugny_payslip()
        payslip["salaire_brut"] = 2500.0
        report = compare_bulletins(payslip, _bugny_ref())
        assert report.has_tier_s_anomaly

    def test_systemic_detection(self):
        cfg = default_thresholds()
        cfg.systemic_min_employees = 2
        from app.modules.payroll.backtest.models import DiscrepancyLine, DiscrepancyReport

        reports = []
        for _ in range(3):
            reports.append(
                DiscrepancyReport(
                    matricule="X",
                    lines=[
                        DiscrepancyLine(
                            field_key="cout_total_employeur",
                            label="Coût employeur",
                            tier="C",
                            reference_value=7207.57,
                            actual_value=7217.57,
                            delta=10.0,
                            tolerance=0.5,
                            verdict=Verdict.ANOMALIE,
                        )
                    ],
                )
            )
        systemic = detect_systemic_deltas(reports, cfg)
        assert "cout_total_employeur" in systemic
        assert systemic["cout_total_employeur"] == 10.0
