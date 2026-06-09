"""Tests commandes paramétrage JEI."""

from __future__ import annotations

from datetime import date
from unittest.mock import patch

import pytest

from app.modules.jei_settings.application.commands import save_jei_settings
from app.modules.jei_settings.schemas.requests import JeiSettingsUpdate


@pytest.fixture
def mock_repo():
    with patch(
        "app.modules.jei_settings.application.commands.jei_settings_repository"
    ) as repo:
        yield repo


@pytest.fixture
def mock_queries():
    with patch(
        "app.modules.jei_settings.application.commands.queries.get_jei_settings"
    ) as get_settings:
        from app.modules.jei_settings.schemas.responses import JeiSettings

        get_settings.return_value = JeiSettings(
            company_id="company-1",
            jei_enabled=False,
            date_creation_etablissement=None,
            taux_exoneration=1.0,
        )
        yield get_settings


def test_save_jei_requires_date_when_enabled(mock_repo, mock_queries):
    with pytest.raises(ValueError, match="date de création"):
        save_jei_settings(
            "company-1",
            JeiSettingsUpdate(jei_enabled=True),
        )


def test_save_jei_success(mock_repo, mock_queries):
    mock_repo.upsert.return_value = {
        "id": "row-1",
        "company_id": "company-1",
        "jei_enabled": True,
        "date_creation_etablissement": "2024-06-01",
        "taux_exoneration": 1.0,
    }
    result = save_jei_settings(
        "company-1",
        JeiSettingsUpdate(
            jei_enabled=True,
            date_creation_etablissement=date(2024, 6, 1),
        ),
    )
    assert result.jei_enabled is True
    assert result.date_creation_etablissement == date(2024, 6, 1)
    mock_repo.upsert.assert_called_once()
