"""
Tests non-régression et unitaires du module Planning (conflict_engine).
"""

from __future__ import annotations

import inspect
from pathlib import Path
from typing import Any, get_args

import pytest

from app.modules.planning.domain.conflict_engine import (
    check_absence_conflict,
    check_contract_overtime,
    check_shift_overlap,
    check_weekly_rest,
    run_all_checks,
)

# ---------------------------------------------------------------------------
# Chemins repo (backend/tests → racine EYWAI)
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[4]
_FRONTEND_PLANNING_TS = _REPO_ROOT / "frontend" / "src" / "api" / "planning.ts"
_PLANNING_MIGRATION_SQL = (
    _REPO_ROOT / "supabase" / "migrations" / "20260422100001_planning_module.sql"
)


# =============================================================================
# Partie 1 — Non-régression
# =============================================================================


def test_planning_imports_do_not_break_existing_modules() -> None:
    """Imports du module Planning sans ImportError."""
    import app.modules.planning.api.router  # noqa: F401
    import app.modules.planning.application.commands  # noqa: F401
    import app.modules.planning.application.queries  # noqa: F401
    import app.modules.planning.infrastructure.repository  # noqa: F401


def test_planning_router_registered_in_main() -> None:
    """Le préfixe /api/planning est bien enregistré sur l'application FastAPI."""
    from app.main import app

    from tests.route_helpers import collect_app_route_paths

    paths = collect_app_route_paths(app)
    assert any("/api/planning" in p for p in paths), (
        "Aucune route ne contient /api/planning — vérifiez include_router(planning_router)."
    )


def test_absence_module_status_unchanged() -> None:
    """AbsenceStatus inchangé (Literal)."""
    from app.modules.absences.schemas.requests import AbsenceStatus

    values = set(get_args(AbsenceStatus))
    assert values == {"pending", "validated", "rejected", "cancelled"}


def test_payroll_employee_schedules_write_pattern() -> None:
    """Transmission paie : écriture sur employee_schedules, pas payroll_variable_elements."""
    from app.modules.planning.application import commands as planning_commands

    src = inspect.getsource(planning_commands._transmit_to_payroll)
    assert "employee_schedules" in src
    assert "payroll_variable_elements" not in src


def test_shift_update_payload_has_transverse_category() -> None:
    """Le client TS expose transverse_category sur ShiftUpdatePayload."""
    assert _FRONTEND_PLANNING_TS.is_file(), f"Fichier manquant : {_FRONTEND_PLANNING_TS}"
    text = _FRONTEND_PLANNING_TS.read_text(encoding="utf-8")
    assert "ShiftUpdatePayload" in text
    assert "transverse_category" in text


def test_planning_migration_file_exists() -> None:
    assert _PLANNING_MIGRATION_SQL.is_file(), (
        f"Migration planning introuvable : {_PLANNING_MIGRATION_SQL}"
    )


def test_planning_migration_contains_required_tables() -> None:
    sql = _PLANNING_MIGRATION_SQL.read_text(encoding="utf-8")
    required = [
        "collective_agreements",
        "shift_types",
        "shifts",
        "planning_week_status",
        "planning_day_status",
        "planning_lock_history",
        "company_planning_settings",
    ]
    for name in required:
        assert f"CREATE TABLE IF NOT EXISTS public.{name}" in sql, (
            f"Table attendue absente ou renommée : {name}"
        )


# =============================================================================
# Partie 2 — Fixtures conflict_engine
# =============================================================================


@pytest.fixture
def absence_cp() -> dict[str, Any]:
    return {"type": "CP", "selected_days": ["2026-04-21", "2026-04-22"]}


@pytest.fixture
def shift_morning() -> dict[str, Any]:
    return {
        "id": "shift-1",
        "shift_date": "2026-04-21",
        "start_time": "08:00:00",
        "end_time": "16:00:00",
        "transverse_category": None,
    }


