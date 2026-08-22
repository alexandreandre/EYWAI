"""Tests service comptabilisation pointages."""

from unittest.mock import patch

from app.modules.schedules.application.punch_accounting_service import (
    apply_punch_accounting_to_proposal,
)
from app.modules.schedules.domain.punch_accounting_entities import (
    PunchAccountingSettings,
    PunchShiftSlot,
)
from app.modules.schedules.schemas.ai import (
    AiCalendarProposalResponse,
    AiDayEntry,
    AiEmployeeProposal,
)


@patch("app.modules.schedules.application.punch_accounting_service.repo.list_slots")
@patch("app.modules.schedules.application.punch_accounting_service.repo.get_settings")
def test_proposal_deducts_break_without_shift_slots(mock_settings, mock_slots):
    """Horaires variables : aucun créneau, la pause vient du seuil de présence."""
    mock_settings.return_value = PunchAccountingSettings(
        enabled=True,
        default_break_deduct_minutes=30,
        break_threshold_minutes=360,
    )
    mock_slots.return_value = []

    proposal = AiCalendarProposalResponse(
        year=2026,
        month=6,
        source="relevé",
        employees=[
            AiEmployeeProposal(
                raw_name="HUGO",
                days=[
                    AiDayEntry(jour=1, punch_entry_raw="07:00", punch_exit_raw="16:00"),
                    AiDayEntry(jour=5, punch_entry_raw="08:00", punch_exit_raw="13:00"),
                    # Feuille papier : heures déjà calculées, aucun pointage brut.
                    AiDayEntry(jour=8, heures=8.5),
                ],
            )
        ],
    )

    result = apply_punch_accounting_to_proposal(proposal, "co-1")

    days = result.employees[0].days
    assert days[0].heures == 8.5
    # Demi-journée sous le seuil : aucune pause déduite.
    assert days[1].heures == 5.0
    # Journée sans pointage brut : la pause a déjà été déduite à l'extraction.
    assert days[2].heures == 8.5
    assert days[2].type == "travail"


@patch("app.modules.schedules.application.punch_accounting_service.repo.list_slots")
@patch("app.modules.schedules.application.punch_accounting_service.repo.get_settings")
def test_day_without_punch_data_is_not_turned_into_absence(mock_settings, mock_slots):
    """Sans grille horaire, une journée vide reste vide, pas une absence à 0 h."""
    mock_settings.return_value = PunchAccountingSettings(enabled=True)
    mock_slots.return_value = []

    proposal = AiCalendarProposalResponse(
        year=2026,
        month=6,
        source="relevé",
        employees=[AiEmployeeProposal(raw_name="HUGO", days=[AiDayEntry(jour=3)])],
    )

    day = apply_punch_accounting_to_proposal(proposal, "co-1").employees[0].days[0]

    assert day.heures is None
    assert day.type == "travail"


@patch("app.modules.schedules.application.punch_accounting_service.repo.list_slots")
@patch("app.modules.schedules.application.punch_accounting_service.repo.get_settings")
def test_fingerprint_follows_settings_and_slots(mock_settings, mock_slots):
    from app.modules.schedules.application.punch_accounting_service import (
        punch_calc_fingerprint,
    )

    mock_settings.return_value = PunchAccountingSettings(
        enabled=True, default_break_deduct_minutes=30, break_threshold_minutes=360
    )
    mock_slots.return_value = []
    reference = punch_calc_fingerprint("co-1")

    mock_settings.return_value = PunchAccountingSettings(
        enabled=True, default_break_deduct_minutes=45, break_threshold_minutes=360
    )
    assert punch_calc_fingerprint("co-1") != reference

    # Une grille horaire modifiée change aussi les heures produites.
    mock_settings.return_value = PunchAccountingSettings(
        enabled=True, default_break_deduct_minutes=30, break_threshold_minutes=360
    )
    assert punch_calc_fingerprint("co-1") == reference
    mock_slots.return_value = [PunchShiftSlot(code="A", break_deduct_minutes=45)]
    assert punch_calc_fingerprint("co-1") != reference


