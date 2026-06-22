"""Tests détection paliers médailles du travail."""

from __future__ import annotations

from unittest.mock import patch

from app.modules.work_medals.application.detection import scan_company_work_medals
from app.modules.work_medals.schemas.responses import MedalTier, WorkMedalSettings


def test_detection_creates_case_once():
    settings = WorkMedalSettings(
        company_id="company-1",
        enabled=True,
        reminder_months_before=6,
        tiers=[
            MedalTier(
                level="argent",
                years=20,
                label="Argent",
                amount_mode="fixed",
                amount_value=400,
            )
        ],
    )
    employees = [
        {
            "id": "emp-1",
            "hire_date": "2000-01-01",
            "prior_service_months": 0,
            "employment_status": "actif",
            "first_name": "Marie",
            "last_name": "Dupont",
        }
    ]

    with patch(
        "app.modules.work_medals.application.detection.queries.get_work_medal_settings_raw",
        return_value=settings,
    ):
        with patch(
            "app.modules.work_medals.application.detection._list_active_employees",
            return_value=employees,
        ):
            with patch(
                "app.modules.work_medals.application.detection.work_medal_cases_repository.get_by_employee_level",
                return_value=None,
            ):
                with patch(
                    "app.modules.work_medals.application.detection.work_medal_cases_repository.insert"
                ) as insert:
                    insert.return_value = {"id": "case-1", "status": "awaiting_rh"}
                    result = scan_company_work_medals("company-1")
                    assert result.created == 1
                    insert.assert_called_once()
                    payload = insert.call_args[0][0]
                    assert payload["employee_id"] == "emp-1"
                    assert payload["medal_level"] == "argent"
                    assert payload["status"] == "awaiting_rh"


def test_detection_skips_when_disabled():
    settings = WorkMedalSettings(company_id="company-1", enabled=False)
    with patch(
        "app.modules.work_medals.application.detection.queries.get_work_medal_settings_raw",
        return_value=settings,
    ):
        result = scan_company_work_medals("company-1")
        assert result.created == 0
