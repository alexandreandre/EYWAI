"""Tests unitaires — calcul des retards onboarding."""

from datetime import date

from app.modules.onboarding.domain.overdue import (
    count_overdue_tasks,
    is_task_overdue,
    parse_hire_date,
    summarize_tasks,
)


class TestParseHireDate:
    def test_iso_string(self):
        assert parse_hire_date("2026-04-01") == date(2026, 4, 1)

    def test_datetime_string(self):
        assert parse_hire_date("2026-04-01T10:00:00Z") == date(2026, 4, 1)


class TestIsTaskOverdue:
    def test_overdue_when_past_due(self):
        hire = date(2026, 4, 1)
        ref = date(2026, 4, 10)
        assert is_task_overdue(hire, 3, False, ref) is True

    def test_not_overdue_when_completed(self):
        hire = date(2026, 4, 1)
        ref = date(2026, 4, 10)
        assert is_task_overdue(hire, 3, True, ref) is False

    def test_not_overdue_before_due(self):
        hire = date(2026, 4, 1)
        ref = date(2026, 4, 3)
        assert is_task_overdue(hire, 3, False, ref) is False


class TestCountOverdueTasks:
    def test_counts_only_open_overdue(self):
        hire = date(2026, 4, 1)
        ref = date(2026, 4, 20)
        tasks = [
            {"due_days": 1, "is_completed": False},
            {"due_days": 30, "is_completed": False},
            {"due_days": 1, "is_completed": True},
        ]
        assert count_overdue_tasks(hire, tasks, ref) == 1


class TestSummarizeTasks:
    def test_progress_pct(self):
        tasks = [
            {"is_completed": True},
            {"is_completed": False},
            {"is_completed": True},
        ]
        nb_completed, nb_total, pct = summarize_tasks(tasks)
        assert nb_completed == 2
        assert nb_total == 3
        assert abs(pct - 200 / 3) < 0.01
