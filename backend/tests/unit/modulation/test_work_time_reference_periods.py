"""Intégration — référence horaire réduite sans accord de modulation."""

from datetime import date

from app.modules.modulation.domain.reference_period_rules import (
    WorkTimePeriod,
    resolve_effective_weekly_hours_for_week,
)


def test_reduced_reference_without_modulation_agreement():
    """Entreprise sans annualisation : période 28 h/semaine prime sur contrat 35 h."""
    monday = date(2026, 4, 6)
    periods = [
        WorkTimePeriod(
            id="p1",
            company_id="c1",
            label="Référence réduite",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 8, 31),
            daily_reference_hours=None,
            weekly_reference_hours=28.0,
            affects_payroll=True,
            affects_planning=False,
            default_week_template_id=None,
            is_active=True,
        )
    ]
    effective = resolve_effective_weekly_hours_for_week(
        35.0, monday, modulation_map=None, reference_periods=periods
    )
    assert effective == 28.0
