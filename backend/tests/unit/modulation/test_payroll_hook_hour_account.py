"""Tests hook paie compte d'heures modulation."""

from unittest.mock import patch

from app.modules.modulation.application.payroll_hook import (
    apply_modulation_hour_account_to_calendar,
)
from app.modules.modulation.domain.entities import ModulationSettings


def _hs_calendar(*hours: float) -> list[dict]:
    return [{"type": "travail_hs25", "heures": h} for h in hours]


@patch("app.modules.modulation.application.payroll_hook.sync_employee_modulation_counter")
@patch("app.modules.modulation.application.payroll_hook.sync_account_balance_cache")
@patch("app.modules.modulation.application.payroll_hook.repo.insert_movement")
@patch("app.modules.modulation.application.payroll_hook._decision_du_mois", return_value=None)
@patch("app.modules.modulation.application.payroll_hook.repo.list_movements_for_employee")
@patch("app.modules.modulation.application.payroll_hook.repo.get_modulation_settings")
def test_apply_hour_account_franchise_14_of_20(
    mock_settings,
    mock_movements,
    mock_consumed,
    mock_insert,
    _mock_sync_cache,
    _mock_sync_counter,
):
    mock_settings.return_value = ModulationSettings(
        hour_account_enabled=True,
        hs_franchise_hours_per_period=14,
    )
    mock_movements.return_value = []
    mock_consumed.return_value = None
    mock_insert.return_value = {"id": "mov-1"}

    calendar = _hs_calendar(12, 8)
    updated, movement_ids, result = apply_modulation_hour_account_to_calendar(
        "company-1",
        "emp-1",
        2026,
        3,
        calendar,
    )

    assert result.hs_realisees == 20.0
    assert result.hs_credited == 14.0
    assert result.hs_paid == 6.0
    assert movement_ids == ["mov-1"]
    mock_insert.assert_called_once()
    paid_hs = sum(
        float(j.get("heures") or 0)
        for j in updated
        if j.get("type") in ("travail_hs25", "travail_hs50")
    )
    assert paid_hs == 6.0


@patch("app.modules.modulation.application.payroll_hook.repo.get_modulation_settings")
def test_apply_hour_account_disabled_returns_unchanged(mock_settings):
    mock_settings.return_value = ModulationSettings(hour_account_enabled=False)
    calendar = _hs_calendar(10)

    updated, movement_ids, result = apply_modulation_hour_account_to_calendar(
        "company-1",
        "emp-1",
        2026,
        3,
        calendar,
    )

    assert updated == calendar
    assert movement_ids == []
    assert result.hs_credited == 0.0


@patch("app.modules.modulation.application.payroll_hook.sync_employee_modulation_counter")
@patch("app.modules.modulation.application.payroll_hook.sync_account_balance_cache")
@patch("app.modules.modulation.application.payroll_hook.repo.insert_movement")
@patch("app.modules.modulation.application.payroll_hook._decision_du_mois")
@patch("app.modules.modulation.application.payroll_hook.repo.list_movements_for_employee")
@patch("app.modules.modulation.application.payroll_hook.repo.get_modulation_settings")
def test_tout_au_compteur_sauf_si_la_rh_paie_ce_mois(
    mock_settings, mock_movements, mock_decision, mock_insert, _cache, _counter
):
    """Spec 2026-11-05 § 3.2-3.3 : 4 h sup à 25 % → 5 h de repos ; la
    décision du mois les laisse payées."""
    mock_settings.return_value = ModulationSettings(
        hour_account_enabled=True, hs_routing_policy="account_all"
    )
    mock_movements.return_value = []
    mock_insert.return_value = {"id": "mov-1"}

    mock_decision.return_value = None
    _, _, result = apply_modulation_hour_account_to_calendar(
        "company-1", "emp-1", 2026, 10, _hs_calendar(4),
        majorations={"travail_hs25": 0.25},
    )
    assert (result.hs_credited, result.repos_credite, result.paye_ce_mois) == (4.0, 5.0, False)
    assert mock_insert.call_args[0][0]["hours"] == 5.0

    mock_insert.reset_mock()
    mock_decision.return_value = {"hours_to_account": 0, "status": "applied_payroll"}
    updated, ids, result = apply_modulation_hour_account_to_calendar(
        "company-1", "emp-1", 2026, 10, _hs_calendar(4),
    )
    assert (result.hs_credited, result.hs_paid, result.paye_ce_mois) == (0.0, 4.0, True)
    assert ids == []
    mock_insert.assert_not_called()
    assert sum(j["heures"] for j in updated) == 4


@patch("app.modules.modulation.application.payroll_hook._decision_du_mois", return_value=None)
@patch("app.modules.modulation.application.payroll_hook.repo.list_movements_for_employee")
@patch("app.modules.modulation.application.payroll_hook.repo.get_modulation_settings")
def test_tout_au_compteur_respecte_le_plafond(mock_settings, mock_movements, _decision):
    mock_settings.return_value = ModulationSettings(
        hour_account_enabled=True,
        hs_routing_policy="account_all",
        max_account_balance_hours=10.0,
    )
    mock_movements.return_value = [
        {"movement_type": "opening_balance", "hours": 9.0, "year": 2026, "month": 9,
         "status": "validated", "source": "manual_rh"},
    ]
    _, _, result = apply_modulation_hour_account_to_calendar(
        "company-1", "emp-1", 2026, 10, _hs_calendar(4), persister=False,
        majorations={"travail_hs25": 0.25},
    )
    assert result.repos_credite == 1.0
    assert result.hs_credited == 0.8
    assert result.hs_paid == 3.2


