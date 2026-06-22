"""Tests unitaires — saisie manuelle solde RTT absolu."""

from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from app.modules.absences.application.leave_settings_commands import apply_rtt_solde_manual


class TestApplyRttSoldeManual:
    @patch(
        "app.modules.absences.application.leave_settings_commands.upsert_employee_adjustment"
    )
    @patch(
        "app.modules.absences.application.leave_settings_commands.compute_rtt_balance"
    )
    @patch(
        "app.modules.absences.application.leave_settings_commands._rtt_eligible_for_employee",
        return_value=True,
    )
    @patch(
        "app.modules.absences.application.leave_settings_commands.build_employee_cp_seniority_context"
    )
    @patch(
        "app.modules.absences.application.leave_settings_commands.get_leave_policy"
    )
    @patch(
        "app.modules.absences.application.leave_settings_commands.absence_repository"
    )
    @patch(
        "app.modules.absences.application.leave_settings_commands.get_employee_hire_date",
        return_value="2020-01-01",
    )
    @patch(
        "app.modules.absences.application.leave_settings_commands._ensure_employee_in_company"
    )
    @patch("app.modules.absences.application.leave_settings_commands.supabase")
    def test_converts_absolute_solde_to_opening_balance(
        self,
        mock_supabase,
        _mock_ensure,
        _mock_hire,
        mock_absence_repo,
        _mock_policy,
        mock_build_ctx,
        _mock_eligible,
        mock_compute_rtt,
        mock_upsert,
    ):
        mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
            data=[{"id": "emp-1", "statut": "Cadre"}]
        )
        mock_build_ctx.return_value = MagicMock(is_forfait=True)
        mock_absence_repo.list_validated_for_employees.return_value = []
        mock_compute_rtt.return_value = {"acquis": 3.0, "pris": 0.0, "solde": 3.0}
        mock_upsert.return_value = {
            "cp_n1_opening_balance": 5.0,
            "cp_n_opening_balance": 2.0,
            "rtt_opening_balance": 2.0,
            "rtt_forfeited_days": 0,
            "note": None,
        }

        result = apply_rtt_solde_manual(
            "co-1",
            "emp-1",
            2026,
            rtt_solde=5.0,
        )

        mock_upsert.assert_called_once()
        payload = mock_upsert.call_args.args[3]
        assert payload == {"rtt_opening_balance": 2.0}
        assert result.rtt_opening_balance == 2.0
        assert result.cp_n1_opening_balance == 5.0
        assert result.cp_n_opening_balance == 2.0

    @patch(
        "app.modules.absences.application.leave_settings_commands._ensure_employee_in_company"
    )
    @patch(
        "app.modules.absences.application.leave_settings_commands.get_employee_hire_date",
        return_value=None,
    )
    def test_missing_hire_date_raises(self, _mock_hire, _mock_ensure):
        with pytest.raises(ValueError, match="Date d'embauche manquante"):
            apply_rtt_solde_manual("co-1", "emp-1", 2026, rtt_solde=1.0)

    @patch(
        "app.modules.absences.application.leave_settings_commands._rtt_eligible_for_employee",
        return_value=False,
    )
    @patch(
        "app.modules.absences.application.leave_settings_commands.build_employee_cp_seniority_context"
    )
    @patch(
        "app.modules.absences.application.leave_settings_commands.get_leave_policy"
    )
    @patch(
        "app.modules.absences.application.leave_settings_commands.get_employee_hire_date",
        return_value="2020-01-01",
    )
    @patch(
        "app.modules.absences.application.leave_settings_commands._ensure_employee_in_company"
    )
    @patch("app.modules.absences.application.leave_settings_commands.supabase")
    def test_ineligible_employee_raises(
        self,
        mock_supabase,
        _mock_ensure,
        _mock_hire,
        _mock_policy,
        mock_build_ctx,
        _mock_eligible,
    ):
        mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
            data=[{"id": "emp-1", "statut": "Non-cadre"}]
        )
        mock_build_ctx.return_value = MagicMock(is_forfait=False)

        with pytest.raises(ValueError, match="non éligible"):
            apply_rtt_solde_manual("co-1", "emp-1", 2026, rtt_solde=1.0)

    @patch(
        "app.modules.absences.application.leave_settings_commands.upsert_employee_adjustment"
    )
    @patch(
        "app.modules.absences.application.leave_settings_commands.compute_rtt_balance"
    )
    @patch(
        "app.modules.absences.application.leave_settings_commands._rtt_eligible_for_employee",
        return_value=True,
    )
    @patch(
        "app.modules.absences.application.leave_settings_commands.build_employee_cp_seniority_context"
    )
    @patch(
        "app.modules.absences.application.leave_settings_commands.get_leave_policy"
    )
    @patch(
        "app.modules.absences.application.leave_settings_commands.absence_repository"
    )
    @patch(
        "app.modules.absences.application.leave_settings_commands.get_employee_hire_date",
        return_value="2020-01-01",
    )
    @patch(
        "app.modules.absences.application.leave_settings_commands._ensure_employee_in_company"
    )
    @patch("app.modules.absences.application.leave_settings_commands.supabase")
    def test_only_rtt_fields_sent_on_upsert(
        self,
        mock_supabase,
        _mock_ensure,
        _mock_hire,
        mock_absence_repo,
        _mock_policy,
        mock_build_ctx,
        _mock_eligible,
        mock_compute_rtt,
        mock_upsert,
    ):
        mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
            data=[{"id": "emp-1"}]
        )
        mock_build_ctx.return_value = MagicMock()
        mock_absence_repo.list_validated_for_employees.return_value = []
        mock_compute_rtt.return_value = {"solde": 0.0}
        mock_upsert.return_value = {
            "cp_n1_opening_balance": 0,
            "cp_n_opening_balance": 0,
            "rtt_opening_balance": 4.5,
            "rtt_forfeited_days": 0,
            "note": "Reprise",
        }

        apply_rtt_solde_manual(
            "co-1",
            "emp-1",
            date.today().year,
            rtt_solde=4.5,
            note="Reprise",
        )

        payload = mock_upsert.call_args.args[3]
        assert set(payload.keys()) == {"rtt_opening_balance", "note"}
        assert payload["rtt_opening_balance"] == 4.5
        assert payload["note"] == "Reprise"
