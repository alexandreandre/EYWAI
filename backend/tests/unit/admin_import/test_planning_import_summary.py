"""Tests résumé import calendrier."""

from app.modules.admin_import.application.planning_import_summary import (
    build_planning_import_summary,
)


def test_summary_counts_unique_sheets_not_month_rows() -> None:
    month_groups = [
        {
            "year": 2026,
            "month": m,
            "employees": [
                {
                    "raw_name": "BOUFRIDA",
                    "employee_id": "e1",
                    "matched_name": "Samir BOUFRIDA",
                    "review_status": "ok",
                    "days": [{"jour": 1, "nature": "prevu"}],
                },
                {
                    "raw_name": "INCONNU",
                    "employee_id": None,
                    "review_status": "error",
                    "days": [{"jour": 1, "nature": "prevu"}],
                },
            ],
        }
        for m in range(1, 13)
    ]
    summary = build_planning_import_summary(
        preview={
            "affected_months": [{"year": 2026, "month": 1}, {"year": 2026, "month": 12}],
            "warnings": [],
        },
        batch_summary={"month_groups": month_groups, "sheets_parsed": 2},
        parser_key="quadra_planning_calendar",
        period_mode="year",
        year=2026,
        month=1,
    )
    assert summary["employees_total"] == 2
    assert summary["employees_ok"] == 1
    assert summary["employees_error"] == 1
    assert summary["employees_importable"] == 1
    assert summary["days_total"] == 12
    assert summary["validation_status"] == "warning"
