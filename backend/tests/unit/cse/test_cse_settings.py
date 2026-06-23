"""Tests unitaires API paramètres CSE entreprise."""

from unittest.mock import patch

import pytest

from app.modules.cse.application.cse_settings import (
    get_company_cse_settings,
    save_company_cse_settings,
)


class TestCseSettingsCommands:
    def test_save_invalid_status_raises(self):
        with patch(
            "app.modules.cse.infrastructure.cse_settings_repository.cse_settings_repository.get_by_company",
            return_value=None,
        ):
            with pytest.raises(ValueError, match="cse_status invalide"):
                save_company_cse_settings("co-1", {"cse_status": "invalid"})

    def test_get_defaults_when_missing(self):
        with patch(
            "app.modules.cse.infrastructure.cse_settings_repository.cse_settings_repository.get_by_company",
            return_value=None,
        ):
            settings = get_company_cse_settings("co-1")
        assert settings.company_id == "co-1"
        assert settings.cse_status == "unknown"

    def test_save_carence(self):
        with patch(
            "app.modules.cse.infrastructure.cse_settings_repository.cse_settings_repository.get_by_company",
            return_value=None,
        ), patch(
            "app.modules.cse.infrastructure.cse_settings_repository.cse_settings_repository.upsert",
            return_value={
                "company_id": "co-1",
                "cse_status": "carence",
                "carence_pv_document_id": None,
                "carence_valid_until": "2027-09-06",
                "notes": "PV 2019",
            },
        ):
            saved = save_company_cse_settings(
                "co-1",
                {
                    "cse_status": "carence",
                    "carence_valid_until": "2027-09-06",
                    "notes": "PV 2019",
                },
            )
        assert saved.cse_status == "carence"
        assert saved.carence_valid_until.isoformat() == "2027-09-06"
