"""Tests unitaires rapprochement IJSS."""

from app.modules.ijss_tracking.domain.reconciliation import (
    aggregate_line_status,
    aggregate_period_status,
    match_received_to_employee,
)


def test_match_by_nir():
    employees = [{"id": "e1", "first_name": "Jean", "last_name": "DUPONT", "nir": "1234567890123"}]
    match = match_received_to_employee(
        employee_name_raw="",
        employee_nir="1234567890123",
        amount=842.50,
        employees=employees,
        expected_lines=[],
    )
    assert match is not None
    assert match.employee_id == "e1"
    assert match.confidence == "strong"


def test_aggregate_line_ok():
    assert aggregate_line_status(
        expected_amount=842.50,
        cpam_amount=842.50,
        bank_amount=842.50,
        threshold=1.0,
        has_justification=False,
    ) == "ok"


def test_aggregate_line_variance():
    assert aggregate_line_status(
        expected_amount=842.50,
        cpam_amount=610.0,
        bank_amount=610.0,
        threshold=1.0,
        has_justification=False,
    ) == "variance"


def test_aggregate_period_status():
    assert aggregate_period_status(["ok", "ok", "justified"]) == "reconciled"
    assert aggregate_period_status(["ok", "variance"]) == "partial"
