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




def _creneau_journee():
    from app.modules.schedules.domain.punch_accounting_rules import slot_from_row

    return [slot_from_row({"id": "j", "code": "A", "entry_time": "08:00", "exit_time": "16:30",
                           "theoretical_gross_minutes": 510, "break_deduct_minutes": 45})]


def _une_journee(day: AiDayEntry) -> AiCalendarProposalResponse:
    return AiCalendarProposalResponse(
        year=2026, month=6, source="relevé",
        employees=[AiEmployeeProposal(raw_name="SALARIE", days=[day])],
    )


@patch("app.modules.schedules.application.punch_accounting_service.repo.list_slots")
@patch("app.modules.schedules.application.punch_accounting_service.repo.get_settings")
def test_entree_sans_sortie_reste_un_jour_vide_a_completer(mock_settings, mock_slots):
    """03/11 : plus d'« absence » à 0 h (retenue d'absence injustifiée si l'on
    forçait la paie) : le jour reste vide, avec l'alerte nommée."""
    mock_settings.return_value = PunchAccountingSettings(enabled=True, slot_detection="nearest_entry")
    mock_slots.return_value = _creneau_journee()

    result = apply_punch_accounting_to_proposal(
        _une_journee(AiDayEntry(jour=9, heures=0.0, punch_entry_raw="800", punch_exit_raw=None)),
        "co-1",
    )

    day = result.employees[0].days[0]
    assert day.heures is None
    assert day.type == "travail"
    assert any("Pointage incomplet" in w for w in result.employees[0].warnings)
    assert any(q.code == "punch_incomplete" for q in result.quality_checks)


@patch("app.modules.schedules.application.punch_accounting_service.repo.list_slots")
@patch("app.modules.schedules.application.punch_accounting_service.repo.get_settings")
def test_la_pause_pointee_va_jusqu_au_calcul(mock_settings, mock_slots):
    mock_settings.return_value = PunchAccountingSettings(enabled=True, slot_detection="nearest_entry")
    mock_slots.return_value = _creneau_journee()

    result = apply_punch_accounting_to_proposal(
        _une_journee(AiDayEntry(jour=9, heures=4.03, punch_entry_raw="800",
                                punch_exit_raw="1217", punch_break_minutes=15)),
        "co-1",
    )

    assert result.employees[0].days[0].heures == 4.03


@patch("app.modules.schedules.application.punch_accounting_service.repo.list_slots")
@patch("app.modules.schedules.application.punch_accounting_service.repo.get_settings")
def test_les_alertes_de_chaque_jour_restent_sur_le_salarie(mock_settings, mock_slots):
    mock_settings.return_value = PunchAccountingSettings(enabled=True, slot_detection="nearest_entry")
    mock_slots.return_value = _creneau_journee()
    proposal = AiCalendarProposalResponse(
        year=2026, month=6, source="relevé",
        employees=[AiEmployeeProposal(raw_name="SALARIE", days=[
            AiDayEntry(jour=8, heures=0.0, punch_entry_raw="800"),
            AiDayEntry(jour=9, heures=0.0, punch_entry_raw="800"),
            AiDayEntry(jour=10, heures=8.6, punch_entry_raw="720", punch_exit_raw="1630"),
        ])],
    )

    warnings = apply_punch_accounting_to_proposal(proposal, "co-1").employees[0].warnings

    assert any(w.startswith("Jour 8 :") for w in warnings)
    assert any(w.startswith("Jour 9 :") for w in warnings)
    assert any(w.startswith("Jour 10 :") for w in warnings)
