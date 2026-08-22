"""Lot 4 Task 5 : la pause réellement badgée prime sur le forfait.

Moteur activé, l'ancien chemin ne lisait que première entrée/dernière
sortie : la pause badgée était réintégrée en temps travaillé puis une
pause forfaitaire retirée — 2 h de pause réelle fabriquaient ~2 h de
fausses HS. La réalité badgée prime désormais sur toute estimation.
"""

from unittest.mock import MagicMock, patch

from app.modules.schedules.domain.punch_accounting_entities import (
    PlannedShiftBreak,
    PunchAccountingSettings,
    PunchDayInput,
)
from app.modules.schedules.domain.punch_accounting_rules import (
    compute_punch_day,
    resolve_break_minutes,
    slot_from_row,
)

_SLOT = slot_from_row(
    {
        "code": "M",
        "entry_time": "08:00",
        "exit_time": "16:00",
        "theoretical_gross_minutes": 480,
        "break_deduct_minutes": 45,
    }
)
_SETTINGS = PunchAccountingSettings(
    enabled=True,
    tolerance_minutes=10,
    default_break_deduct_minutes=45,
    require_manager_validation_for_overtime=False,
)


def test_la_pause_mesuree_prime_sur_creneau_et_forfait():
    assert (
        resolve_break_minutes(_SLOT, _SETTINGS, None, measured_break_minutes=120)
        == 120
    )
    planned = PlannedShiftBreak(unpaid_break_minutes=30)
    assert (
        resolve_break_minutes(_SLOT, _SETTINGS, planned, measured_break_minutes=120)
        == 120
    )


def test_sans_mesure_le_comportement_actuel_est_inchange():
    """Colorplast et MBC (feuilles importées, double run) ne bougent pas."""
    assert resolve_break_minutes(_SLOT, _SETTINGS, None) == 45
    planned = PlannedShiftBreak(unpaid_break_minutes=30)
    assert resolve_break_minutes(_SLOT, _SETTINGS, planned) == 30


def test_une_longue_pause_badgee_ne_fabrique_plus_d_hs():
    """08:00→19:00 avec 2 h de pause badgée = 9 h travaillées.
    Avant : pointé = 11 h − 45 min = 10,25 h → ~2 h de fausses HS."""
    jour = PunchDayInput(
        entry_minutes=480,
        exit_minutes=1140,
        shift_code="M",
        measured_break_minutes=120,
    )
    r = compute_punch_day(jour, _SETTINGS, [_SLOT])
    assert r.pointed_net_hours == 9.0
    assert r.theoretical_net_hours == 7.25  # 480 min brut − 45 min de pause créneau
    # Seul le VRAI excédent de travail : 9 − 7,25 − 10 min de tolérance.
    # Avant : late_exit comptait 3 h (la pause badgée passait pour des HS).
    assert r.overtime_hours == 1.58
    assert r.overtime_reason == "daily_excess"


def test_import_badgeuse_transmet_la_pause_mesuree():
    """La pause mesurée = amplitude − travail badgé, transmise au moteur."""
    from datetime import date

    from app.modules.schedules.application import badgeuse_import as mod

    dto = MagicMock()
    dto.has_override = False
    dto.effective_seconds = 9 * 3600      # 9 h badgées en séquences
    capture = {}

    def fake_compute(company_id, **kwargs):
        capture.update(kwargs)
        return 9.0, False, 0.0, None

    with (
        patch.object(mod, "_first_last_punch_minutes", return_value=(480, 1140)),
        patch(
            "app.modules.schedules.application.punch_accounting_service."
            "compute_accounted_hours_for_badgeuse_day",
            side_effect=fake_compute,
        ),
        patch(
            "app.modules.schedules.infrastructure.punch_accounting_repository."
            "get_settings",
            return_value=_SETTINGS,
        ),
    ):
        mod._accounted_hours_for_day(
            company_id="comp-1",
            employee_id="emp-1",
            day=date(2026, 7, 3),
            dto=dto,
            planned_entry=None,
        )
    # 11 h d'amplitude − 9 h badgées = 120 min de pause réelle
    assert capture.get("measured_break_minutes") == 120


def test_la_part_payee_de_la_pause_n_est_pas_deduite_de_la_mesure():
    """C5 — société à pauses payées (MBC : 2×10 min comprises dans les
    7 h 30) : 60 min badgées ne retirent que 60 − 20 = 40 min."""
    planned = PlannedShiftBreak(paid_break_minutes=20)
    assert (
        resolve_break_minutes(
            _SLOT, _SETTINGS, planned, measured_break_minutes=60
        )
        == 40
    )


def test_pause_mesuree_plus_courte_que_la_part_payee():
    planned = PlannedShiftBreak(paid_break_minutes=30)
    assert (
        resolve_break_minutes(
            _SLOT, _SETTINGS, planned, measured_break_minutes=20
        )
        == 0
    )


def test_bout_en_bout_la_part_payee_traverse_compute_punch_day():
    """Faux vert n°5 : le fix C5 vivait dans une branche que la prod
    n'appelait pas. Le VRAI chemin (compute_punch_day) doit déduire
    mesure − part payée, y compris quand la part payée vient du CRÉNEAU."""
    from app.modules.schedules.domain.punch_accounting_entities import PunchDayInput

    slot_paye = slot_from_row(
        {
            "code": "M",
            "entry_time": "08:00",
            "exit_time": "16:30",
            "theoretical_gross_minutes": 510,
            "break_deduct_minutes": 45,
            "paid_break_minutes": 20,
        }
    )
    jour = PunchDayInput(
        entry_minutes=480,
        exit_minutes=990,          # 08:00 → 16:30, amplitude 8,5 h
        shift_code="M",
        measured_break_minutes=60,  # 1 h badgée
    )
    r = compute_punch_day(jour, _SETTINGS, [slot_paye])
    # 510 min − (60 − 20 payées) = 470 min = 7,83 h
    assert r.pointed_net_hours == 7.83


def test_resolve_lit_la_part_payee_du_creneau_sans_planning():
    slot_paye = slot_from_row(
        {
            "code": "M",
            "entry_time": "08:00",
            "exit_time": "16:30",
            "theoretical_gross_minutes": 510,
            "break_deduct_minutes": 45,
            "paid_break_minutes": 20,
        }
    )
    assert (
        resolve_break_minutes(
            slot_paye, _SETTINGS, None, measured_break_minutes=60
        )
        == 40
    )


def test_import_badgeuse_transmet_la_part_payee_du_planning():
    from datetime import date

    from app.modules.schedules.application import badgeuse_import as mod

    dto = MagicMock()
    dto.has_override = False
    dto.effective_seconds = 8 * 3600
    capture = {}

    def fake_compute(company_id, **kwargs):
        capture.update(kwargs)
        return 8.0, False, 0.0, None

    with (
        patch.object(mod, "_first_last_punch_minutes", return_value=(480, 990)),
        patch(
            "app.modules.schedules.application.punch_accounting_service."
            "compute_accounted_hours_for_badgeuse_day",
            side_effect=fake_compute,
        ),
        patch(
            "app.modules.schedules.infrastructure.punch_accounting_repository."
            "get_settings",
            return_value=_SETTINGS,
        ),
    ):
        mod._accounted_hours_for_day(
            company_id="comp-1",
            employee_id="emp-1",
            day=date(2026, 7, 3),
            dto=dto,
            planned_entry={"jour": 3, "pause_min": 20, "pause_payee": True},
        )
    assert capture.get("planned_paid_break_minutes") == 20
