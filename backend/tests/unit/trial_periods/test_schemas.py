"""Validation des entrées d'API."""

from datetime import date

import pytest
from pydantic import ValidationError

from app.modules.trial_periods.schemas.requests import (
    TrialPeriodCreate,
    TrialPeriodRenew,
    TrialPeriodUpdate,
)


def test_creation_valide():
    body = TrialPeriodCreate(
        employee_id="e1",
        start_date=date(2026, 3, 1),
        duration_value=2,
        duration_unit="mois",
        renewal_allowed=True,
    )
    assert body.duration_unit == "mois"


def test_creation_refuse_une_unite_inconnue():
    with pytest.raises(ValidationError):
        TrialPeriodCreate(
            employee_id="e1",
            start_date=date(2026, 3, 1),
            duration_value=2,
            duration_unit="trimestres",
            renewal_allowed=False,
        )


def test_creation_refuse_une_duree_nulle():
    with pytest.raises(ValidationError):
        TrialPeriodCreate(
            employee_id="e1",
            start_date=date(2026, 3, 1),
            duration_value=0,
            duration_unit="mois",
            renewal_allowed=False,
        )


def test_mise_a_jour_partielle():
    body = TrialPeriodUpdate(duration_value=3)
    assert body.duration_unit is None
    assert body.duration_value == 3


def test_renouvellement_exige_ses_trois_champs():
    body = TrialPeriodRenew(
        renewed_at=date(2026, 4, 20), duration_value=2, duration_unit="mois"
    )
    assert body.duration_value == 2
    with pytest.raises(ValidationError):
        TrialPeriodRenew(renewed_at=date(2026, 4, 20), duration_value=2)
