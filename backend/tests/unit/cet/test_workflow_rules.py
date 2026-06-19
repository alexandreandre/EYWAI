"""Tests règles workflow CET."""

from app.modules.cet.domain.rules import (
    resolve_initial_workflow,
    validate_request_deadline,
)


def test_resolve_auto():
    status, step = resolve_initial_workflow("auto", has_manager=True)
    assert status == "validated"
    assert step == "approved_rh"


def test_resolve_manager_with_team():
    status, step = resolve_initial_workflow("manager", has_manager=True)
    assert status == "pending"
    assert step == "pending_manager"


def test_resolve_manager_without_team_falls_back_rh():
    status, step = resolve_initial_workflow("manager", has_manager=False)
    assert status == "pending"
    assert step == "pending"


def test_request_deadline_blocks():
    try:
        validate_request_deadline(20, 15)
        assert False, "expected ValueError"
    except ValueError as e:
        assert "Date limite" in str(e)


def test_request_deadline_ok():
    validate_request_deadline(10, 15)
