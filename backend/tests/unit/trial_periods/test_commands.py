"""Construction des payloads de période d'essai."""

from datetime import date

import pytest

from app.modules.trial_periods.application.commands import (
    build_confirm_payload,
    build_create_payload,
    build_renewal_payload,
)
from app.modules.trial_periods.domain.constants import STATUS_CONFIRMEE


def test_creation_calcule_la_date_de_fin():
    payload = build_create_payload(
        company_id="c1",
        employee_id="e1",
        start_date=date(2026, 3, 1),
        duration_value=2,
        duration_unit="mois",
        renewal_allowed=True,
        created_by="u1",
    )
    assert payload["end_date"] == "2026-04-30"
    assert payload["status"] == "en_cours"
    assert payload["start_date"] == "2026-03-01"
    assert payload["renewal_allowed"] is True
    assert payload["created_by"] == "u1"


def test_creation_refuse_une_duree_inexploitable():
    with pytest.raises(ValueError, match="durée"):
        build_create_payload(
            company_id="c1",
            employee_id="e1",
            start_date=date(2026, 3, 1),
            duration_value=0,
            duration_unit="mois",
            renewal_allowed=False,
            created_by="u1",
        )


def test_renouvellement_repousse_la_fin():
    trial = {
        "start_date": "2026-03-01",
        "duration_value": 2,
        "duration_unit": "mois",
        "renewal_allowed": True,
        "renewed_at": None,
    }
    payload = build_renewal_payload(
        trial,
        renewed_at=date(2026, 4, 20),
        renewal_duration_value=2,
        renewal_duration_unit="mois",
        renewed_by="u1",
    )
    assert payload["end_date"] == "2026-06-30"
    assert payload["renewed_at"] == "2026-04-20"
    assert payload["renewal_duration_value"] == 2
    assert payload["renewed_by"] == "u1"


def test_renouvellement_refuse_si_la_convention_ne_l_ouvre_pas():
    trial = {
        "start_date": "2026-03-01",
        "duration_value": 2,
        "duration_unit": "mois",
        "renewal_allowed": False,
        "renewed_at": None,
    }
    with pytest.raises(ValueError, match="renouvellement"):
        build_renewal_payload(
            trial,
            renewed_at=date(2026, 4, 20),
            renewal_duration_value=2,
            renewal_duration_unit="mois",
            renewed_by="u1",
        )


def test_renouvellement_refuse_une_seconde_fois():
    trial = {
        "start_date": "2026-03-01",
        "duration_value": 2,
        "duration_unit": "mois",
        "renewal_allowed": True,
        "renewed_at": "2026-04-20",
    }
    with pytest.raises(ValueError, match="déjà"):
        build_renewal_payload(
            trial,
            renewed_at=date(2026, 4, 25),
            renewal_duration_value=1,
            renewal_duration_unit="mois",
            renewed_by="u1",
        )


def test_renouvellement_refuse_apres_le_terme():
    # Le renouvellement doit être notifié avant la fin de la période initiale.
    trial = {
        "start_date": "2026-03-01",
        "duration_value": 2,
        "duration_unit": "mois",
        "renewal_allowed": True,
        "renewed_at": None,
    }
    with pytest.raises(ValueError, match="terme"):
        build_renewal_payload(
            trial,
            renewed_at=date(2026, 5, 2),
            renewal_duration_value=2,
            renewal_duration_unit="mois",
            renewed_by="u1",
        )


def test_confirmation():
    payload = build_confirm_payload("u1")
    assert payload["status"] == STATUS_CONFIRMEE
    assert payload["confirmed_by"] == "u1"
    assert payload["confirmed_at"]
