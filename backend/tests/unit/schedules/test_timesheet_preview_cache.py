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


@patch(
    "app.modules.schedules.application.timesheet_import.cache_service.punch_calc_fingerprint"
)
@patch(
    "app.modules.schedules.application.timesheet_import.cache_service"
    ".timesheet_import_repository.find_recent_preview_by_hash"
)
def test_un_apercu_ancre_sur_une_autre_semaine_n_est_pas_resservi(mock_find, mock_fingerprint):
    """Colorplast 19/09 : `semaine-26.pdf` importé une première fois ancré S27 par
    erreur ; réimporté ancré S26, le cache aurait resservi les jours de S27."""
    from datetime import date

    mock_find.return_value = _row({**_PREVIEW, "week_anchor_date": "2026-06-29"})
    mock_fingerprint.return_value = _PREVIEW["calc_fingerprint"]

    assert find_cached_preview("co-1", "hash", year=2026, month=6, week_anchor_date=date(2026, 6, 22)) is None
    assert find_cached_preview("co-1", "hash", year=2026, month=6, week_anchor_date=date(2026, 6, 29)) is not None
    # Sans ancrage demandé, un aperçu ancré ne convient pas non plus.
    assert find_cached_preview("co-1", "hash", year=2026, month=6) is None


# --- Tournage C1 (18/10/2026) : un salarié supprimé puis recréé ---------------
#
# L'aperçu en cache garde les identifiants des salariés reconnus. Un salarié
# supprimé (puis recréé sous un autre identifiant) faisait échouer le même
# fichier en 422 à l'enregistrement (`schedule_import_items_employee_id_fkey`).

_AVEC_SALARIES = {
    **_PREVIEW,
    "employees": [
        {"raw_name": "MARTIN Léa", "employee_id": "e-garde"},
        {"raw_name": "DUPONT Jean", "employee_id": "e-supprime"},
        {"raw_name": "INCONNU", "employee_id": None},
    ],
}


@patch(
    "app.modules.schedules.application.timesheet_import.cache_service"
    ".timesheet_import_repository.ids_de_salaries_existants"
)
@patch(
    "app.modules.schedules.application.timesheet_import.cache_service.punch_calc_fingerprint"
)
@patch(
    "app.modules.schedules.application.timesheet_import.cache_service"
    ".timesheet_import_repository.find_recent_preview_by_hash"
)
def test_un_apercu_qui_nomme_un_salarie_supprime_n_est_pas_resservi(mock_find, mock_fingerprint, mock_existants):
    mock_find.return_value = _row(_AVEC_SALARIES)
    mock_fingerprint.return_value = _PREVIEW["calc_fingerprint"]
    mock_existants.return_value = {"e-garde"}

    assert find_cached_preview("co-1", "hash", year=2026, month=6) is None
    mock_existants.assert_called_once_with("co-1", {"e-garde", "e-supprime"})


@patch(
    "app.modules.schedules.application.timesheet_import.cache_service"
    ".timesheet_import_repository.ids_de_salaries_existants"
)
@patch(
    "app.modules.schedules.application.timesheet_import.cache_service.punch_calc_fingerprint"
)
@patch(
    "app.modules.schedules.application.timesheet_import.cache_service"
    ".timesheet_import_repository.find_recent_preview_by_hash"
)
def test_un_apercu_dont_tous_les_salaries_existent_est_resservi(mock_find, mock_fingerprint, mock_existants):
    mock_find.return_value = _row(_AVEC_SALARIES)
    mock_fingerprint.return_value = _PREVIEW["calc_fingerprint"]
    mock_existants.return_value = {"e-garde", "e-supprime"}

    assert find_cached_preview("co-1", "hash", year=2026, month=6) is not None
