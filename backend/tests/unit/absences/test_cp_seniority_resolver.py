"""Tests CP ancienneté resolver et métallurgie."""

from datetime import date


from app.modules.absences.domain.cp_seniority import (
    CpSenioritySettings,
    EmployeeCpSeniorityContext,
    compute_cp_seniority_grant,
)
from app.modules.absences.domain.cp_seniority_resolver import (
    recommended_preset_for_idcc,
    resolve_barème_from_cc,
    resolve_effective_cp_seniority_rules,
)
from app.modules.absences.domain.leave_policy import LeavePolicySettings


class TestCpSeniorityResolver:
    def test_recommended_preset_3248(self):
        assert recommended_preset_for_idcc("3248") == "metallurgie_idcc_3248"

    def test_resolve_barème_from_cc_3248(self):
        rules, source = resolve_barème_from_cc("3248")
        assert rules is not None
        assert source == "seed_officiel"
        assert len(rules.tiers) == 4

    def test_metallurgie_preset_rules(self):
        settings = CpSenioritySettings(
            enabled=True,
            preset="metallurgie_idcc_3248",
            seniority_basis="seniority_reference_date",
        )
        rules = resolve_effective_cp_seniority_rules(settings)
        assert rules.mode == "cumulative_rules"


class TestMetallurgieGrant:
    def test_cadre_two_years_one_day(self):
        ref = date(2026, 5, 31)
        settings = CpSenioritySettings(
            enabled=True,
            preset="metallurgie_idcc_3248",
            seniority_basis="company_only",
        )
        ctx = EmployeeCpSeniorityContext(
            hire_date=date(2024, 1, 1),
            statut="Non-Cadre",
        )
        grant = compute_cp_seniority_grant(settings, ctx, ref)
        assert grant.days_granted == 1

    def test_age_45_extra_day(self):
        ref = date(2026, 5, 31)
        settings = CpSenioritySettings(enabled=True, preset="metallurgie_idcc_3248")
        ctx = EmployeeCpSeniorityContext(
            hire_date=date(2024, 1, 1),
            birth_date=date(1975, 6, 1),
            statut="Non-Cadre",
        )
        grant = compute_cp_seniority_grant(settings, ctx, ref)
        assert grant.days_granted == 2

    def test_prorata_mid_year_hire(self):
        ref = date(2026, 5, 31)
        settings = CpSenioritySettings(enabled=True, preset="metallurgie_idcc_3248")
        ctx = EmployeeCpSeniorityContext(
            hire_date=date(2026, 1, 15),
            statut="Non-Cadre",
        )
        grant = compute_cp_seniority_grant(
            settings, ctx, ref, policy=LeavePolicySettings()
        )
        assert grant.prorata_applied is True
        assert "prorata_applied" in grant.warnings

    def test_birth_date_missing_warning(self):
        ref = date(2026, 5, 31)
        settings = CpSenioritySettings(enabled=True, preset="metallurgie_idcc_3248")
        ctx = EmployeeCpSeniorityContext(
            hire_date=date(2024, 1, 1),
            statut="Non-Cadre",
        )
        grant = compute_cp_seniority_grant(settings, ctx, ref)
        assert "birth_date_missing" in grant.warnings

    def test_forfait_one_year(self):
        ref = date(2026, 5, 31)
        settings = CpSenioritySettings(enabled=True, preset="metallurgie_idcc_3248")
        ctx = EmployeeCpSeniorityContext(
            hire_date=date(2025, 3, 1),
            statut="Cadre au forfait jour",
        )
        grant = compute_cp_seniority_grant(settings, ctx, ref)
        assert grant.days_granted >= 1

    def test_cadre_dirigeant_one_year_without_forfait(self):
        """Art. 89 : +1 j. à 1 an pour cadre dirigeant (hors forfait)."""
        ref = date(2026, 5, 31)
        settings = CpSenioritySettings(enabled=True, preset="metallurgie_idcc_3248")
        ctx = EmployeeCpSeniorityContext(
            hire_date=date(2025, 3, 1),
            statut="Cadre",
            is_cadre_dirigeant=True,
        )
        grant = compute_cp_seniority_grant(settings, ctx, ref)
        assert grant.days_granted == 1
        assert grant.category == "cadre"

    def test_cadre_non_dirigeant_one_year_zero(self):
        ref = date(2026, 5, 31)
        settings = CpSenioritySettings(enabled=True, preset="metallurgie_idcc_3248")
        ctx = EmployeeCpSeniorityContext(
            hire_date=date(2025, 3, 1),
            statut="Cadre",
            is_cadre_dirigeant=False,
        )
        grant = compute_cp_seniority_grant(settings, ctx, ref)
        assert grant.days_granted == 0
