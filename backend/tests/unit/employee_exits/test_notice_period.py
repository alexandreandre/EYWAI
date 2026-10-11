"""
Tests unitaires du calcul de préavis (domain/notice_period.py).

[H6] Sources ouvertes le 11/10/2026 :
- service-public.gouv.fr F2883, « Démission d'un salarié » (vérifié le
  08/07/2026) : « La loi ne fixe pas la durée du préavis de démission. Le plus
  souvent, la durée du préavis est fixée par la convention ou l'accord collectif
  […] Le contrat de travail peut fixer la durée du préavis de démission. En
  l'absence de convention ou d'accord collectif ou de précision dans le contrat
  de travail, ce sont les usages pratiqués dans la localité ou la profession
  qui s'appliquent. »
- Code du travail, art. L1234-1 (Légifrance, en vigueur depuis le 01/05/2008) :
  préavis de licenciement d'un mois de six mois à moins de deux ans
  d'ancienneté, de deux mois au-delà ; moins de six mois : loi, convention ou
  usages. Aucune distinction entre cadres et non-cadres : les durées plus
  longues des cadres viennent des conventions.
"""

from datetime import date

import pytest

from app.modules.employee_exits.domain.notice_period import (
    compute_notice_period,
    compute_seniority_months,
    resolve_employee_category,
)


pytestmark = pytest.mark.unit


class TestResolveEmployeeCategory:
    def test_cadre(self):
        assert resolve_employee_category("Cadre") == ("cadre", True)

    def test_non_cadre(self):
        assert resolve_employee_category("Non-Cadre") == ("non_cadre", True)

    def test_empty_defaults_non_cadre(self):
        category, explicit = resolve_employee_category(None)
        assert category == "non_cadre"
        assert explicit is False


class TestComputeSeniorityMonths:
    def test_one_year(self):
        assert compute_seniority_months(date(2024, 1, 1), date(2025, 1, 1)) == 12


class TestComputeNoticePeriod:
    def test_no_collective_agreement_uses_legal_licenciement(self):
        result = compute_notice_period(
            exit_type="licenciement",
            hire_date=date(2022, 1, 1),
            reference_date=date(2025, 6, 1),
            statut="Employé",
            collective_agreement_name=None,
            collective_agreement_idcc=None,
        )
        assert result.days == 60
        assert result.source == "legal"
        assert "L1234-1" in result.detail
        assert any("Aucune convention collective" in w for w in result.warnings)

    @pytest.mark.parametrize("statut", ["Cadre", "Employé"])
    def test_le_preavis_legal_de_licenciement_ne_distingue_pas_les_cadres(self, statut):
        deux_ans = compute_notice_period(
            exit_type="licenciement",
            hire_date=date(2022, 1, 1),
            reference_date=date(2025, 6, 1),
            statut=statut,
        )
        un_an = compute_notice_period(
            exit_type="licenciement",
            hire_date=date(2024, 6, 1),
            reference_date=date(2025, 6, 1),
            statut=statut,
        )
        assert (deux_ans.days, un_an.days) == (60, 30)
        assert "adre" not in deux_ans.detail

    @pytest.mark.parametrize("statut", ["Cadre", "Employé"])
    def test_la_loi_ne_fixe_pas_de_preavis_de_demission(self, statut):
        result = compute_notice_period(
            exit_type="demission",
            hire_date=date(2022, 1, 1),
            reference_date=date(2025, 6, 1),
            statut=statut,
        )
        assert result.days == 0
        assert result.source == "none"
        assert result.applicable is True
        assert "La loi ne fixe pas la durée du préavis de démission" in result.detail
        assert "légal" not in result.label + result.detail

    def test_convention_overrides_legal(self):
        rules = {
            "preavis": {
                "demission": {
                    "non_cadre": [
                        {"anciennete_mois_min": 24, "jours": 75},
                    ]
                }
            }
        }
        result = compute_notice_period(
            exit_type="demission",
            hire_date=date(2022, 1, 1),
            reference_date=date(2025, 6, 1),
            statut="Employé",
            collective_agreement_name="Syntec",
            collective_agreement_idcc="1486",
            cc_rules=rules,
        )
        assert result.days == 75
        assert result.source == "convention"

    def test_convention_without_preavis_rules_falls_back_legal(self):
        result = compute_notice_period(
            exit_type="licenciement",
            hire_date=date(2022, 1, 1),
            reference_date=date(2025, 6, 1),
            statut="Employé",
            collective_agreement_name="Syntec",
            collective_agreement_idcc="1486",
            cc_rules={"prime_anciennete": {}},
        )
        assert result.days == 60
        assert result.source == "legal"
        assert any("Aucune règle de préavis extraite" in w for w in result.warnings)

    def test_demission_sans_regle_de_convention_duree_a_saisir(self):
        result = compute_notice_period(
            exit_type="demission",
            hire_date=date(2022, 1, 1),
            reference_date=date(2025, 6, 1),
            statut="Employé",
            collective_agreement_name="Syntec",
            collective_agreement_idcc="1486",
            cc_rules={"prime_anciennete": {}},
        )
        assert result.days == 0
        assert result.source == "none"
        assert any("Aucune règle de préavis extraite" in w for w in result.warnings)

    def test_rupture_conventionnelle_not_applicable(self):
        result = compute_notice_period(
            exit_type="rupture_conventionnelle",
            hire_date=date(2022, 1, 1),
            reference_date=date(2025, 6, 1),
            statut="Employé",
        )
        assert result.days == 0
        assert result.source == "not_applicable"
        assert result.applicable is False

    def test_fin_cdd_not_applicable(self):
        """Un CDD prend fin de plein droit à son terme : pas de préavis."""
        result = compute_notice_period(
            exit_type="fin_cdd",
            hire_date=date(2026, 6, 29),
            reference_date=date(2026, 6, 30),
            statut="Employé",
        )
        assert result.days == 0
        assert result.source == "not_applicable"
        assert result.applicable is False
        assert "L1243-5" in result.detail

    def test_transfert_not_applicable(self):
        """Transfert intra-groupe : le contrat se poursuit, pas de préavis."""
        result = compute_notice_period(
            exit_type="transfert",
            hire_date=date(2026, 1, 23),
            reference_date=date(2026, 2, 28),
            statut="Employé",
        )
        assert result.days == 0
        assert result.source == "not_applicable"
        assert result.applicable is False
        assert "solde de tout compte" in result.detail

    def test_gross_misconduct_zero(self):
        result = compute_notice_period(
            exit_type="licenciement",
            hire_date=date(2022, 1, 1),
            reference_date=date(2025, 6, 1),
            statut="Employé",
            is_gross_misconduct=True,
        )
        assert result.days == 0
        assert result.source == "not_applicable"

    def test_missing_hire_date_warns(self):
        result = compute_notice_period(
            exit_type="demission",
            hire_date=None,
            reference_date=date(2025, 6, 1),
            statut="Employé",
        )
        assert any("Date d'embauche" in w for w in result.warnings)

    def test_seniority_under_six_months(self):
        result = compute_notice_period(
            exit_type="licenciement",
            hire_date=date(2025, 4, 1),
            reference_date=date(2025, 6, 1),
            statut="Employé",
        )
        assert result.days == 0
        assert result.source == "legal"
