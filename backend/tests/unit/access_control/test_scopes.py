"""Tests unitaires — évaluation des permissions scopées (fail-closed)."""

from __future__ import annotations

from app.modules.access_control.domain.scopes import (
    EmployeeAccessContext,
    build_grant_from_rows,
    evaluate_employee_access,
    filter_allowed_employee_ids,
)


def _emp(eid: str, company: str = "co-1", team: str | None = "team-mod") -> EmployeeAccessContext:
    return EmployeeAccessContext(employee_id=eid, company_id=company, team_id=team)


def test_absent_grant_denies():
    assert evaluate_employee_access(None, _emp("e1")) is False


def test_company_mismatch_denies():
    grant = build_grant_from_rows(
        permission_id="p1",
        permission_code="payslips.validate",
        company_id="co-1",
        scope_mode="company",
    )
    assert evaluate_employee_access(grant, _emp("e1", company="co-2")) is False


def test_deny_exception_beats_company_scope():
    grant = build_grant_from_rows(
        permission_id="p1",
        permission_code="payslips.validate",
        company_id="co-1",
        scope_mode="company",
        targets=[{"employee_id": "boss", "effect": "deny"}],
    )
    assert evaluate_employee_access(grant, _emp("boss")) is False
    assert evaluate_employee_access(grant, _emp("other")) is True


def test_allow_exception_beats_teams_and_none():
    grant = build_grant_from_rows(
        permission_id="p1",
        permission_code="payslips.validate",
        company_id="co-1",
        scope_mode="none",
        targets=[{"employee_id": "dir", "effect": "allow"}],
    )
    assert evaluate_employee_access(grant, _emp("dir", team=None)) is True
    assert evaluate_employee_access(grant, _emp("other")) is False


def test_deny_beats_allow_same_employee():
    # Dernière valeur wins dans build ; on force deny prioritaire via evaluate order
    grant = build_grant_from_rows(
        permission_id="p1",
        permission_code="payslips.validate",
        company_id="co-1",
        scope_mode="company",
        targets=[
            {"employee_id": "x", "effect": "allow"},
            {"employee_id": "x", "effect": "deny"},
        ],
    )
    assert evaluate_employee_access(grant, _emp("x")) is False


def test_teams_scope_requires_matching_team():
    grant = build_grant_from_rows(
        permission_id="p1",
        permission_code="expenses.approve",
        company_id="co-1",
        scope_mode="teams",
        team_ids=["team-mod"],
    )
    assert evaluate_employee_access(grant, _emp("a", team="team-mod")) is True
    assert evaluate_employee_access(grant, _emp("b", team="team-moi")) is False
    assert evaluate_employee_access(grant, _emp("c", team=None)) is False


def test_filter_allowed_preserves_order_and_uniqueness():
    grant = build_grant_from_rows(
        permission_id="p1",
        permission_code="schedules.view_all",
        company_id="co-1",
        scope_mode="teams",
        team_ids=["t1"],
        targets=[{"employee_id": "extra", "effect": "allow"}],
    )
    employees = [
        _emp("a", team="t1"),
        _emp("b", team="t2"),
        _emp("a", team="t1"),
        _emp("extra", team=None),
    ]
    assert filter_allowed_employee_ids(grant, employees) == ["a", "extra"]
