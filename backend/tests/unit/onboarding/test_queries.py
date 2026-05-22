"""Tests unitaires — queries onboarding (repository mocké)."""

from datetime import date, datetime, timezone
from unittest.mock import MagicMock, patch

from app.modules.onboarding.application import queries


class TestListHubSummaries:
    def test_delegates_to_repository(self):
        repo = MagicMock()
        repo.list_hub_summaries.return_value = {
            "items": [
                {
                    "employee_id": "emp-1",
                    "first_name": "Jean",
                    "last_name": "Dupont",
                    "job_title": "Dev",
                    "hire_date": date(2026, 4, 1),
                    "days_since_hire": 10,
                    "checklist_id": "cl-1",
                    "has_checklist": True,
                    "progress_pct": 50.0,
                    "nb_total": 4,
                    "nb_completed": 2,
                    "nb_overdue": 1,
                    "completed_at": None,
                    "checklist_created_at": datetime(2026, 4, 1, tzinfo=timezone.utc),
                }
            ],
            "kpis": {
                "in_progress": 1,
                "overdue_tasks": 1,
                "completed_this_month": 0,
            },
            "lookback_days": 90,
        }

        with patch(
            "app.modules.onboarding.application.queries.onboarding_repository",
            repo,
        ):
            result = queries.list_hub_summaries("co-1", 90)

        assert result["lookback_days"] == 90
        assert len(result["items"]) == 1
        assert result["items"][0]["employee_id"] == "emp-1"
        assert result["kpis"]["overdue_tasks"] == 1
        repo.list_hub_summaries.assert_called_once_with("co-1", 90)
