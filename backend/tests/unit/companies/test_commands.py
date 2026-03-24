"""
Tests unitaires des commandes du module companies (application/commands.py).

Repository mocké : pas d'accès DB.
"""
from unittest.mock import MagicMock, patch

import pytest

from app.modules.companies.application import commands
from app.modules.companies.application.dto import CompanySettingsResultDto


MODULE_COMMANDS = "app.modules.companies.application.commands"


class TestUpdateCompanySettings:
    """Commande update_company_settings."""

    def test_update_company_settings_merge_medical_follow_up(self):
        """Merge settings existants avec medical_follow_up_enabled du delta."""
        mock_repo = MagicMock()
        mock_repo.get_settings.return_value = {"medical_follow_up_enabled": False}
        mock_repo.update_settings.return_value = None

        with patch(f"{MODULE_COMMANDS}.company_repository", mock_repo):
            result = commands.update_company_settings(
                company_id="company-1",
                settings_delta={"medical_follow_up_enabled": True},
                current_user=MagicMock(),
            )

        assert isinstance(result, CompanySettingsResultDto)
        assert result.medical_follow_up_enabled is True
        assert result.settings == {"medical_follow_up_enabled": True}
        mock_repo.get_settings.assert_called_once_with("company-1")
        mock_repo.update_settings.assert_called_once_with(
            "company-1", {"medical_follow_up_enabled": True}
        )

    def test_update_company_settings_preserves_existing_keys(self):
        """Les clés existantes non présentes dans le delta sont conservées."""
        mock_repo = MagicMock()
        mock_repo.get_settings.return_value = {
            "medical_follow_up_enabled": False,
            "other_setting": "keep",
        }
        mock_repo.update_settings.return_value = None

        with patch(f"{MODULE_COMMANDS}.company_repository", mock_repo):
            result = commands.update_company_settings(
                company_id="company-2",
                settings_delta={"medical_follow_up_enabled": True},
                current_user=MagicMock(),
            )

        assert result.settings["medical_follow_up_enabled"] is True
        assert result.settings["other_setting"] == "keep"
        mock_repo.update_settings.assert_called_once()
        call_settings = mock_repo.update_settings.call_args[0][1]
        assert call_settings["other_setting"] == "keep"

    def test_update_company_settings_raises_when_company_not_found(self):
        """LookupError si get_settings retourne None (entreprise inexistante)."""
        mock_repo = MagicMock()
        mock_repo.get_settings.return_value = None

        with patch(f"{MODULE_COMMANDS}.company_repository", mock_repo):
            with pytest.raises(LookupError, match="Entreprise non trouvée"):
                commands.update_company_settings(
                    company_id="unknown",
                    settings_delta={"medical_follow_up_enabled": True},
                    current_user=MagicMock(),
                )
        mock_repo.update_settings.assert_not_called()

    def test_update_company_settings_empty_delta_keeps_current(self):
        """Delta vide : pas de clé medical_follow_up, settings inchangés."""
        mock_repo = MagicMock()
        mock_repo.get_settings.return_value = {"medical_follow_up_enabled": True}
        mock_repo.update_settings.return_value = None

        with patch(f"{MODULE_COMMANDS}.company_repository", mock_repo):
            result = commands.update_company_settings(
                company_id="company-3",
                settings_delta={},
                current_user=MagicMock(),
            )

        assert result.medical_follow_up_enabled is True
        assert result.settings == {"medical_follow_up_enabled": True}
        mock_repo.update_settings.assert_called_once_with(
            "company-3", {"medical_follow_up_enabled": True}
        )

    def test_update_company_settings_coerces_medical_to_bool(self):
        """medical_follow_up_enabled dans le delta est converti en bool."""
        mock_repo = MagicMock()
        mock_repo.get_settings.return_value = {}
        mock_repo.update_settings.return_value = None

        with patch(f"{MODULE_COMMANDS}.company_repository", mock_repo):
            result = commands.update_company_settings(
                company_id="company-4",
                settings_delta={"medical_follow_up_enabled": 1},
                current_user=MagicMock(),
            )
        assert result.medical_follow_up_enabled is True

        mock_repo.get_settings.return_value = {}
        with patch(f"{MODULE_COMMANDS}.company_repository", mock_repo):
            result2 = commands.update_company_settings(
                company_id="company-4",
                settings_delta={"medical_follow_up_enabled": 0},
                current_user=MagicMock(),
            )
        assert result2.medical_follow_up_enabled is False
