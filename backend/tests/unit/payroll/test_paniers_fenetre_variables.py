"""Les paniers d'équipe sont comptés sur la fenêtre, pas sur le mois civil."""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock

import pytest

pytestmark = pytest.mark.unit


@pytest.fixture()
def supabase_mock(monkeypatch):
    from app.modules.planning.application import shift_payroll_aggregation as agg

    client = MagicMock()
    client.table.return_value.select.return_value.eq.return_value.eq.return_value.is_.return_value.gte.return_value.lte.return_value.execute.return_value = MagicMock(
        data=[]
    )
    monkeypatch.setattr(agg, "supabase", client)
    return client


def _bornes_appelees(client) -> tuple[str, str]:
    """(gte, lte) transmis à PostgREST pour shift_date."""
    requete = client.table.return_value.select.return_value
    requete = requete.eq.return_value.eq.return_value.is_.return_value
    return requete.gte.call_args[0][1], requete.gte.return_value.lte.call_args[0][1]


def test_sans_bornes_explicites_on_reste_sur_le_mois(supabase_mock):
    from app.modules.planning.application.shift_payroll_aggregation import (
        aggregate_shift_payroll_metrics,
    )

    aggregate_shift_payroll_metrics("e1", 2026, 7)
    assert _bornes_appelees(supabase_mock) == ("2026-07-01", "2026-07-31")


def test_les_bornes_explicites_priment(supabase_mock):
    from app.modules.planning.application.shift_payroll_aggregation import (
        aggregate_shift_payroll_metrics,
    )

    aggregate_shift_payroll_metrics(
        "e1", 2026, 7, start=date(2026, 6, 22), end=date(2026, 7, 19)
    )
    assert _bornes_appelees(supabase_mock) == ("2026-06-22", "2026-07-19")
