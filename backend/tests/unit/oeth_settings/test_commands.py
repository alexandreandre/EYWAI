"""Tests commandes OETH."""

from __future__ import annotations

from datetime import date
from unittest.mock import patch

import pytest

from app.modules.oeth_settings.application.commands import save_oeth_settings, save_employee_boeth
from app.modules.oeth_settings.schemas.requests import EmployeeBoethUpdate, OethSettingsUpdate


@pytest.fixture
def mock_settings_repo():
    with patch(
        "app.modules.oeth_settings.application.commands.oeth_settings_repository"
    ) as repo:
        yield repo


@pytest.fixture
def mock_settings_queries():
    with patch(
        "app.modules.oeth_settings.application.commands.queries.get_oeth_settings"
    ) as get_settings:
        from app.modules.oeth_settings.schemas.responses import OethSettings

        get_settings.return_value = OethSettings(
            company_id="company-1",
            oeth_assujetti=False,
            taux_obligation=0.06,
        )
        yield get_settings


def test_save_oeth_settings(mock_settings_repo, mock_settings_queries):
    mock_settings_repo.upsert.return_value = {
        "id": "row-1",
        "company_id": "company-1",
        "taux_obligation": 0.06,
    }
    mock_settings_queries.return_value = mock_settings_queries.return_value
    with patch(
        "app.modules.oeth_settings.application.commands.queries.get_oeth_settings"
    ) as refreshed:
        from app.modules.oeth_settings.schemas.responses import OethSettings

        refreshed.return_value = OethSettings(
            company_id="company-1",
            date_franchissement_seuil_20=date(2022, 1, 1),
            taux_obligation=0.06,
        )
        result = save_oeth_settings(
            "company-1",
            OethSettingsUpdate(date_franchissement_seuil_20=date(2022, 1, 1)),
        )
    assert result.date_franchissement_seuil_20 == date(2022, 1, 1)


def test_save_employee_boeth_invalid_code():
    with pytest.raises(ValueError, match="Code BOETH invalide"):
        save_employee_boeth(
            "company-1",
            "emp-1",
            EmployeeBoethUpdate(boeth_code="99", valid_from=date(2025, 1, 1)),
        )


def test_save_employee_boeth_success():
    with patch(
        "app.modules.oeth_settings.application.commands.boeth_profiles_repository"
    ) as repo, patch(
        "app.modules.oeth_settings.application.commands.queries.get_employee_boeth"
    ) as get_prof:
        from app.modules.oeth_settings.schemas.responses import EmployeeBoethProfile

        repo.upsert_profile.return_value = {"id": "p1"}
        get_prof.return_value = EmployeeBoethProfile(
            employee_id="emp-1",
            company_id="company-1",
            boeth_code="01",
            valid_from=date(2025, 1, 1),
        )
        result = save_employee_boeth(
            "company-1",
            "emp-1",
            EmployeeBoethUpdate(boeth_code="01", valid_from=date(2025, 1, 1)),
        )
        assert result.boeth_code == "01"
