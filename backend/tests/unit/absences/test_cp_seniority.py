"""Tests CP ancienneté — barème plasturgie et intégration soldes."""

from __future__ import annotations

from datetime import date


from app.modules.absences.domain.cp_seniority import (
    CpSenioritySettings,
    EmployeeCpSeniorityContext,
    compute_cp_seniority_grant,
    resolve_employee_category,
)
from app.modules.absences.domain.leave_policy import LeavePolicySettings
from app.modules.absences.domain.rules import (
    compute_absence_balances,
    compute_cp_period_balances,
    get_available_conge_paye_days,
)


def _settings_enabled() -> CpSenioritySettings:
    return CpSenioritySettings(
        enabled=True,
        preset="plasturgie_idcc_0292",
    )


def _hire_years_ago(years: int, ref: date) -> date:
    return date(ref.year - years, ref.month, min(ref.day, 28))


class TestCpSeniorityEngine:
    def test_disabled_returns_zero(self):
        ref = date(2026, 5, 31)
        ctx = EmployeeCpSeniorityContext(
            hire_date=_hire_years_ago(6, ref),
            statut="Non-Cadre",
        )
        grant = compute_cp_seniority_grant(
            CpSenioritySettings.disabled(), ctx, ref
        )
        assert grant.days_granted == 0

    def test_ouvrier_four_years_zero(self):
        ref = date(2026, 5, 31)
        ctx = EmployeeCpSeniorityContext(
            hire_date=_hire_years_ago(4, ref),
            statut="Non-Cadre",
        )
        grant = compute_cp_seniority_grant(_settings_enabled(), ctx, ref)
        assert grant.days_granted == 0

    def test_ouvrier_five_years_one_day(self):
        ref = date(2026, 5, 31)
        ctx = EmployeeCpSeniorityContext(
            hire_date=_hire_years_ago(5, ref),
            statut="Non-Cadre",
        )
        grant = compute_cp_seniority_grant(_settings_enabled(), ctx, ref)
        assert grant.days_granted == 1
        assert grant.category == "ouvrier_etam"

    def test_ouvrier_twelve_years_two_days(self):
        ref = date(2026, 5, 31)
        ctx = EmployeeCpSeniorityContext(
            hire_date=_hire_years_ago(12, ref),
            statut="Non-Cadre",
        )
        grant = compute_cp_seniority_grant(_settings_enabled(), ctx, ref)
        assert grant.days_granted == 2

    def test_cadre_three_years_one_day(self):
        ref = date(2026, 5, 31)
        ctx = EmployeeCpSeniorityContext(
            hire_date=_hire_years_ago(3, ref),
            statut="Cadre",
        )
        grant = compute_cp_seniority_grant(_settings_enabled(), ctx, ref)
        assert grant.days_granted == 1
        assert grant.category == "cadre"

    def test_cadre_ten_years_three_days_total_not_cumulative(self):
        ref = date(2026, 5, 31)
        ctx = EmployeeCpSeniorityContext(
            hire_date=_hire_years_ago(10, ref),
            statut="Cadre",
        )
        grant = compute_cp_seniority_grant(_settings_enabled(), ctx, ref)
        assert grant.days_granted == 3

    def test_forfait_reduction(self):
        ref = date(2026, 5, 31)
        ctx = EmployeeCpSeniorityContext(
            hire_date=_hire_years_ago(10, ref),
            statut="Cadre au forfait jour",
        )
        grant = compute_cp_seniority_grant(_settings_enabled(), ctx, ref)
        assert grant.days_granted == 3
        assert grant.forfait_days_reduction == 3

    def test_prior_service_reaches_tier_earlier(self):
        ref = date(2026, 5, 31)
        ctx = EmployeeCpSeniorityContext(
            hire_date=_hire_years_ago(3, ref),
            statut="Non-Cadre",
            prior_service_months=24,
        )
        settings = CpSenioritySettings(
            enabled=True,
            preset="plasturgie_idcc_0292",
            seniority_basis="include_prior_service",
        )
        grant = compute_cp_seniority_grant(settings, ctx, ref)
        assert grant.days_granted == 1

    def test_resolve_category_cadre(self):
        assert (
            resolve_employee_category(
                EmployeeCpSeniorityContext(hire_date=date.today(), statut="Cadre")
            )
            == "cadre"
        )
        assert (
            resolve_employee_category(
                EmployeeCpSeniorityContext(
                    hire_date=date.today(), statut="Non-Cadre"
                )
            )
            == "ouvrier_etam"
        )


