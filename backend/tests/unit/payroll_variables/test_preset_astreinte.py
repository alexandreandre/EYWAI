"""Tests preset astreinte équipes."""

from unittest.mock import MagicMock, patch

from app.modules.payroll_variables.application.preset_astreinte_equipes import (
    PRESET_RULES,
    apply_astreinte_equipes_preset,
)


@patch("app.modules.payroll_variables.application.preset_astreinte_equipes.supabase")
@patch("app.modules.payroll_variables.application.preset_astreinte_equipes.repo")
def test_preset_creates_rules_when_empty(mock_repo, mock_supabase):
    mock_repo.list_rules.return_value = []
    mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
        data=[]
    )
    insert_mock = MagicMock()
    insert_mock.execute.return_value = MagicMock(
        data=[{"id": "bonus-1", "libelle": "Prime d'astreinte"}]
    )
    mock_supabase.table.return_value.insert.return_value = insert_mock

    result = apply_astreinte_equipes_preset("company-1")

    assert len(result["created_rules"]) == len(PRESET_RULES)
    assert mock_repo.upsert_rule.call_count == len(PRESET_RULES)