@patch("app.modules.modulation.application.payroll_hook._decision_du_mois", return_value=None)
@patch("app.modules.modulation.application.payroll_hook.repo.list_movements_for_employee", return_value=[])
@patch("app.modules.modulation.application.payroll_hook.repo.get_modulation_settings")
def test_les_heures_declarees_vont_au_compteur_une_seule_fois(mock_settings, _mv, _dec):
    """8 h saisies à la main, 2 h au planning : 8 h au compteur, plus rien à
    payer, et la déclaration restante revient à 0 pour le moteur."""
    from datetime import date

    mock_settings.return_value = ModulationSettings(
        hour_account_enabled=True, hs_routing_policy="account_all"
    )
    fenetre = (date(2026, 10, 1), date(2026, 10, 31))
    cal = [{"type": "travail_hs25", "heures": 2.0, "date_complete": "2026-10-05"}]
    updated, _, result = apply_modulation_hour_account_to_calendar(
        "c", "e", 2026, 10, cal, persister=False, bornes_variables=fenetre,
        majorations={"travail_hs25": 0.25}, heures_declarees=(8.0, 0.0),
    )
    assert result.repos_credite == 10.0
    assert result.declaration_restante == (0.0, 0.0)
    assert [e for e in updated if e["type"].startswith("travail_hs")] == []


@patch("app.modules.modulation.application.payroll_hook._decision_du_mois", return_value=None)
@patch("app.modules.modulation.application.payroll_hook.repo.list_movements_for_employee", return_value=[])
@patch("app.modules.modulation.application.payroll_hook.repo.get_modulation_settings")
def test_sans_compteur_la_declaration_ne_bouge_pas(mock_settings, _mv, _dec):
    mock_settings.return_value = ModulationSettings()
    cal = [{"type": "travail_hs25", "heures": 2.0, "date_complete": "2026-10-05"}]
    updated, _, result = apply_modulation_hour_account_to_calendar(
        "c", "e", 2026, 10, cal, heures_declarees=(8.0, 0.0),
    )
    assert updated == cal
    assert result.declaration_restante is None


@patch("app.modules.modulation.application.payroll_hook.repo.list_movements_for_employee")
@patch("app.modules.modulation.application.payroll_hook.repo.get_modulation_settings")
def test_societe_repassee_en_paye_le_solde_reste_visible(mock_settings, mock_mv):
    from app.modules.modulation.application.payroll_hook import etat_recuperation_du_bulletin

    mock_settings.return_value = ModulationSettings(
        hour_account_enabled=True, hs_routing_policy="pay_all"
    )
    mock_mv.return_value = [
        {"movement_type": "opening_balance", "hours": 20.0, "year": 2026, "month": 9,
         "status": "validated", "source": "manual_rh"},
    ]
    assert etat_recuperation_du_bulletin("c", "e", 2026, 10)["solde"] == 20.0
    mock_mv.return_value = []
    assert etat_recuperation_du_bulletin("c", "e", 2026, 10) is None
    mock_settings.return_value = ModulationSettings()
    mock_mv.return_value = [{"movement_type": "opening_balance", "hours": 20.0, "year": 2026, "month": 9, "status": "validated"}]
    assert etat_recuperation_du_bulletin("c", "e", 2026, 10) is None


@patch("app.modules.modulation.application.payroll_hook._decision_du_mois")
@patch("app.modules.modulation.application.payroll_hook.repo.list_movements_for_employee", return_value=[])
@patch("app.modules.modulation.application.payroll_hook.repo.get_modulation_settings")
def test_une_decision_partielle_n_est_pas_un_mois_paye(mock_settings, _mv, mock_dec):
    mock_settings.return_value = ModulationSettings(
        hour_account_enabled=True, hs_routing_policy="manual"
    )
    mock_dec.return_value = {"hours_to_account": 2, "status": "validated"}
    _, _, result = apply_modulation_hour_account_to_calendar(
        "c", "e", 2026, 10, _hs_calendar(4), persister=False,
    )
    assert result.hs_credited == 2.0
    assert result.paye_ce_mois is False
    assert result.regle == "manual"


@patch("app.modules.modulation.application.payroll_hook.sync_employee_modulation_counter")
@patch("app.modules.modulation.application.payroll_hook.sync_account_balance_cache")
@patch("app.modules.modulation.application.payroll_hook.repo.insert_movement", return_value={"id": "m"})
@patch("app.modules.modulation.application.payroll_hook._decision_du_mois")
@patch("app.modules.modulation.application.payroll_hook.repo.list_movements_for_employee", return_value=[])
@patch("app.modules.modulation.application.payroll_hook.repo.get_modulation_settings")
def test_societe_qui_paie_le_mois_au_compteur_se_choisit(
    mock_settings, _mv, mock_dec, mock_insert, _c, _s
):
    """Comitech, Mont-Blanc, Cartol : tout est payé, sauf le mois qu'on met au
    compteur pour un salarié ; sans décision, le calendrier n'est pas touché."""
    mock_settings.return_value = ModulationSettings(
        hour_account_enabled=True, hs_routing_policy="pay_all"
    )
    cal = _hs_calendar(4)
    mock_dec.return_value = None
    updated, ids, result = apply_modulation_hour_account_to_calendar(
        "c", "e", 2026, 10, cal, heures_declarees=(6.0, 0.0),
    )
    assert updated == cal
    assert ids == []
    assert (result.hs_realisees, result.hs_paid, result.regle) == (6.0, 6.0, "pay_all")
    assert result.declaration_restante is None
    mock_insert.assert_not_called()

    mock_dec.return_value = {"hours_to_account": 4, "status": "validated"}
    updated, ids, result = apply_modulation_hour_account_to_calendar(
        "c", "e", 2026, 10, cal, majorations={"travail_hs25": 0.25},
    )
    assert updated == []
    assert result.repos_credite == 5.0
    assert result.au_compteur_ce_mois is True
