"""Tests règles métier médailles du travail."""

from __future__ import annotations

from datetime import date

import pytest

from app.modules.work_medals.domain.entities import MedalTier
from app.modules.work_medals.domain.rules import (
    compute_employee_seniority_months,
    compute_social_tax_flag,
    compute_tier_amount,
    detect_case_status,
    can_transition,
    milestone_reached_date,
)


def test_seniority_total_career_with_prior_service():
    hire = date(2010, 1, 1)
    # 10 ans (120 mois) avant embauche + 10 ans dans l'entreprise = 20 ans
    months = compute_employee_seniority_months(
        hire,
        prior_service_months=120,
        seniority_basis="total_career",
        reference_date=date(2020, 1, 1),
    )
    assert months == 240


def test_seniority_company_only_ignores_prior():
    hire = date(2010, 1, 1)
    months = compute_employee_seniority_months(
        hire,
        prior_service_months=120,
        seniority_basis="company_only",
        reference_date=date(2020, 1, 1),
    )
    assert months == 120


def test_detect_case_status_upcoming_vs_eligible():
    assert detect_case_status(234, 20, 6) == "upcoming"
    assert detect_case_status(240, 20, 6) == "awaiting_rh"
    assert detect_case_status(100, 20, 6) is None


def test_milestone_reached_date():
    hire = date(2006, 6, 15)
    reached = milestone_reached_date(hire, 0, "company_only", 20)
    assert reached == date(2026, 6, 15)


def test_compute_tier_amount_fixed():
    tier = MedalTier("argent", 20, "Argent", "fixed", 400)
    assert compute_tier_amount(tier, 3000) == 400


def test_compute_tier_amount_salary_months():
    tier = MedalTier("vermeil", 30, "Vermeil", "salary_months", 0.5)
    assert compute_tier_amount(tier, 3000) == 1500


@pytest.mark.parametrize(
    "amount,base,year,expected",
    [
        (400, 3000, 2026, False),
        (4000, 3000, 2026, True),
        (400, 3000, 2027, True),
    ],
)
def test_compute_social_tax_flag(amount, base, year, expected):
    assert (
        compute_social_tax_flag(amount, base, year, default_is_socially_taxed=False)
        is expected
    )


def test_can_transition_workflow():
    assert can_transition("awaiting_rh", "approved", "rh")
    assert can_transition("awaiting_employee", "approved", "rh")
    assert not can_transition("upcoming", "approved", "rh")
