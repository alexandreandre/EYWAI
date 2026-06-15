"""Tests unitaires — règles d'écart calendrier paie."""

from datetime import date

from app.modules.schedules.domain.ecart_rules import (
    compute_day_ecarts,
    compute_heures_supplementaires,
    compute_month_completion,
    compute_row_status,
    detect_absence_conflict_days,
    detect_absence_conflicts,
    is_day_ready_for_payroll,
    is_significant_ecart,
)


def _weekday_planned(day: int, hours: float | None = 8.0):
    return {"jour": day, "type": "travail", "heures_prevues": hours}


def _weekday_actual(day: int, hours: float | None = 8.0):
    return {"jour": day, "type": "travail", "heures_faites": hours}


def _build_full_june_2026(
    weekday_travail,
) -> tuple[list[dict], list[dict]]:
    planned: list[dict] = []
    actual: list[dict] = []
    for day in range(1, 31):
        dt = date(2026, 6, day)
        if dt.weekday() >= 5:
            planned.append({"jour": day, "type": "weekend", "heures_prevues": 0})
            actual.append({"jour": day, "type": "weekend", "heures_faites": 0})
            continue
        prev, fait = weekday_travail(day)
        planned.append({"jour": day, "type": "travail", "heures_prevues": prev})
        actual.append({"jour": day, "type": "travail", "heures_faites": fait})
    return planned, actual


class TestIsDayReadyForPayroll:
    def test_travail_requires_prevu_and_reel(self):
        assert is_day_ready_for_payroll(
            {"jour": 3, "type": "travail", "heures_prevues": 8},
            {"jour": 3, "type": "travail", "heures_faites": 8},
        )
        assert not is_day_ready_for_payroll(
            {"jour": 3, "type": "travail", "heures_prevues": 8},
            {"jour": 3, "type": "travail", "heures_faites": None},
        )

    def test_travail_zero_reel_incomplete_en_horaire(self):
        assert not is_day_ready_for_payroll(
            {"jour": 3, "type": "travail", "heures_prevues": 8},
            {"jour": 3, "type": "travail", "heures_faites": 0},
        )
        assert is_day_ready_for_payroll(
            {"jour": 3, "type": "travail", "heures_prevues": 8},
            {"jour": 3, "type": "travail", "heures_faites": 0},
            forfait=True,
        )

    def test_weekend_complete_without_hours(self):
        assert is_day_ready_for_payroll(
            {"jour": 7, "type": "weekend", "heures_prevues": 0},
            None,
        )

    def test_saturday_travail_requires_reel(self):
        assert not is_day_ready_for_payroll(
            {"jour": 6, "type": "travail", "heures_prevues": 8},
            {"jour": 6, "type": "travail", "heures_faites": None},
        )


class TestComputeMonthCompletion:
    def test_a_saisir_when_actual_missing_on_travail_day(self):
        planned, actual = _build_full_june_2026(
            lambda day: (8, None if day == 10 else 8)
        )
        assert compute_month_completion(planned, actual, 2026, 6) == "a_saisir"

    def test_saisi_when_all_travail_days_complete(self):
        planned, actual = _build_full_june_2026(lambda _day: (8, 8))
        assert compute_month_completion(planned, actual, 2026, 6) == "saisi"


class TestIsSignificantEcart:
    def test_small_ecart_not_significant(self):
        assert is_significant_ecart(160, 161) is False

    def test_large_ratio_is_significant(self):
        assert is_significant_ecart(100, 120) is True

    def test_large_absolute_without_prevu(self):
        assert is_significant_ecart(0, 5) is True


class TestComputeRowStatus:
    def test_a_saisir_when_prevu_missing_on_travail_day(self):
        planned = [_weekday_planned(3), _weekday_planned(4, None)]
        actual = [_weekday_actual(3), _weekday_actual(4)]
        assert compute_row_status(planned, actual, 2026, 6, False) == "a_saisir"

    def test_a_saisir_when_reel_missing_on_travail_day(self):
        planned, actual = _build_full_june_2026(lambda _day: (8, None))
        assert compute_row_status(planned, actual, 2026, 6, False) == "a_saisir"

    def test_a_saisir_when_reel_zero_on_travail_day(self):
        planned, actual = _build_full_june_2026(lambda _day: (8, 0))
        assert compute_row_status(planned, actual, 2026, 6, False) == "a_saisir"

    def test_saisi_avec_ecart(self):
        planned = []
        actual = []
        for day in range(1, 31):
            from datetime import date

            dt = date(2026, 6, day)
            if dt.weekday() >= 5:
                planned.append({"jour": day, "type": "weekend", "heures_prevues": 0})
                actual.append({"jour": day, "type": "weekend", "heures_faites": 0})
                continue
            prev = 10 if day == 2 else 8
            fait = 28 if day == 2 else prev
            planned.append({"jour": day, "type": "travail", "heures_prevues": prev})
            actual.append({"jour": day, "type": "travail", "heures_faites": fait})
        assert compute_row_status(planned, actual, 2026, 6, False) == "saisi_avec_ecart"

    def test_forfait_ecart_jours(self):
        planned = []
        actual = []
        for day in range(1, 31):
            from datetime import date

            dt = date(2026, 6, day)
            if dt.weekday() >= 5:
                planned.append({"jour": day, "type": "weekend", "heures_prevues": 0})
                actual.append({"jour": day, "type": "weekend", "heures_faites": 0})
                continue
            planned.append({"jour": day, "type": "travail", "heures_prevues": 1})
            actual.append(
                {
                    "jour": day,
                    "type": "travail",
                    "heures_faites": 0 if day == 2 else 1,
                }
            )
        assert compute_row_status(planned, actual, 2026, 6, True) == "saisi_avec_ecart"


class TestAbsenceConflicts:
    def test_detect_conflict_when_travail_on_absence_day(self):
        planned = [_weekday_planned(10)]
        assert detect_absence_conflicts(planned, {10}) == 1
        assert detect_absence_conflict_days(planned, {10}) == [10]

    def test_no_conflict_when_conge(self):
        planned = [{"jour": 10, "type": "conge", "heures_prevues": 0}]
        assert detect_absence_conflicts(planned, {10}) == 0


class TestDayEcartsAndHeuresSup:
    def test_compute_day_ecarts(self):
        planned = [_weekday_planned(5, 8), _weekday_planned(6, 8)]
        actual = [_weekday_actual(5, 10), _weekday_actual(6, 8)]
        details = compute_day_ecarts(planned, actual, forfait=False)
        assert len(details) == 1
        assert details[0]["jour"] == 5
        assert details[0]["heures_sup"] is True

    def test_compute_heures_supplementaires(self):
        planned = [_weekday_planned(5, 8)]
        actual = [_weekday_actual(5, 10)]
        assert compute_heures_supplementaires(planned, actual) == 2.0
