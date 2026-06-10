"""Tests apply_salary_update — report date future."""

from datetime import date, timedelta
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.modules.employees.application import commands

pytestmark = pytest.mark.unit


@patch("app.modules.employees.application.commands._maybe_activate_after_onboarding")
@patch("app.modules.employees.application.commands._employee_repository")
def test_apply_salary_future_ne_sync_pas(mock_repo, _mock_onboarding):
    future = (date.today() + timedelta(days=30)).isoformat()
    mock_repo.insert_salary_history.return_value = {"id": "h1", "effective_date": future}

    row = commands.apply_salary_update(
        employee_id="e1",
        company_id="c1",
        ancien_salaire={"valeur": 2000},
        nouveau_salaire={"valeur": 2200},
        motif="Test",
        effective_date=future,
        created_by="u1",
    )

    assert row["id"] == "h1"
    mock_repo.sync_salaire_actif.assert_not_called()


@patch("app.modules.employees.application.commands._maybe_activate_after_onboarding")
@patch("app.modules.employees.application.commands._employee_repository")
def test_apply_salary_today_sync(mock_repo, _mock_onboarding):
    today = date.today().isoformat()
    mock_repo.insert_salary_history.return_value = {"id": "h2"}
    mock_repo.sync_salaire_actif.return_value = {"id": "e1"}

    commands.apply_salary_update(
        employee_id="e1",
        company_id="c1",
        ancien_salaire={"valeur": 2000},
        nouveau_salaire={"valeur": 2200},
        motif=None,
        effective_date=today,
        created_by="u1",
    )

    mock_repo.sync_salaire_actif.assert_called_once()


@patch("app.modules.employees.application.commands._maybe_activate_after_onboarding")
@patch("app.modules.employees.application.commands._employee_repository")
def test_apply_salary_sync_employe_introuvable(mock_repo, _mock_onboarding):
    mock_repo.insert_salary_history.return_value = {"id": "h3"}
    mock_repo.sync_salaire_actif.return_value = None

    with pytest.raises(HTTPException) as exc:
        commands.apply_salary_update(
            employee_id="e1",
            company_id="c1",
            ancien_salaire={"valeur": 2000},
            nouveau_salaire={"valeur": 2200},
            motif=None,
            effective_date=date.today().isoformat(),
            created_by="u1",
        )
    assert exc.value.status_code == 404