@pytest.fixture
def shift_afternoon() -> dict[str, Any]:
    return {
        "id": "shift-2",
        "shift_date": "2026-04-21",
        "start_time": "14:00:00",
        "end_time": "22:00:00",
        "transverse_category": None,
    }


@pytest.fixture
def shift_night() -> dict[str, Any]:
    return {
        "id": "shift-3",
        "shift_date": "2026-04-21",
        "start_time": "22:00:00",
        "end_time": "06:00:00",
        "transverse_category": None,
    }


# --- check_absence_conflict (3) ---


def test_absence_conflict_detected(absence_cp: dict[str, Any]) -> None:
    r = check_absence_conflict("2026-04-21", [absence_cp])
    assert r.has_blocking_conflict is True
    assert r.conflict_type == "absence_conflict"


def test_absence_no_conflict_different_date(absence_cp: dict[str, Any]) -> None:
    r = check_absence_conflict("2026-04-23", [absence_cp])
    assert r.has_blocking_conflict is False
    assert r.conflict_type == "no_conflict"


def test_absence_empty_list() -> None:
    r = check_absence_conflict("2026-04-21", [])
    assert r.has_blocking_conflict is False


# --- check_shift_overlap (4) ---


def test_overlap_detected(shift_morning: dict[str, Any]) -> None:
    r = check_shift_overlap("14:00", "22:00", [shift_morning])
    assert r.has_blocking_conflict is True
    assert r.conflict_type == "shift_overlap"


def test_no_overlap_adjacent(shift_morning: dict[str, Any]) -> None:
    r = check_shift_overlap("16:00", "22:00", [shift_morning])
    assert r.has_blocking_conflict is False
    assert r.conflict_type == "no_conflict"


def test_no_overlap_excluded_shift(shift_morning: dict[str, Any]) -> None:
    r = check_shift_overlap(
        "08:00", "16:00", [shift_morning], exclude_shift_id="shift-1"
    )
    assert r.has_blocking_conflict is False


def test_overlap_night_shift(shift_night: dict[str, Any]) -> None:
    r = check_shift_overlap("23:00", "02:00", [shift_night])
    assert r.has_blocking_conflict is True
    assert r.conflict_type == "shift_overlap"


# --- check_weekly_rest (3) ---


def _shift_day(
    day: str, start: str, end: str, sid: str, transverse: None | str = None
) -> dict[str, Any]:
    return {
        "id": sid,
        "shift_date": day,
        "start_time": start,
        "end_time": end,
        "transverse_category": transverse,
    }


def test_weekly_rest_ok() -> None:
    """Lun–ven 8h, week-end libre → pas de violation du repos hebdo."""
    week = [
        _shift_day("2026-04-20", "08:00:00", "16:00:00", "a1"),
        _shift_day("2026-04-21", "08:00:00", "16:00:00", "a2"),
        _shift_day("2026-04-22", "08:00:00", "16:00:00", "a3"),
        _shift_day("2026-04-23", "08:00:00", "16:00:00", "a4"),
        _shift_day("2026-04-24", "08:00:00", "16:00:00", "a5"),
    ]
    r = check_weekly_rest(week, min_rest_hours=35)
    assert r.conflict_type == "no_conflict"
    assert r.is_warning_only is False


def test_weekly_rest_violation() -> None:
    """7 jours 06:00–22:00 → créneaux de repos < 35 h."""
    days = [
        "2026-04-20",
        "2026-04-21",
        "2026-04-22",
        "2026-04-23",
        "2026-04-24",
        "2026-04-25",
        "2026-04-26",
    ]
    week = [
        _shift_day(d, "06:00:00", "22:00:00", f"full-{i}")
        for i, d in enumerate(days)
    ]
    r = check_weekly_rest(week, min_rest_hours=35)
    assert r.conflict_type == "weekly_rest_violation"
    assert r.is_warning_only is True


def test_weekly_rest_empty_week() -> None:
    r = check_weekly_rest([])
    assert r.conflict_type == "no_conflict"


