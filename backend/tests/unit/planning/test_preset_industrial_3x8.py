"""Tests preset planning 3×8 industriel."""

from unittest.mock import patch

from app.modules.planning.application.preset_shift_teams import (
    INDUSTRIAL_3X8_SHIFT_TYPES,
    apply_industrial_3x8_preset,
)


@patch("app.modules.planning.application.preset_shift_teams.shift_type_commands")
@patch(
    "app.modules.planning.application.preset_shift_teams.get_shift_types_for_company"
)
def test_industrial_3x8_creates_missing_shift_types(mock_get_types, mock_commands):
    mock_get_types.return_value = []
    result = apply_industrial_3x8_preset("company-1")

    assert result["created_shift_types"] == ["MATIN", "APREM", "NUIT"]
    assert mock_commands.create_shift_type.call_count == len(INDUSTRIAL_3X8_SHIFT_TYPES)


@patch("app.modules.planning.application.preset_shift_teams.shift_type_commands")
@patch(
    "app.modules.planning.application.preset_shift_teams.get_shift_types_for_company"
)
def test_industrial_3x8_skips_existing(mock_get_types, mock_commands):
    mock_get_types.return_value = [{"code": "MATIN"}, {"code": "NUIT"}]
    result = apply_industrial_3x8_preset("company-1")

    assert result["created_shift_types"] == ["APREM"]
    assert result["skipped_existing"] == ["MATIN", "NUIT"]
    mock_commands.create_shift_type.assert_called_once()
