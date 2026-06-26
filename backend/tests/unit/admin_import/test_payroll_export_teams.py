"""Tests paramétrage équipes MOD/MOI — import export paie."""

from unittest.mock import patch

from app.modules.admin_import.application.payroll_export_teams import (
    company_has_mod_moi_teams,
    resolve_mod_moi_team_mapping,
)


def test_company_has_mod_moi_teams_when_mod_present():
    with patch(
        "app.modules.admin_import.application.payroll_export_teams.teams_repository.get_teams_by_company",
        return_value=[{"name": "MOD"}, {"name": "Production"}],
    ):
        assert company_has_mod_moi_teams("co-1") is True


def test_company_has_mod_moi_teams_false_without_matching_names():
    with patch(
        "app.modules.admin_import.application.payroll_export_teams.teams_repository.get_teams_by_company",
        return_value=[{"name": "Administration"}],
    ):
        assert company_has_mod_moi_teams("co-1") is False


def test_resolve_uses_explicit_override():
    with patch(
        "app.modules.admin_import.application.payroll_export_teams.company_repository.get_settings",
    ) as mock_settings:
        assert resolve_mod_moi_team_mapping("co-1", explicit=True) is True
        assert resolve_mod_moi_team_mapping("co-1", explicit=False) is False
        mock_settings.assert_not_called()


def test_resolve_uses_company_settings():
    with patch(
        "app.modules.admin_import.application.payroll_export_teams.company_repository.get_settings",
        return_value={"payroll_export_mod_moi_teams": True},
    ), patch(
        "app.modules.admin_import.application.payroll_export_teams.company_has_mod_moi_teams",
        return_value=False,
    ) as mock_has:
        assert resolve_mod_moi_team_mapping("co-1") is True
        mock_has.assert_not_called()


def test_resolve_falls_back_to_existing_teams():
    with patch(
        "app.modules.admin_import.application.payroll_export_teams.company_repository.get_settings",
        return_value={},
    ), patch(
        "app.modules.admin_import.application.payroll_export_teams.company_has_mod_moi_teams",
        return_value=True,
    ):
        assert resolve_mod_moi_team_mapping("co-1") is True