# --- check_contract_overtime (2) ---


def test_contract_overtime_detected() -> None:
    week = [
        _shift_day("2026-04-20", "08:00:00", "17:00:00", "d1"),
        _shift_day("2026-04-21", "08:00:00", "17:00:00", "d2"),
        _shift_day("2026-04-22", "08:00:00", "17:00:00", "d3"),
        _shift_day("2026-04-23", "08:00:00", "17:00:00", "d4"),
        _shift_day("2026-04-24", "08:00:00", "17:00:00", "d5"),
    ]
    r = check_contract_overtime(week, 35.0)
    assert r.conflict_type == "contract_overtime"
    assert r.is_warning_only is True
    assert "+10h00" in r.message


def test_contract_no_overtime() -> None:
    week = [
        _shift_day("2026-04-20", "08:00:00", "15:00:00", "n1"),
        _shift_day("2026-04-21", "08:00:00", "15:00:00", "n2"),
        _shift_day("2026-04-22", "08:00:00", "15:00:00", "n3"),
        _shift_day("2026-04-23", "08:00:00", "15:00:00", "n4"),
        _shift_day("2026-04-24", "08:00:00", "15:00:00", "n5"),
    ]
    r = check_contract_overtime(week, 35.0)
    assert r.conflict_type == "no_conflict"


# --- run_all_checks (3) ---


def test_run_all_checks_blocking_stops_chain(absence_cp: dict[str, Any]) -> None:
    """Conflit absence bloquant : la chaîne s'arrête après le premier check."""
    results = run_all_checks(
        shift_date="2026-04-21",
        new_start="10:00",
        new_end="12:00",
        existing_absences=[absence_cp],
        existing_day_shifts=[],
        week_shifts=[],
        contract_hours_per_week=35.0,
        exclude_shift_id=None,
        min_rest_hours=35,
    )
    assert len(results) == 1
    assert results[0].has_blocking_conflict is True
    assert results[0].conflict_type == "absence_conflict"


def test_run_all_checks_warnings_continue() -> None:
    """Pas de blocage : repos hebdo + dépassement contrat (2 avertissements)."""
    days = [
        "2026-04-20",
        "2026-04-21",
        "2026-04-22",
        "2026-04-23",
        "2026-04-24",
        "2026-04-25",
        "2026-04-26",
    ]
    week = [
        _shift_day(d, "06:00:00", "22:00:00", f"w-{i}")
        for i, d in enumerate(days)
    ]
    results = run_all_checks(
        shift_date="2026-04-20",
        new_start="23:00",
        new_end="23:30",
        existing_absences=[],
        existing_day_shifts=[],
        week_shifts=week,
        contract_hours_per_week=35.0,
        exclude_shift_id=None,
        min_rest_hours=35,
    )
    # L'implémentation enchaîne 4 contrôles ; les 2 derniers peuvent être des warnings.
    assert len(results) == 4
    warnings = [r for r in results if r.is_warning_only]
    types = {r.conflict_type for r in warnings}
    assert "weekly_rest_violation" in types
    assert "contract_overtime" in types
    assert len(warnings) >= 2


def test_run_all_checks_no_conflict() -> None:
    """Semaine légère : aucun conflit bloquant ni avertissement métier."""
    week = [_shift_day("2026-04-20", "08:00:00", "15:00:00", "solo")]
    results = run_all_checks(
        shift_date="2026-04-20",
        new_start="08:00",
        new_end="15:00",
        existing_absences=[],
        existing_day_shifts=[],
        week_shifts=week,
        contract_hours_per_week=35.0,
        exclude_shift_id=None,
        min_rest_hours=35,
    )
    assert len(results) == 4
    assert all(not r.has_blocking_conflict for r in results)
    blocking_types = {"absence_conflict", "shift_overlap"}
    assert not any(r.conflict_type in blocking_types for r in results)
