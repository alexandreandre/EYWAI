"""Compte d'heures modulation en bac à sable : même calcul, aucune écriture.

Une génération sans persistance doit router les heures sup exactement comme
une vraie (franchise créditée, reste payé, calendrier réduit) mais ne créer
aucun mouvement ni synchroniser aucun compteur : le rejeu d'audit ne laisse
pas de trace dans le compte du salarié.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from app.modules.modulation.application.payroll_hook import (
    apply_modulation_hour_account_to_calendar,
)
from app.modules.modulation.domain.entities import ModulationSettings

pytestmark = pytest.mark.unit

_HOOK = "app.modules.modulation.application.payroll_hook"


@patch(f"{_HOOK}.sync_employee_modulation_counter")
@patch(f"{_HOOK}.sync_account_balance_cache")
@patch(f"{_HOOK}.repo.insert_movement")
@patch(f"{_HOOK}.repo.get_franchise_consumed_in_period", return_value=0.0)
@patch(f"{_HOOK}.repo.list_movements_for_employee_year", return_value=[])
@patch(f"{_HOOK}.repo.get_modulation_settings")
def test_sans_persister_le_routage_est_calcule_mais_rien_n_est_ecrit(
    mock_settings, _movements, _consumed, mock_insert, mock_sync_cache, mock_sync_counter
):
    mock_settings.return_value = ModulationSettings(
        hour_account_enabled=True, hs_franchise_hours_per_period=14
    )
    calendrier = [{"type": "travail_hs25", "heures": 12}, {"type": "travail_hs25", "heures": 8}]

    updated, movement_ids, result = apply_modulation_hour_account_to_calendar(
        "company-1", "emp-1", 2026, 3, calendrier, persister=False
    )

    assert (result.hs_realisees, result.hs_credited, result.hs_paid) == (20.0, 14.0, 6.0)
    assert sum(float(j["heures"]) for j in updated if j["type"] == "travail_hs25") == 6.0
    assert movement_ids == []
    mock_insert.assert_not_called()
    mock_sync_cache.assert_not_called()
    mock_sync_counter.assert_not_called()
