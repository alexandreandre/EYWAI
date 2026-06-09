"""Règles d'accès au dossier documents pendant un départ."""

from datetime import date

import pytest

from app.modules.employee_exits.domain.document_access import (
    rh_can_view_employee_documents,
    rh_documents_access_message,
    rh_should_list_in_documents_explorer,
)

pytestmark = pytest.mark.unit


def test_rh_can_view_active_employee_documents():
    assert rh_can_view_employee_documents({"employment_status": "actif"}) is True


def test_rh_can_view_en_sortie_until_last_working_day():
    employee = {
        "employment_status": "en_sortie",
        "exit_last_working_day": "2026-07-08",
    }
    assert (
        rh_can_view_employee_documents(employee, reference_date=date(2026, 7, 8))
        is True
    )
    assert (
        rh_can_view_employee_documents(employee, reference_date=date(2026, 7, 9))
        is False
    )


def test_rh_documents_access_message_for_en_sortie():
    message = rh_documents_access_message(
        {
            "employment_status": "en_sortie",
            "exit_last_working_day": "2026-07-08",
        }
    )
    assert message is not None
    assert "08/07/2026" in message
    assert "dossier documents" in message


def test_rh_should_not_list_parti_in_documents_explorer():
    assert (
        rh_should_list_in_documents_explorer({"employment_status": "parti"})
        is False
    )


def test_rh_should_not_list_en_sortie_after_last_day_in_explorer():
    employee = {
        "employment_status": "en_sortie",
        "exit_last_working_day": "2026-06-01",
    }
    assert (
        rh_should_list_in_documents_explorer(
            employee, reference_date=date(2026, 6, 8)
        )
        is False
    )
    assert (
        rh_should_list_in_documents_explorer(
            employee, reference_date=date(2026, 6, 1)
        )
        is True
    )
