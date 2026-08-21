"""Tests service validate IJSS (montant CPAM)."""

from __future__ import annotations

from unittest.mock import MagicMock

import app.modules.ijss_tracking.application.apply_to_payslip as mod
from app.modules.ijss_tracking.application.apply_to_payslip import (
    _resolve_brut_amount,
    apply_validated_ijss_to_payslip,
)


def test_resolve_brut_manual_preempts():
    exp = {"employee_id": "e1", "ijss_brut_validated": 100.0}
    amt, src = _resolve_brut_amount(exp, "p1", 448.0, "manual")
    assert amt == 448.0
    assert src == "manual"


def test_resolve_brut_from_cpam_matched():
    exp = {"employee_id": "e1"}
    received = [
        {
            "employee_id": "e1",
            "source": "cpam_decompte",
            "match_status": "matched",
            "amount": 320.5,
        }
    ]

    class FakeRepo:
        @staticmethod
        def list_received_lines(_period_id):
            return received

    original = mod.repo.list_received_lines
    mod.repo.list_received_lines = FakeRepo.list_received_lines
    try:
        amt, src = _resolve_brut_amount(exp, "p1", None, None)
    finally:
        mod.repo.list_received_lines = original
    assert amt == 320.5
    assert src == "cpam_decompte"


def test_apply_validated_regenerates_payslip(monkeypatch):
    expected = {
        "id": "exp-1",
        "period_id": "per-1",
        "employee_id": "emp-1",
        "ijss_brut_validated": 320.5,
        "validation_source": "cpam_decompte",
        "ijss_theorique": 350.0,
        "payslip_id": "ps-old",
    }
    period = {"id": "per-1", "period_year": 2026, "period_month": 5, "status": "open"}
    updated_fields: dict = {}

    monkeypatch.setattr(mod.repo, "get_expected_line", lambda _c, _e: expected)
    monkeypatch.setattr(mod.repo, "get_period", lambda _c, _p: period)
    monkeypatch.setattr(
        mod.repo,
        "update_expected_line",
        lambda eid, fields: updated_fields.update(fields) or {**expected, **fields},
    )

    emp_mock = MagicMock()
    emp_mock.data = {"statut": "CDI"}
    client_mock = MagicMock()
    client_mock.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = (
        emp_mock
    )
    monkeypatch.setattr(mod, "get_supabase_admin_client", lambda: client_mock)
    # Lot 3 : la garde « bulletin validé » lit le bulletin existant
    monkeypatch.setattr(mod, "_fetch_existing_payslip", lambda *a: None)

    gen_calls: list = []

    def fake_process(employee_id, year, month, **kwargs):
        gen_calls.append((employee_id, year, month, kwargs))
        return {"payslip_id": "ps-new"}

    monkeypatch.setattr(
        "app.modules.payroll.documents.payslip_generator.process_payslip_generation",
        fake_process,
    )
    monkeypatch.setattr(
        "app.modules.ijss_tracking.application.service._recompute_period",
        lambda p: p,
    )

    result = apply_validated_ijss_to_payslip("co-1", "exp-1", "user-1")

    assert result["applied_ijss_brut"] == 320.5
    assert result["payslip_id"] == "ps-new"
    assert gen_calls[0][2] == 5
    assert gen_calls[0][3]["ijss_brut_override"] == 320.5
    assert gen_calls[0][3]["ijss_tracking_meta"]["brut_validated"] == 320.5
    assert updated_fields["applied_ijss_brut"] == 320.5
    assert updated_fields["payslip_id"] == "ps-new"
