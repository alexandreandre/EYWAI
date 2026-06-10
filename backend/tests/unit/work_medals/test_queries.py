"""Tests lecture médailles du travail."""

from __future__ import annotations

from unittest.mock import patch

from app.modules.work_medals.application import queries
from app.modules.work_medals.schemas.responses import WorkMedalSettings


def test_list_cases_awaiting_rh_includes_legacy_statuses():
    with patch(
        "app.modules.work_medals.application.queries.work_medal_cases_repository.migrate_legacy_employee_pending"
    ) as migrate:
        with patch(
            "app.modules.work_medals.application.queries.work_medal_cases_repository.list_by_company"
        ) as list_cases:
            migrate.return_value = 1
            list_cases.return_value = []
            queries.list_work_medal_cases("company-1", status="awaiting_rh")
            migrate.assert_called_once_with("company-1")
            list_cases.assert_called_once_with(
                "company-1",
                status=None,
                statuses=["awaiting_rh", "awaiting_employee"],
                medal_level=None,
            )


def test_summary_migrates_legacy_before_count():
    settings = WorkMedalSettings(company_id="company-1", enabled=True, tiers=[])
    with patch(
        "app.modules.work_medals.application.queries.get_work_medal_settings",
        return_value=settings,
    ):
        with patch(
            "app.modules.work_medals.application.queries.work_medal_cases_repository.migrate_legacy_employee_pending"
        ) as migrate:
            with patch(
                "app.modules.work_medals.application.queries.work_medal_cases_repository.count_by_status",
                side_effect=[2, 1],
            ):
                migrate.return_value = 1
                summary = queries.get_work_medal_summary("company-1")
                migrate.assert_called_once_with("company-1")
                assert summary.awaiting_rh == 2
                assert summary.total_actionable == 2
