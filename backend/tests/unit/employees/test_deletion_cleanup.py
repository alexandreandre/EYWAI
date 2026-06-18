"""Tests unitaires — suppression employé (impact + nettoyage)."""

from unittest.mock import MagicMock, patch

from app.modules.employees.application.deletion_cleanup import (
    DeletionImpact,
    cleanup_employee_orphan_rows,
    get_deletion_impact,
)


@patch("app.modules.employees.application.deletion_cleanup.supabase")
def test_get_deletion_impact_builds_summary(mock_supabase):
    emp_data = {
        "id": "emp-1",
        "first_name": "Jules",
        "last_name": "Henri",
        "user_id": "u1",
    }
    emp_chain = MagicMock()
    emp_chain.execute.return_value = MagicMock(data=emp_data)
    mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.maybe_single.return_value = (
        emp_chain
    )

    with patch(
        "app.modules.employees.application.deletion_cleanup._count_rows",
        side_effect=lambda table, _eid: 2 if table == "payslips" else 0,
    ):
        impact = get_deletion_impact("emp-1", "co-1")

    assert isinstance(impact, DeletionImpact)
    assert impact.employee_name == "Jules Henri"
    assert impact.counts.get("payslips") == 2
    assert any("bulletin" in line for line in impact.summary_lines)
    assert impact.has_user_account is True


@patch("app.modules.employees.application.deletion_cleanup.supabase")
def test_get_deletion_impact_empty_when_employee_missing(mock_supabase):
    emp_chain = MagicMock()
    emp_chain.execute.return_value = MagicMock(data=None)
    mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.maybe_single.return_value = (
        emp_chain
    )

    impact = get_deletion_impact("missing", "co-1")
    assert impact.employee_name == ""
    assert impact.summary_lines == []


@patch("app.modules.employees.application.deletion_cleanup._delete_by_employee_id")
@patch("app.modules.employees.application.deletion_cleanup.supabase")
def test_cleanup_orphan_rows_deletes_salary_advances(mock_supabase, mock_delete):
    mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = (
        MagicMock(data=[])
    )

    cleanup_employee_orphan_rows("emp-1")

    deleted_tables = [call.args[0] for call in mock_delete.call_args_list]
    assert "salary_advances" in deleted_tables
