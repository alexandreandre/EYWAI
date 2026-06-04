"""Tests unitaires comparison_service (mocks, sans Supabase)."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from app.modules.payslips.application.comparison_service import (
    acquit_payslip_alert_for_user,
    ignore_payslip_alert_for_user,
    validate_payslip_for_user,
)
from app.modules.payslips.application.dto import PayslipCriticalActiveError, UserContext
from app.modules.payslips.domain.comparison_engine import ComparisonResult, PayslipAlert


def _ctx_rh() -> UserContext:
    return UserContext(
        user_id="u-rh",
        is_platform_admin=False,
        has_rh_access_in_company=lambda _cid: True,
        active_company_id="c1",
        first_name="Rh",
        last_name="Test",
    )


def test_t17_validate_payslip_blocked_when_active_critical_alert():
    detail = {
        "employee_id": "e1",
        "company_id": "c1",
        "year": 2025,
        "month": 3,
        "payslip_data": {},
    }
    crit = PayslipAlert(
        rule_id="R01",
        level="CRITIQUE",
        message="Variation brut",
        field="salaire_brut",
        value_n=2000.0,
        value_n1=1800.0,
        delta_pct=11.0,
        status="active",
    )
    result = ComparisonResult(
        bulletin_n_id="ps1",
        bulletin_n1_id=None,
        month_n=3,
        year_n=2025,
        month_n1=None,
        year_n1=None,
        lines=[],
        alerts=[crit],
        has_critical=True,
    )
    with (
        patch(
            "app.modules.payslips.application.comparison_service.payslip_meta_reader.get_payslip_meta",
            return_value={"company_id": "c1", "employee_id": "e1"},
        ),
        patch(
            "app.modules.payslips.application.comparison_service.get_payslip_details",
            return_value=detail,
        ),
        patch(
            "app.modules.payslips.application.comparison_service.fetch_previous_validated_payslip",
            return_value=None,
        ),
        patch(
            "app.modules.payslips.application.comparison_service.fetch_employee_statut",
            return_value=None,
        ),
        patch(
            "app.modules.payslips.application.comparison_service.fetch_recent_nets_asc_for_r10",
            return_value=[],
        ),
        patch(
            "app.modules.payslips.application.comparison_service.compute_comparison",
            return_value=result,
        ),
        patch(
            "app.modules.payslips.application.comparison_service.mark_payslip_validated",
        ) as mock_mark,
    ):
        with pytest.raises(PayslipCriticalActiveError) as excinfo:
            validate_payslip_for_user("ps1", _ctx_rh())
    assert len(excinfo.value.critical_alerts) >= 1
    mock_mark.assert_not_called()


def test_t18_validate_payslip_passes_when_no_active_critical():
    detail = {
        "employee_id": "e1",
        "company_id": "c1",
        "year": 2025,
        "month": 3,
        "payslip_data": {},
    }
    warn = PayslipAlert(
        rule_id="R02",
        level="AVERTISSEMENT",
        message="Variation modérée",
        field="salaire_brut",
        value_n=1030.0,
        value_n1=1000.0,
        delta_pct=3.0,
        status="active",
    )
    result = ComparisonResult(
        bulletin_n_id="ps1",
        bulletin_n1_id=None,
        month_n=3,
        year_n=2025,
        month_n1=None,
        year_n1=None,
        lines=[],
        alerts=[warn],
        has_critical=False,
    )
    with (
        patch(
            "app.modules.payslips.application.comparison_service.payslip_meta_reader.get_payslip_meta",
            return_value={"company_id": "c1", "employee_id": "e1"},
        ),
        patch(
            "app.modules.payslips.application.comparison_service.get_payslip_details",
            return_value=detail,
        ),
        patch(
            "app.modules.payslips.application.comparison_service.fetch_previous_validated_payslip",
            return_value=None,
        ),
        patch(
            "app.modules.payslips.application.comparison_service.fetch_employee_statut",
            return_value=None,
        ),
        patch(
            "app.modules.payslips.application.comparison_service.fetch_recent_nets_asc_for_r10",
            return_value=[],
        ),
        patch(
            "app.modules.payslips.application.comparison_service.compute_comparison",
            return_value=result,
        ),
        patch(
            "app.modules.payslips.application.comparison_service.mark_payslip_validated",
        ) as mock_mark,
    ):
        validate_payslip_for_user("ps1", _ctx_rh())
    mock_mark.assert_called_once_with("ps1", "u-rh")


def test_t19_acquit_alert_updates_status_via_service():
    with (
        patch(
            "app.modules.payslips.application.comparison_service.payslip_meta_reader.get_payslip_meta",
            return_value={"company_id": "c1", "employee_id": "e1"},
        ),
        patch(
            "app.modules.payslips.application.comparison_service.update_payslip_data_alerts_status",
        ) as mock_upd,
    ):
        acquit_payslip_alert_for_user("ps1", "R05", _ctx_rh(), "Vu avec la paie")
    mock_upd.assert_called_once_with(
        "ps1", "R05", "acquittee", "u-rh", "Vu avec la paie"
    )


def test_t20_ignore_alert_updates_status_via_service():
    with (
        patch(
            "app.modules.payslips.application.comparison_service.payslip_meta_reader.get_payslip_meta",
            return_value={"company_id": "c1", "employee_id": "e1"},
        ),
        patch(
            "app.modules.payslips.application.comparison_service.update_payslip_data_alerts_status",
        ) as mock_upd,
    ):
        ignore_payslip_alert_for_user("ps1", "R05", _ctx_rh(), None)
    mock_upd.assert_called_once_with("ps1", "R05", "ignoree", "u-rh", None)
