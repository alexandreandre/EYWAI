"""Tests commandes médailles du travail."""

from __future__ import annotations

from datetime import date
from unittest.mock import patch

import pytest

from app.modules.monthly_inputs.application.dto import CreateSingleResultDto
from app.modules.work_medals.application import commands
from app.modules.work_medals.schemas.requests import (
    WorkMedalApproveRequest,
    WorkMedalDismissRequest,
    WorkMedalSettingsUpdate,
)
from app.modules.work_medals.schemas.responses import MedalTier, WorkMedalCase, WorkMedalSettings


@pytest.fixture
def mock_settings():
    return WorkMedalSettings(
        company_id="company-1",
        enabled=True,
        tiers=[
            MedalTier(
                level="argent",
                years=20,
                label="Médaille d'argent (20 ans)",
                amount_mode="fixed",
                amount_value=400,
            )
        ],
    )


@pytest.fixture
def awaiting_rh_case():
    return WorkMedalCase(
        id="case-1",
        company_id="company-1",
        employee_id="emp-1",
        medal_level="argent",
        milestone_years=20,
        eligible_date=date(2026, 1, 1),
        status="awaiting_rh",
    )


def test_approve_creates_monthly_input(awaiting_rh_case, mock_settings):
    with patch(
        "app.modules.work_medals.application.commands.queries.get_work_medal_case",
        return_value=awaiting_rh_case,
    ):
        with patch(
            "app.modules.work_medals.application.commands.queries.get_work_medal_settings_raw",
            return_value=mock_settings,
        ):
            with patch(
                "app.modules.work_medals.application.commands._get_employee_row",
                return_value={
                    "id": "emp-1",
                    "company_id": "company-1",
                    "salaire_de_base": {"valeur": 2500},
                },
            ):
                with patch(
                    "app.modules.work_medals.application.commands.create_employee_monthly_input",
                    return_value=CreateSingleResultDto(
                        inserted_data={"id": "mi-1", "amount": 400}
                    ),
                ) as create_input:
                    with patch(
                        "app.modules.work_medals.application.commands.work_medal_cases_repository.update"
                    ) as update:
                        update.return_value = {
                            **awaiting_rh_case.model_dump(mode="json"),
                            "status": "paid",
                            "amount_computed": 400,
                            "monthly_input_id": "mi-1",
                        }
                        with patch(
                            "app.modules.work_medals.application.commands.notify_employee_approved"
                        ):
                            result = commands.approve_work_medal_case(
                                "case-1",
                                "company-1",
                                "rh-user",
                                WorkMedalApproveRequest(
                                    payroll_year=2026, payroll_month=6
                                ),
                            )
                            assert result.status == "paid"
                            create_input.assert_called_once()
                            args = create_input.call_args[0]
                            assert args[0] == "emp-1"
                            prime = args[1]
                            assert prime.amount == 400
                            assert prime.is_taxable is True
                            assert prime.is_socially_taxed is False


def test_dismissed_case_no_payroll(awaiting_rh_case):
    with patch(
        "app.modules.work_medals.application.commands.queries.get_work_medal_case",
        return_value=awaiting_rh_case,
    ):
        with patch(
            "app.modules.work_medals.application.commands.create_employee_monthly_input"
        ) as create_input:
            with patch(
                "app.modules.work_medals.application.commands.work_medal_cases_repository.update"
            ) as update:
                update.return_value = {
                    **awaiting_rh_case.model_dump(mode="json"),
                    "status": "dismissed",
                }
                result = commands.dismiss_work_medal_case(
                    "case-1",
                    "company-1",
                    WorkMedalDismissRequest(reason="Déjà payé"),
                )
                assert result.status == "dismissed"
                create_input.assert_not_called()


def test_approve_legacy_awaiting_employee(awaiting_rh_case, mock_settings):
    legacy_case = WorkMedalCase(
        **{**awaiting_rh_case.model_dump(), "status": "awaiting_employee"}
    )
    with patch(
        "app.modules.work_medals.application.commands.queries.get_work_medal_case",
        return_value=legacy_case,
    ):
        with patch(
            "app.modules.work_medals.application.commands.queries.get_work_medal_settings_raw",
            return_value=mock_settings,
        ):
            with patch(
                "app.modules.work_medals.application.commands._get_employee_row",
                return_value={
                    "id": "emp-1",
                    "company_id": "company-1",
                    "salaire_de_base": {"valeur": 2500},
                },
            ):
                with patch(
                    "app.modules.work_medals.application.commands.create_employee_monthly_input",
                    return_value=CreateSingleResultDto(
                        inserted_data={"id": "mi-1", "amount": 400}
                    ),
                ):
                    with patch(
                        "app.modules.work_medals.application.commands.work_medal_cases_repository.update"
                    ) as update:
                        update.return_value = {
                            **legacy_case.model_dump(mode="json"),
                            "status": "paid",
                        }
                        with patch(
                            "app.modules.work_medals.application.commands.notify_employee_approved"
                        ):
                            result = commands.approve_work_medal_case(
                                "case-1",
                                "company-1",
                                "rh-user",
                                WorkMedalApproveRequest(
                                    payroll_year=2026, payroll_month=6
                                ),
                            )
                            assert result.status == "paid"


def test_save_settings_triggers_scan_when_enabling(mock_settings):
    disabled = WorkMedalSettings(
        company_id="company-1",
        enabled=False,
        tiers=mock_settings.tiers,
    )
    with patch(
        "app.modules.work_medals.application.commands.queries.get_work_medal_settings",
        return_value=disabled,
    ):
        with patch(
            "app.modules.work_medals.application.commands.work_medal_settings_repository.upsert",
            return_value={"company_id": "company-1", "enabled": True, "tiers": []},
        ):
            with patch(
                "app.modules.work_medals.application.commands.queries._settings_from_row",
                return_value=WorkMedalSettings(company_id="company-1", enabled=True, tiers=[]),
            ):
                with patch(
                    "app.modules.work_medals.application.detection.scan_company_work_medals"
                ) as scan:
                    commands.save_work_medal_settings(
                        "company-1",
                        WorkMedalSettingsUpdate(enabled=True),
                    )
                    scan.assert_called_once_with("company-1")
