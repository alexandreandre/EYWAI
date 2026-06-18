"""Tests unitaires — persistance batch import pointages."""

from app.modules.schedules.application.persist_timesheet import persist_timesheet_batch
from app.modules.schedules.schemas.ai import AiDayEntry
from app.modules.schedules.schemas.persist import PersistTimesheetEmployee, PersistTimesheetRequest


class TestPersistTimesheetBatch:
    def test_merges_days_per_employee(self):
        planned_store: dict[str, list] = {"e1": [{"jour": 1, "type": "travail", "heures_prevues": 8}]}
        actual_store: dict[str, list] = {}

        def get_planned(eid, y, m):
            return list(planned_store.get(eid, []))

        def get_actual(eid, y, m):
            return list(actual_store.get(eid, []))

        def update_planned(eid, y, m, rows):
            planned_store[eid] = rows

        def update_actual(eid, y, m, rows):
            actual_store[eid] = rows

        payload = PersistTimesheetRequest(
            year=2026,
            month=5,
            employees=[
                PersistTimesheetEmployee(
                    employee_id="e1",
                    days=[
                        AiDayEntry(jour=26, heures=7.0, type="travail", nature="reel"),
                        AiDayEntry(jour=27, heures=7.0, type="travail", nature="prevu"),
                    ],
                )
            ],
        )
        result = persist_timesheet_batch(
            payload,
            get_planned=get_planned,
            get_actual=get_actual,
            update_planned=update_planned,
            update_actual=update_actual,
        )
        assert result.total_days_written == 2
        assert result.results[0].success is True
        assert any(d["jour"] == 26 for d in actual_store["e1"])
        assert any(d["jour"] == 27 for d in planned_store["e1"])
        assert any(d["jour"] == 1 for d in planned_store["e1"])
