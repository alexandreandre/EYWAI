"""Tests cache d'aperçu d'import : les règles de calcul font partie de la clé."""

from unittest.mock import patch

from app.modules.schedules.application.timesheet_import.cache_service import (
    find_cached_preview,
)

_PREVIEW = {
    "year": 2026,
    "month": 6,
    "source": "relevé",
    "employees": [],
    "calc_fingerprint": "v2:True|30|30|360|shift_code|True|True",
}


def _row(preview: dict) -> dict:
    return {"preview_json": preview}


@patch(
    "app.modules.schedules.application.timesheet_import.cache_service.punch_calc_fingerprint"
)
@patch(
    "app.modules.schedules.application.timesheet_import.cache_service"
    ".timesheet_import_repository.find_recent_preview_by_hash"
)
def test_cached_preview_served_under_same_rules(mock_find, mock_fingerprint):
    mock_find.return_value = _row(_PREVIEW)
    mock_fingerprint.return_value = _PREVIEW["calc_fingerprint"]

    preview = find_cached_preview("co-1", "hash", year=2026, month=6)

    assert preview is not None


@patch(
    "app.modules.schedules.application.timesheet_import.cache_service.punch_calc_fingerprint"
)
@patch(
    "app.modules.schedules.application.timesheet_import.cache_service"
    ".timesheet_import_repository.find_recent_preview_by_hash"
)
def test_cached_preview_dropped_when_rules_changed(mock_find, mock_fingerprint):
    mock_find.return_value = _row(_PREVIEW)
    mock_fingerprint.return_value = "v2:True|30|45|360|shift_code|True|True"

    assert find_cached_preview("co-1", "hash", year=2026, month=6) is None


@patch(
    "app.modules.schedules.application.timesheet_import.cache_service.punch_calc_fingerprint"
)
@patch(
    "app.modules.schedules.application.timesheet_import.cache_service"
    ".timesheet_import_repository.find_recent_preview_by_hash"
)
def test_preview_without_fingerprint_is_reextracted(mock_find, mock_fingerprint):
    """Aperçu produit avant la pose de l'empreinte : jamais resservi."""
    legacy = {k: v for k, v in _PREVIEW.items() if k != "calc_fingerprint"}
    mock_find.return_value = _row(legacy)
    mock_fingerprint.return_value = _PREVIEW["calc_fingerprint"]

    assert find_cached_preview("co-1", "hash", year=2026, month=6) is None
