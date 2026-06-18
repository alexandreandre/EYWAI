from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from app.modules.badgeuse.application.deps import deps
from app.modules.badgeuse.application.punch_service import get_day_detail_for_employee
from app.modules.schedules.application.badgeuse_import import (
    import_actual_hours_from_badgeuse,
)
from app.modules.schedules.application.exceptions import ScheduleAppError


def test_get_day_detail_includes_accounting_fields():
    entries = []
    with (
        patch.object(
            deps.time_entry_repository,
            "get_entries_for_employee_on_day",
            return_value=entries,
        ),
        patch.object(
            deps.time_entry_validation_repository,
            "is_day_validated",
            return_value=False,
        ),
        patch.object(
            deps.day_accounting_repository,
            "get_accounted_seconds",
            return_value=28800,
        ),
    ):
        detail = get_day_detail_for_employee(
            employee_id="emp-1",
            company_id="co-1",
            day=date(2026, 6, 17),
        )

    assert detail["computed_seconds"] == 0
    assert detail["accounted_seconds"] == 28800
    assert detail["effective_seconds"] == 28800
    assert detail["has_override"] is True
    assert detail["override_differs_from_computed"] is True


@patch(
    "app.modules.schedules.application.badgeuse_import.calculate_payroll_events"
)
@patch("app.modules.schedules.application.badgeuse_import.update_actual_hours")
@patch(
    "app.modules.schedules.application.badgeuse_import.badgeuse_punch_service.get_summary_for_employee_period"
)
@patch(
    "app.modules.schedules.application.badgeuse_import.schedule_repository.get_actual_hours",
    return_value=None,
)
@patch(
    "app.modules.schedules.application.badgeuse_import.schedule_repository.get_planned_calendar",
    return_value={
        "calendrier_prevu": [
            {"jour": 10, "type": "travail", "heures_prevues": 8.5},
        ]
    },
)
@patch(
    "app.modules.schedules.application.badgeuse_import.get_employee_company_and_statut",
    return_value=("co-1", "CDI"),
)
def test_import_badgeuse_writes_heures_faites(
    _mock_statut,
    _mock_planned,
    _mock_actual,
    mock_summary,
    mock_update_actual,
    _mock_payroll,
):
    from app.modules.badgeuse.application._internals import DayStatusDTO

    mock_summary.return_value = {
        date(2026, 6, 10): DayStatusDTO(
            date=date(2026, 6, 10),
            status="Complet",
            total_seconds=30600,
            sequences_count=1,
            has_anomalies=False,
            validated=False,
            computed_seconds=30600,
            accounted_seconds=28800,
            effective_seconds=28800,
            has_override=True,
            override_differs_from_computed=True,
        ),
    }

    result = import_actual_hours_from_badgeuse(
        "emp-1", 2026, 6, recalculate_payroll=False
    )

    assert result.days_updated == 1
    mock_update_actual.assert_called_once()
    payload = mock_update_actual.call_args[0][1]
    day_10 = next(e for e in payload.calendrier_reel if e.jour == 10)
    assert day_10.heures_faites == pytest.approx(8.0)


@patch(
    "app.modules.schedules.application.badgeuse_import.get_employee_company_and_statut",
    return_value=("co-1", "forfait jour"),
)
def test_import_badgeuse_rejects_forfait_jour(_mock_statut):
    with pytest.raises(ScheduleAppError) as exc:
        import_actual_hours_from_badgeuse("emp-1", 2026, 6)
    assert exc.value.status_code == 400
