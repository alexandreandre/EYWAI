"""Scénario intégration LEWIS — barèmes CP anc., RTT forfait, variables paie."""

from datetime import date

from app.modules.absences.domain.cp_seniority import (
    CpSenioritySettings,
    EmployeeCpSeniorityContext,
    compute_cp_seniority_grant,
)
from app.modules.absences.domain.leave_policy import LeavePolicySettings
from app.modules.absences.domain.rtt_forfait import calculate_rtt_annual_forfait_jours
from app.modules.absences.domain.rules import compute_rtt_balance
from app.modules.payroll_variables.domain.rules import compute_rule_amount


def test_lewis_rtt_forfait_2026():
    assert calculate_rtt_annual_forfait_jours(
        2026, forfait_days=218, cp_ouvres_deduction=25.0
    ) == 9.0


def test_lewis_cp_seniority_cadre_forfait():
    ref = date(2026, 5, 31)
    settings = CpSenioritySettings(enabled=True, preset="lewis_agreement")
    ctx = EmployeeCpSeniorityContext(
        hire_date=date(2024, 1, 1),
        statut="Cadre au forfait jour",
    )
    grant = compute_cp_seniority_grant(settings, ctx, ref)
    assert grant.days_granted >= 1
    assert grant.forfait_days_reduction >= 1


def test_lewis_rtt_only_forfait_jours():
    policy = LeavePolicySettings(
        rtt_use_forfait_jours_formula=True,
        rtt_forfait_annual_days=218,
        rtt_forfait_cp_ouvres_deduction=25.0,
        rtt_forfait_cadres_only=True,
    )
    forfait = EmployeeCpSeniorityContext(
        hire_date=date(2015, 3, 1),
        statut="Cadre au forfait jour",
    )
    balance = compute_rtt_balance(
        date(2015, 3, 1),
        [],
        date(2026, 5, 1),
        policy=policy,
        employee_ctx=forfait,
    )
    assert balance["acquis"] == 9.0


def test_lewis_productivity_variable_mai():
    """Prime productivité fixe 36 € pour éligibles."""
    amount = compute_rule_amount("fixed_monthly", 36.0, None, 1.0)
    assert amount == 36.0
