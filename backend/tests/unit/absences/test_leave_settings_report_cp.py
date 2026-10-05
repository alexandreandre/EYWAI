"""Activer le report des CP (`cp_carryover_enabled`) après une reprise.

Le report change la période sur laquelle s'imputent les congés pris : le N-1
d'abord, comme le fait l'ancien logiciel et comme le veut la règle. Les
compteurs repris d'un bulletin sont stockés en écart par rapport au calcul
théorique à leur date de référence ; ce théorique change avec le report dès
qu'un congé a été pris dans la période en cours avant la reprise. L'écart doit
donc être réexprimé : le solde repris ne bouge pas, seuls les congés posés
ensuite sortent du N-1 en premier.
"""

from datetime import date, timedelta
from unittest.mock import MagicMock, patch

import pytest

from app.modules.absences.application.leave_settings_commands import (
    rebaser_reprises_cp,
    update_leave_settings,
)
from app.modules.absences.domain.leave_policy import (
    EmployeeLeaveAdjustment,
    LeavePolicySettings,
)
from app.modules.absences.domain.rules import compute_cp_period_balances
from app.modules.absences.schemas.leave_settings import LeaveSettingsUpdate

pytestmark = pytest.mark.unit

_CMD = "app.modules.absences.application.leave_settings_commands"
_QUERIES = "app.modules.absences.infrastructure.queries"

SANS_REPORT = LeavePolicySettings(cp_counting_unit="ouvre", cp_acquisition_days_per_month=2.083)
AVEC_REPORT = LeavePolicySettings(
    cp_counting_unit="ouvre", cp_acquisition_days_per_month=2.083, cp_carryover_enabled=True
)
REPRISE = date(2026, 8, 31)


def _jours_ouvres(debut: date, nombre: int) -> list[str]:
    jours: list[str] = []
    jour = debut
    while len(jours) < nombre:
        if jour.weekday() < 5:
            jours.append(jour.isoformat())
        jour += timedelta(days=1)
    return jours


def _conges(debut: date, nombre: int) -> dict:
    return {
        "type": "conge_paye",
        "status": "validated",
        "selected_days": _jours_ouvres(debut, nombre),
    }


def _reglages_actuels() -> MagicMock:
    reglages = MagicMock()
    reglages.model_dump.return_value = {
        "cp_acquisition_days_per_month": 2.083,
        "cp_counting_unit": "ouvre",
        "cp_reference_period_start_month": 6,
        "cp_carryover_enabled": False,
        "cp_carryover_max_days": None,
        "rtt_annual_days": None,
        "rtt_use_calendar_formula": False,
        "rtt_use_forfait_jours_formula": False,
        "rtt_forfait_annual_days": 216,
        "rtt_forfait_cp_ouvres_deduction": 25.0,
        "rtt_forfait_cadres_only": True,
        "rtt_period_start_month": 1,
        "rtt_period_end_month": 12,
        "rtt_carryover_enabled": False,
        "rtt_year_end_reminder_enabled": False,
        "rtt_year_end_reminder_days_before": 15,
    }
    return reglages


class TestActiverLeReport:
    @patch(f"{_CMD}.rebaser_reprises_cp")
    @patch(f"{_CMD}.upsert_leave_policy")
    @patch(f"{_CMD}.get_leave_policy")
    @patch(f"{_CMD}.get_leave_settings")
    def test_activer_le_report_reexprime_les_reprises(
        self, get_settings, get_policy, upsert, rebase
    ):
        get_settings.return_value = _reglages_actuels()
        get_policy.side_effect = [SANS_REPORT, AVEC_REPORT]

        update_leave_settings("co-1", LeaveSettingsUpdate(cp_carryover_enabled=True))

        assert upsert.call_args.args[1]["cp_carryover_enabled"] is True
        rebase.assert_called_once_with("co-1", SANS_REPORT, AVEC_REPORT)


