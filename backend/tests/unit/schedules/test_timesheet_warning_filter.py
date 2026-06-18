"""Tests filtre alertes import pointages."""

from app.modules.schedules.application.timesheet_warning_filter import (
    filter_timesheet_warnings,
    is_timesheet_noise_warning,
)


def test_filters_single_channel():
    assert is_timesheet_noise_warning("BOUSSANOUNE Rachid : single_channel_extraction (vision).")


def test_filters_llm_english_commentary():
    msg = (
        "For MOUSSAFIR Abdelkerim, the note 'erreur sur demande CP?' suggests "
        "a potential issue with the leave request."
    )
    assert is_timesheet_noise_warning(msg)


def test_filters_weekly_total_llm_noise():
    assert is_timesheet_noise_warning(
        "Le total hebdomadaire pour SAFI Karimullah est 23:42, ce qui est 23.7 heures. "
        "Il y a une légère différence."
    )


def test_keeps_actionable_french_warning():
    msg = "Période du relevé (mai) différente du mois sélectionné (juin)."
    assert not is_timesheet_noise_warning(msg)
    assert filter_timesheet_warnings([msg]) == [msg]
