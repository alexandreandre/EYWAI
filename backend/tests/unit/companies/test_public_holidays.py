"""
Tests unitaires — jours fériés légaux (domain/public_holidays.py).
"""

import pytest

from app.modules.companies.domain.public_holidays import (
    DEFAULT_OBSERVED_HOLIDAY_IDS,
    LABOR_DAY_HOLIDAY_ID,
    merge_public_holidays_settings,
    normalize_observed_holiday_ids,
    validate_observed_holiday_ids,
)


class TestNormalizeObservedHolidayIds:
    def test_default_when_none(self):
        assert normalize_observed_holiday_ids(None) == DEFAULT_OBSERVED_HOLIDAY_IDS

    def test_default_when_empty(self):
        assert normalize_observed_holiday_ids([]) == DEFAULT_OBSERVED_HOLIDAY_IDS

    def test_filters_unknown_ids(self):
        result = normalize_observed_holiday_ids(["whit_monday", "invalid_id"])
        assert result == ["labor_day", "whit_monday"]

    def test_always_includes_labor_day(self):
        result = normalize_observed_holiday_ids(["christmas"])
        assert LABOR_DAY_HOLIDAY_ID in result
        assert "christmas" in result


class TestValidateObservedHolidayIds:
    def test_rejects_unknown_id(self):
        with pytest.raises(ValueError, match="invalides"):
            validate_observed_holiday_ids(["not_a_holiday"])


class TestMergePublicHolidaysSettings:
    def test_merge_observed_ids(self):
        current = {"medical_follow_up_enabled": True}
        merged = merge_public_holidays_settings(
            current,
            {"observed_holiday_ids": ["whit_monday", "christmas"]},
        )
        assert merged["public_holidays"]["observed_holiday_ids"] == [
            "christmas",
            "labor_day",
            "whit_monday",
        ]
        assert merged["medical_follow_up_enabled"] is True

    def test_merge_none_delta_is_noop(self):
        current = {"medical_follow_up_enabled": False}
        merged = merge_public_holidays_settings(current, None)
        assert merged == current

    def test_merge_rejects_non_list(self):
        with pytest.raises(ValueError, match="liste"):
            merge_public_holidays_settings({}, {"observed_holiday_ids": "bad"})
