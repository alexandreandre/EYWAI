"""Lot 4 Task 2 : « pause 0 » et « tolérance 0 » sont des valeurs légales.

Les `or 45` / `or 30` transformaient silencieusement 0 en défaut : une
société qui coche « aucune pause déduite » se voyait retirer 45 min, et
l'écran réaffichait 45 avec un toast « enregistré ».
"""


def test_reglages_societe_a_zero_sont_conserves():
    from app.modules.schedules.infrastructure.punch_accounting_repository import (
        _row_to_settings,
    )

    s = _row_to_settings(
        {
            "enabled": True,
            "tolerance_minutes": 0,
            "default_break_deduct_minutes": 0,
            "break_threshold_minutes": 0,
        }
    )
    assert s.tolerance_minutes == 0
    assert s.default_break_deduct_minutes == 0


def test_reglages_absents_gardent_les_defauts():
    from app.modules.schedules.infrastructure.punch_accounting_repository import (
        _row_to_settings,
    )

    s = _row_to_settings({"enabled": True})
    assert s.tolerance_minutes == 30
    assert s.default_break_deduct_minutes == 45


def test_la_reponse_api_ne_reecrit_pas_zero():
    from unittest.mock import patch

    from app.modules.schedules.application import punch_accounting_commands as cmds

    with patch.object(cmds, "repo") as fake_repo:
        fake_repo.get_settings_row.return_value = {
            "enabled": True,
            "tolerance_minutes": 0,
            "default_break_deduct_minutes": 0,
        }
        r = cmds._settings_response("comp-1")
    assert r.tolerance_minutes == 0
    assert r.default_break_deduct_minutes == 0


def test_un_creneau_a_pause_zero_est_respecte():
    from app.modules.schedules.domain.punch_accounting_rules import slot_from_row

    slot = slot_from_row(
        {
            "code": "M",
            "entry_time": "08:00",
            "exit_time": "16:00",
            "theoretical_gross_minutes": 465,
            "break_deduct_minutes": 0,
        }
    )
    assert slot.break_deduct_minutes == 0


def test_un_creneau_sans_pause_renseignee_garde_le_defaut():
    from app.modules.schedules.domain.punch_accounting_rules import slot_from_row

    slot = slot_from_row(
        {"code": "M", "entry_time": "08:00", "exit_time": "16:00"}
    )
    assert slot.break_deduct_minutes == 45
    assert slot.theoretical_gross_minutes == 465
