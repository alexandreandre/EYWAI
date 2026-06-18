"""Tests fusion multi-pages."""

from app.modules.schedules.application.timesheet_page_consensus import (
    PageEmployee,
    PageExtractionResult,
)
from app.modules.schedules.application.timesheet_page_merge import merge_page_results


def test_merge_by_matricule_across_pages():
    page1 = PageExtractionResult(
        page_index=1,
        employees=[
            PageEmployee(
                raw_name="DUPONT Jean",
                matricule="42",
                days=[{"jour": 25, "heures": 7.0, "type": "travail"}],
            )
        ],
    )
    page2 = PageExtractionResult(
        page_index=2,
        employees=[
            PageEmployee(
                raw_name="DUPONT Jean",
                matricule="42",
                days=[{"jour": 26, "heures": 8.0, "type": "travail"}],
            )
        ],
    )
    merged = merge_page_results([page1, page2])
    assert len(merged.employees) == 1
    assert len(merged.employees[0].days) == 2


def test_merge_zero_hour_days():
    page = PageExtractionResult(
        page_index=1,
        employees=[
            PageEmployee(
                raw_name="VIDE Semaine",
                matricule="99",
                days=[
                    {"jour": 25, "heures": 0.0, "type": "travail"},
                    {"jour": 26, "heures": 0.0, "type": "travail"},
                ],
            )
        ],
    )
    merged = merge_page_results([page])
    assert len(merged.employees) == 1
    assert len(merged.employees[0].days) == 2
