"""Tests filtrage période import planning / relevé."""

from datetime import date

from app.modules.schedules.application.timesheet_import.structured_parser import TabularDayRow
from app.modules.schedules.application.timesheet_import.tabular_period import (
    ImportPeriodConfig,
    apply_import_period_to_rows,
    collect_dates_from_rows,
)


def _row(y: int, m: int, d: int, name: str = "Alice") -> TabularDayRow:
    return TabularDayRow(
        raw_name=name,
        matricule="001",
        jour=d,
        month=m,
        year=y,
        heures=7.0,
    )


class TestApplyImportPeriodToRows:
    def test_year_mode_keeps_all_months_in_year(self):
        rows = [_row(2026, 1, 5), _row(2026, 3, 12), _row(2025, 12, 31)]
        result = apply_import_period_to_rows(
            rows,
            config=ImportPeriodConfig(mode="year", year=2026, month=1),
        )
        dates = collect_dates_from_rows(result.rows)
        assert dates == [date(2026, 1, 5), date(2026, 3, 12)]

    def test_range_mode_filters_custom_bounds(self):
        rows = [_row(2026, 2, 1), _row(2026, 4, 1), _row(2026, 6, 1)]
        result = apply_import_period_to_rows(
            rows,
            config=ImportPeriodConfig(
                mode="range",
                year=2026,
                month=1,
                start_year=2026,
                start_month=2,
                end_year=2026,
                end_month=4,
            ),
        )
        dates = collect_dates_from_rows(result.rows)
        assert dates == [date(2026, 2, 1), date(2026, 4, 1)]

    def test_month_mode_still_filters_single_month(self):
        rows = [_row(2026, 6, 8), _row(2026, 7, 2)]
        result = apply_import_period_to_rows(
            rows,
            config=ImportPeriodConfig(mode="month", year=2026, month=6),
        )
        dates = collect_dates_from_rows(result.rows)
        assert dates == [date(2026, 6, 8)]