class TestRebaserReprisesAuReport:
    """Reprise au 31/08/2026, sous l'ancien réglage (congés imputés sur N)."""

    def _ligne(self, n1: float, n: float) -> dict:
        return {
            "employee_id": "salarie",
            "year": 2026,
            "cp_n1_opening_balance": n1,
            "cp_n_opening_balance": n,
            "cp_opening_reference_date": REPRISE.isoformat(),
            "note": "Reprise Quadra : bulletin de 08/2026",
        }

    @pytest.mark.parametrize(
        ("embauche", "pris_en_aout", "ecarts", "repris"),
        [
            # Ancien : 10 jours d'août au-delà des 6,24 acquis sur N. Théorique
            # sans report : N-1 25, N −3,76. Repris : N-1 13, N 6,24.
            (date(2014, 5, 5), 10, (-12.0, 10.0), (13.0, 6.24)),
            # Embauché en mars : 8 jours d'août pour 7 acquis sur N-1.
            # Théorique sans report : N-1 7, N −1,76. Repris : N-1 0, N 5,24.
            (date(2026, 3, 2), 8, (-7.0, 7.0), (0.0, 5.24)),
        ],
    )
    @patch(f"{_CMD}.upsert_employee_adjustment")
    @patch(f"{_CMD}.absence_repository")
    @patch(f"{_QUERIES}.get_employee_hire_date")
    @patch(f"{_CMD}.list_company_adjustments_avec_reference")
    def test_le_solde_repris_ne_bouge_pas(
        self, lister, hire, repo, upsert, embauche, pris_en_aout, ecarts, repris
    ):
        conges = [_conges(date(2026, 8, 10), pris_en_aout)]
        lister.return_value = [self._ligne(*ecarts)]
        hire.return_value = embauche.isoformat()
        repo.list_validated_for_employees.return_value = conges

        def soldes(policy, ajustement, au=REPRISE, pris=conges):
            calcul = compute_cp_period_balances(
                embauche, pris, au, policy=policy, adjustment=ajustement
            )
            return calcul["n1_remaining"], calcul["n_remaining_brut"]

        avant = EmployeeLeaveAdjustment(
            cp_n1_opening_balance=ecarts[0],
            cp_n_opening_balance=ecarts[1],
            cp_opening_reference_date=REPRISE,
        )
        assert soldes(SANS_REPORT, avant) == repris

        rebaser_reprises_cp("co-1", SANS_REPORT, AVEC_REPORT)

        # Sans réécriture, ce sont les écarts d'avant qui valent.
        payload = (
            upsert.call_args.args[3]
            if upsert.called
            else {"cp_n1_opening_balance": ecarts[0], "cp_n_opening_balance": ecarts[1]}
        )
        apres = EmployeeLeaveAdjustment(
            cp_n1_opening_balance=payload["cp_n1_opening_balance"],
            cp_n_opening_balance=payload["cp_n_opening_balance"],
            cp_opening_reference_date=REPRISE,
        )
        assert soldes(AVEC_REPORT, apres) == repris

        # Trois jours posés en septembre sortent du N-1 tant qu'il en reste.
        septembre = conges + [_conges(date(2026, 9, 14), 3)]
        n1_fin_septembre, n_fin_septembre = soldes(
            AVEC_REPORT, apres, au=date(2026, 9, 30), pris=septembre
        )
        n1_sans, n_sans = soldes(AVEC_REPORT, apres, au=date(2026, 9, 30))
        sur_n1 = min(3.0, repris[0])
        assert n1_fin_septembre == round(n1_sans - sur_n1, 2)
        assert n_fin_septembre == round(n_sans - (3.0 - sur_n1), 2)

    @patch(f"{_CMD}.upsert_employee_adjustment")
    @patch(f"{_CMD}.absence_repository")
    @patch(f"{_QUERIES}.get_employee_hire_date")
    @patch(f"{_CMD}.list_company_adjustments_avec_reference")
    def test_un_solde_que_le_report_ne_change_pas_n_est_pas_reecrit(
        self, lister, hire, repo, upsert
    ):
        # Aucun congé pris depuis le 1er juin : le report ne change rien au
        # 31/08. L'écart N-1 (−26 pour 25 acquis, N-1 repris à 0) reste tel
        # quel, même si −25 donnerait le même solde.
        lister.return_value = [self._ligne(-26.0, -8.0)]
        hire.return_value = "2019-09-01"
        repo.list_validated_for_employees.return_value = []

        assert rebaser_reprises_cp("co-1", SANS_REPORT, AVEC_REPORT) == 0
        upsert.assert_not_called()
