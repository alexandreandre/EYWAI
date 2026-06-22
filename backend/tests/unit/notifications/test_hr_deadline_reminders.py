"""Tests unitaires relances e-mail RH échéances."""

from __future__ import annotations

from datetime import date
from unittest.mock import patch

from app.modules.employees.domain.deadline_reminders import (
    REMINDER_TYPE_CDD,
    DeadlineCandidate,
)
from app.modules.notifications.application import hr_deadline_reminders as module


COMPANY_ID = "550e8400-e29b-41d4-a716-446655440000"


def _candidate(employee_id: str = "emp-1") -> DeadlineCandidate:
    return DeadlineCandidate(
        employee_id=employee_id,
        reminder_type=REMINDER_TYPE_CDD,
        deadline=date(2025, 6, 15),
        days_remaining=10,
        label="Fin de CDD le 15/06/2025",
        first_name="Alice",
        last_name="Martin",
    )


class TestSendHrDeadlineReminders:
    @patch.object(module, "log_reminder_sent", return_value=True)
    @patch.object(module, "_send_grouped_email", return_value=(1, 0))
    @patch.object(module, "fetch_rh_recipient_emails", return_value=["rh@test.com"])
    @patch.object(module, "fetch_company_name", return_value="ACME")
    @patch.object(module, "was_reminder_sent", return_value=False)
    @patch.object(module, "list_hr_deadline_candidates")
    @patch.object(module, "fetch_employees_for_hr_deadline_reminders")
    def test_sends_and_logs_new_candidates(
        self,
        mock_fetch_employees,
        mock_list_candidates,
        mock_was_sent,
        mock_company_name,
        mock_recipients,
        mock_send_email,
        mock_log,
    ):
        mock_fetch_employees.return_value = [{"id": "emp-1"}]
        mock_list_candidates.return_value = [_candidate()]

        result = module.send_hr_deadline_reminders(COMPANY_ID)

        assert result["sent"] == 1
        assert result["skipped"] == 0
        mock_send_email.assert_called_once()
        mock_log.assert_called_once()

    @patch.object(module, "_send_grouped_email")
    @patch.object(module, "was_reminder_sent", return_value=True)
    @patch.object(module, "list_hr_deadline_candidates")
    @patch.object(module, "fetch_employees_for_hr_deadline_reminders")
    def test_skips_already_sent(
        self,
        mock_fetch_employees,
        mock_list_candidates,
        mock_was_sent,
        mock_send_email,
    ):
        mock_fetch_employees.return_value = [{"id": "emp-1"}]
        mock_list_candidates.return_value = [_candidate()]

        result = module.send_hr_deadline_reminders(COMPANY_ID)

        assert result["sent"] == 0
        assert result["skipped"] == 1
        mock_send_email.assert_not_called()


class TestBuildEmailContent:
    def test_build_email_contains_candidates(self):
        text, html = module._build_email_content("ACME", [_candidate()])
        assert "Alice Martin" in text
        assert "Fin de CDD" in text
        assert "Alice Martin" in html


class TestFetchRhRecipientEmails:
    @patch.object(module, "get_user_email", return_value="rh@test.com")
    @patch.object(module, "fetch_company_users_rows")
    def test_filters_rh_roles(self, mock_rows, mock_email):
        mock_rows.return_value = [
            {"user_id": "u1", "role": "rh"},
            {"user_id": "u2", "role": "collaborateur"},
        ]
        emails = module.fetch_rh_recipient_emails(COMPANY_ID)
        assert emails == ["rh@test.com"]
        mock_email.assert_called_once_with("u1")
