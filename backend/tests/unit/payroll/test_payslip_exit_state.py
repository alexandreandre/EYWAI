"""Tests résolution indemnités de sortie pour bulletin."""

from __future__ import annotations

from unittest.mock import MagicMock

from app.modules.payroll.documents.payslip_run_common import (
    resolve_exit_indemnities_for_payslip,
    resolve_exit_state_for_payslip,
)


def _mock_supabase(rows):
    sb = MagicMock()
    sb.table.return_value.select.return_value.eq.return_value.not_.in_.return_value.order.return_value.limit.return_value.execute.return_value = MagicMock(
        data=rows
    )
    return sb


def test_resolve_exit_state_avec_indemnites():
    rows = [
        {
            "last_working_day": "2025-09-30",
            "calculated_indemnities": {"indemnite_conges": {"montant": 500.0}},
        }
    ]
    indemnities, block = resolve_exit_state_for_payslip(
        "emp-1", 2025, 9, _mock_supabase(rows)
    )
    assert indemnities is not None
    assert block is False
    assert resolve_exit_indemnities_for_payslip("emp-1", 2025, 9, _mock_supabase(rows)) == indemnities


def test_resolve_exit_state_bloque_sans_indemnites():
    rows = [{"last_working_day": "2025-09-30", "calculated_indemnities": None}]
    indemnities, block = resolve_exit_state_for_payslip(
        "emp-1", 2025, 9, _mock_supabase(rows)
    )
    assert indemnities is None
    assert block is True


def test_resolve_exit_state_ignore_autre_mois():
    rows = [{"last_working_day": "2025-08-31", "calculated_indemnities": None}]
    indemnities, block = resolve_exit_state_for_payslip(
        "emp-1", 2025, 9, _mock_supabase(rows)
    )
    assert indemnities is None
    assert block is False
