"""
Tests unitaires des règles de suivi contingent (domain/contingent_rules.py).
"""

from datetime import date

from app.modules.repos_compensateur.domain.contingent_rules import (
    ContingentEmployeeInput,
    ContingentSettings,
    compute_contingent_breakdown,
    compute_effective_management_contingent,
    compute_pause_deduction,
    compute_prorated_management_contingent,
    compute_structural_hours,
    compute_weeks_worked,
)
from app.modules.repos_compensateur.domain.rules import (
    extraire_heures_hs_conjoncturelles_du_bulletin,
    extraire_heures_hs_du_bulletin,
)


def _settings_client_excel() -> ContingentSettings:
    """Paramètres alignés sur le fichier Excel client (360 h, pauses activées)."""
    return ContingentSettings(
        legal_cor_contingent_hours=220.0,
        management_contingent_hours=360.0,
        hours_per_rest_day=7.0,
        include_structural_hours=True,
        pause_deduction_enabled=True,
        pause_hs_deduction_per_workday=0.058765,
        workdays_per_year_for_pause=260,
    )


def _employee_with_paid_hours(paid_total: float) -> ContingentEmployeeInput:
    """Simule un salarié 39 h avec HS payées sur décembre."""
    bulletins = {}
    if paid_total > 0:
        bulletins[12] = {
            "calcul_du_brut": [
                {
                    "libelle": "Heures suppl. majorées à 25%",
                    "quantite": paid_total,
                }
            ]
        }
    return ContingentEmployeeInput(
        employee_id="emp-1",
        first_name="Michel",
        last_name="BUGNY",
        hire_date=date(1997, 4, 7),
        duree_hebdomadaire=39.0,
        opening_balance_hours=0.0,
        validated_repos_requests=[],
        bulletins_par_mois=bulletins,
    )


class TestExtractionHsConjoncturelles:
    def test_exclut_structurelles(self):
        data = {
            "calcul_du_brut": [
                {"libelle": "Heures suppl. structurelles majorées à 10%", "quantite": 10},
                {"libelle": "Heures suppl. majorées à 25%", "quantite": 5},
            ]
        }
        assert extraire_heures_hs_conjoncturelles_du_bulletin(data) == 5.0
        assert extraire_heures_hs_du_bulletin(data) == 15.0


class TestExcelScenarios:
    def test_cotte_low_paid_hours(self):
        settings = _settings_client_excel()
        emp = _employee_with_paid_hours(3.0)
        ref = date(2025, 12, 31)
        breakdown = compute_contingent_breakdown(emp, settings, 2025, ref)

        assert breakdown.paid_hours == 3.0
        assert breakdown.consumed_hours < 250
        assert breakdown.margin_hours > 0

    def test_margin_formula(self):
        settings = _settings_client_excel()
        emp = _employee_with_paid_hours(3.0)
        ref = date(2025, 12, 31)
        breakdown = compute_contingent_breakdown(emp, settings, 2025, ref)
        assert breakdown.margin_hours == round(
            settings.management_contingent_hours - breakdown.total_for_ceiling, 2
        )


class TestStructuralAndPause:
    def test_structural_39h_full_year(self):
        weeks = compute_weeks_worked(date(2020, 1, 1), 2025, date(2025, 12, 31))
        structural = compute_structural_hours(39.0, weeks, include=True)
        assert structural >= 207.0
        assert structural <= 209.0

    def test_pause_deduction_full_year(self):
        settings = _settings_client_excel()
        pause = compute_pause_deduction(
            settings, date(2020, 1, 1), 2025, date(2025, 12, 31)
        )
        assert 15.0 <= pause <= 15.5


class TestProratedManagementContingent:
    def test_full_year(self):
        settings = _settings_client_excel()
        assert compute_effective_management_contingent(
            settings, date(2019, 10, 1), 2025
        ) == 360.0

    def test_jean_may_2025(self):
        assert compute_prorated_management_contingent(360.0, date(2025, 5, 28), 2025) == 210.0

    def test_sow_april_2025(self):
        assert compute_prorated_management_contingent(360.0, date(2025, 4, 22), 2025) == 240.0


class TestManagementContingentProrata:
    def test_prorata_embauche_mai(self):
        from app.modules.repos_compensateur.domain.contingent_rules import (
            compute_effective_management_contingent,
        )

        settings = _settings_client_excel()
        assert compute_effective_management_contingent(
            settings, date(2025, 5, 28), 2025
        ) == 210.0

    def test_prorata_embauche_avril(self):
        from app.modules.repos_compensateur.domain.contingent_rules import (
            compute_effective_management_contingent,
        )

        settings = _settings_client_excel()
        assert compute_effective_management_contingent(
            settings, date(2025, 4, 22), 2025
        ) == 240.0

    def test_annee_complete(self):
        from app.modules.repos_compensateur.domain.contingent_rules import (
            compute_effective_management_contingent,
        )

        settings = _settings_client_excel()
        assert compute_effective_management_contingent(
            settings, date(2019, 10, 1), 2025
        ) == 360.0
