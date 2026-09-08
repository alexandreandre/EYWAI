"""Dépôt des fenêtres de variables — appels PostgREST, client mocké."""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock

import pytest

pytestmark = pytest.mark.unit


@pytest.fixture()
def supabase_mock(monkeypatch):
    from app.modules.payroll.infrastructure import variable_periods_repository as repo

    client = MagicMock()
    monkeypatch.setattr(repo, "supabase", client)
    return client


def test_get_variable_period_renvoie_none_sans_ligne(supabase_mock):
    from app.modules.payroll.infrastructure import variable_periods_repository as repo

    chaine = supabase_mock.table.return_value.select.return_value.match.return_value
    chaine.maybe_single.return_value.execute.return_value = MagicMock(data=None)

    assert repo.get_variable_period("c1", 2026, 7) is None
    supabase_mock.table.assert_called_with("company_variable_periods")


def test_get_variable_period_renvoie_la_ligne(supabase_mock):
    from app.modules.payroll.infrastructure import variable_periods_repository as repo

    ligne = {"start_date": "2026-06-22", "end_date": "2026-07-19", "origin": "manuel"}
    chaine = supabase_mock.table.return_value.select.return_value.match.return_value
    chaine.maybe_single.return_value.execute.return_value = MagicMock(data=ligne)

    assert repo.get_variable_period("c1", 2026, 7) == ligne


def test_upsert_envoie_les_dates_en_iso(supabase_mock):
    from app.modules.payroll.infrastructure import variable_periods_repository as repo

    upsert = supabase_mock.table.return_value.upsert
    upsert.return_value.execute.return_value = MagicMock(data=[{"id": "p1"}])

    repo.upsert_variable_period(
        company_id="c1",
        annee=2026,
        mois=7,
        debut=date(2026, 6, 22),
        fin=date(2026, 7, 19),
        origine="manuel",
        user_id="u1",
    )

    payload = upsert.call_args[0][0]
    assert payload["start_date"] == "2026-06-22"
    assert payload["end_date"] == "2026-07-19"
    assert payload["company_id"] == "c1"
    assert payload["year"] == 2026
    assert payload["month"] == 7
    assert payload["origin"] == "manuel"
    assert payload["created_by"] == "u1"
    assert upsert.call_args[1]["on_conflict"] == "company_id,year,month"