class TestLewisAgreementPreset:
    def _lewis_settings(self) -> CpSenioritySettings:
        return CpSenioritySettings(
            enabled=True,
            preset="lewis_agreement",
        )

    def test_two_years_one_day(self):
        ref = date(2026, 5, 31)
        ctx = EmployeeCpSeniorityContext(
            hire_date=_hire_years_ago(2, ref),
            statut="Non-Cadre",
        )
        grant = compute_cp_seniority_grant(self._lewis_settings(), ctx, ref)
        assert grant.days_granted == 1

    def test_age_45_adds_day(self):
        ref = date(2026, 5, 31)
        birth = date(1980, 1, 1)
        ctx = EmployeeCpSeniorityContext(
            hire_date=_hire_years_ago(2, ref),
            statut="Non-Cadre",
            birth_date=birth,
        )
        grant = compute_cp_seniority_grant(self._lewis_settings(), ctx, ref)
        assert grant.days_granted == 2

    def test_forfait_one_year(self):
        ref = date(2026, 5, 31)
        ctx = EmployeeCpSeniorityContext(
            hire_date=_hire_years_ago(1, ref),
            statut="Cadre au forfait jour",
        )
        grant = compute_cp_seniority_grant(self._lewis_settings(), ctx, ref)
        assert grant.days_granted == 1
        assert grant.category == "forfait"

    def test_seniority_reference_date_basis(self):
        ref = date(2026, 5, 31)
        ctx = EmployeeCpSeniorityContext(
            hire_date=date(2024, 1, 1),
            statut="Non-Cadre",
            seniority_reference_date=date(2022, 1, 1),
        )
        settings = CpSenioritySettings(
            enabled=True,
            preset="lewis_agreement",
            seniority_basis="seniority_reference_date",
        )
        grant = compute_cp_seniority_grant(settings, ctx, ref)
        assert grant.days_granted == 1


class TestCpSeniorityBalanceIntegration:
    def test_compute_cp_period_includes_supplemental(self):
        ref = date(2026, 6, 15)
        hire = date(2016, 1, 1)
        ctx = EmployeeCpSeniorityContext(hire_date=hire, statut="Cadre")
        settings = _settings_enabled()
        periods = compute_cp_period_balances(
            hire,
            [],
            ref,
            policy=LeavePolicySettings(),
            cp_seniority=settings,
            employee_ctx=ctx,
        )
        assert periods["cp_seniority_n"] == 3
        assert periods["periode_courante"]["acquis"] >= 3

    def test_available_cp_includes_seniority(self):
        ref = date(2026, 6, 15)
        hire = date(2016, 1, 1)
        ctx = EmployeeCpSeniorityContext(hire_date=hire, statut="Cadre")
        settings = _settings_enabled()
        available = get_available_conge_paye_days(
            hire,
            [],
            ref,
            cp_seniority=settings,
            employee_ctx=ctx,
        )
        legal_only = get_available_conge_paye_days(hire, [], ref)
        assert available > legal_only
        assert available - legal_only >= 2.9

    def test_compute_absence_balances_breakdown(self):
        ref = date(2026, 6, 15)
        hire = date(2016, 1, 1)
        ctx = EmployeeCpSeniorityContext(hire_date=hire, statut="Cadre")
        settings = _settings_enabled()
        soldes = compute_absence_balances(
            hire,
            [],
            ref,
            cp_seniority=settings,
            employee_ctx=ctx,
        )
        assert soldes["cp_seniority_days"] == 3
        assert soldes["conges_payes"]["acquis"] >= 3
