"""Bascule de l'unité de décompte des CP (ouvrables ↔ ouvrés).

Deux garanties :
- changer d'unité sans donner de taux prend le taux légal de l'unité
  (2,5 en ouvrables, 2,083 en ouvrés) ;
- les compteurs repris d'un bulletin sont stockés en écart par rapport au
  calcul théorique à leur date de référence ; ce théorique change avec
  l'unité, l'écart est donc réexprimé pour que le solde repris ne bouge pas.
"""

from datetime import date, timedelta
from unittest.mock import MagicMock, patch

import pytest

from app.modules.absences.application.leave_settings_commands import (
    rebaser_reprises_cp,
    update_leave_settings,
)
from app.modules.absences.domain.leave_policy import LeavePolicySettings
from app.modules.absences.schemas.leave_settings import LeaveSettingsUpdate

pytestmark = pytest.mark.unit

_CMD = "app.modules.absences.application.leave_settings_commands"
_QUERIES = "app.modules.absences.infrastructure.queries"

OUVRABLE = LeavePolicySettings(cp_counting_unit="ouvrable", cp_acquisition_days_per_month=2.5)
OUVRE = LeavePolicySettings(cp_counting_unit="ouvre", cp_acquisition_days_per_month=2.083)


def _jours_ouvres(debut: date, nombre: int) -> list[str]:
    jours: list[str] = []
    jour = debut
    while len(jours) < nombre:
        if jour.weekday() < 5:
            jours.append(jour.isoformat())
        jour += timedelta(days=1)
    return jours


def _reglages_actuels(**surcharges) -> MagicMock:
    valeurs = {
        "cp_acquisition_days_per_month": 2.5,
        "cp_counting_unit": "ouvrable",
        "cp_reference_period_start_month": 6,
        "cp_carryover_enabled": False,
        "cp_carryover_max_days": None,
        "rtt_annual_days": None,
        "rtt_use_calendar_formula": False,
        "rtt_use_forfait_jours_formula": False,
        "rtt_forfait_annual_days": 214,
        "rtt_forfait_cp_ouvres_deduction": 25.0,
        "rtt_forfait_cadres_only": True,
        "rtt_period_start_month": 1,
        "rtt_period_end_month": 12,
        "rtt_carryover_enabled": False,
        "rtt_year_end_reminder_enabled": False,
        "rtt_year_end_reminder_days_before": 15,
    }
    valeurs.update(surcharges)
    reglages = MagicMock()
    reglages.model_dump.return_value = valeurs
    return reglages


class TestUpdateLeaveSettingsUnite:
    @patch(f"{_CMD}.rebaser_reprises_cp")
    @patch(f"{_CMD}.upsert_leave_policy")
    @patch(f"{_CMD}.get_leave_policy")
    @patch(f"{_CMD}.get_leave_settings")
    def test_passer_en_ouvres_prend_le_taux_legal_et_recale(
        self, get_settings, get_policy, upsert, rebase
    ):
        get_settings.return_value = _reglages_actuels()
        get_policy.side_effect = [OUVRABLE, OUVRE]

        update_leave_settings("co-1", LeaveSettingsUpdate(cp_counting_unit="ouvre"))

        payload = upsert.call_args.args[1]
        assert payload["cp_counting_unit"] == "ouvre"
        assert payload["cp_acquisition_days_per_month"] == 2.083
        rebase.assert_called_once_with("co-1", OUVRABLE, OUVRE)

    @patch(f"{_CMD}.rebaser_reprises_cp")
    @patch(f"{_CMD}.upsert_leave_policy")
    @patch(f"{_CMD}.get_leave_policy")
    @patch(f"{_CMD}.get_leave_settings")
    def test_l_ecran_renvoie_l_ancien_taux_legal_avec_la_nouvelle_unite(
        self, get_settings, get_policy, upsert, rebase
    ):
        # La carte Congés & RTT envoie toujours le taux affiché : 2,5 avec
        # « ouvré » voudrait dire 30 jours par an, on prend 2,083.
        get_settings.return_value = _reglages_actuels()
        get_policy.side_effect = [OUVRABLE, OUVRE]

        update_leave_settings(
            "co-1",
            LeaveSettingsUpdate(cp_counting_unit="ouvre", cp_acquisition_days_per_month=2.5),
        )

        assert upsert.call_args.args[1]["cp_acquisition_days_per_month"] == 2.083
        rebase.assert_called_once()

    @patch(f"{_CMD}.rebaser_reprises_cp")
    @patch(f"{_CMD}.upsert_leave_policy")
    @patch(f"{_CMD}.get_leave_policy")
    @patch(f"{_CMD}.get_leave_settings")
    def test_un_taux_vraiment_specifique_est_conserve(
        self, get_settings, get_policy, upsert, rebase
    ):
        get_settings.return_value = _reglages_actuels()
        specifique = LeavePolicySettings(
            cp_counting_unit="ouvre", cp_acquisition_days_per_month=2.25
        )
        get_policy.side_effect = [OUVRABLE, specifique]

        update_leave_settings(
            "co-1",
            LeaveSettingsUpdate(cp_counting_unit="ouvre", cp_acquisition_days_per_month=2.25),
        )

        assert upsert.call_args.args[1]["cp_acquisition_days_per_month"] == 2.25
        rebase.assert_called_once()

    @patch(f"{_CMD}.rebaser_reprises_cp")
    @patch(f"{_CMD}.upsert_leave_policy")
    @patch(f"{_CMD}.get_leave_policy")
    @patch(f"{_CMD}.get_leave_settings")
    def test_retour_en_ouvrables_reprend_2_5(self, get_settings, get_policy, upsert, rebase):
        get_settings.return_value = _reglages_actuels(
            cp_counting_unit="ouvre", cp_acquisition_days_per_month=2.083
        )
        get_policy.side_effect = [OUVRE, OUVRABLE]

        update_leave_settings(
            "co-1",
            LeaveSettingsUpdate(
                cp_counting_unit="ouvrable", cp_acquisition_days_per_month=2.083
            ),
        )

        assert upsert.call_args.args[1]["cp_acquisition_days_per_month"] == 2.5

    @patch(f"{_CMD}.rebaser_reprises_cp")
    @patch(f"{_CMD}.upsert_leave_policy")
    @patch(f"{_CMD}.get_leave_policy")
    @patch(f"{_CMD}.get_leave_settings")
    def test_sans_changement_d_acquisition_pas_de_recalage(
        self, get_settings, get_policy, upsert, rebase
    ):
        get_settings.return_value = _reglages_actuels()
        get_policy.side_effect = [OUVRABLE, OUVRABLE]

        update_leave_settings("co-1", LeaveSettingsUpdate(rtt_annual_days=10))

        rebase.assert_not_called()


class TestRebaserReprisesCp:
    """Girerd (Colorplast) : reprise à fin août 2026 — N-1 = 12, N = 6,24."""

    def _ligne_girerd(self):
        # Écarts posés sous 2,5 ouvrables : N-1 = 12 − (30 − 15) ; N = 6,24 − 8.
        return {
            "employee_id": "girerd",
            "year": 2026,
            "cp_n1_opening_balance": "-3.00",
            "cp_n_opening_balance": "-1.76",
            "cp_opening_reference_date": "2026-08-31",
            "note": "Import CP bulletin Août 2026",
        }

    @patch(f"{_CMD}.upsert_employee_adjustment")
    @patch(f"{_CMD}.absence_repository")
    @patch(f"{_QUERIES}.get_employee_hire_date")
    @patch(f"{_CMD}.list_company_adjustments_avec_reference")
    def test_le_solde_repris_ne_bouge_pas(self, lister, hire, repo, upsert):
        lister.return_value = [self._ligne_girerd()]
        hire.return_value = "2014-09-01"
        repo.list_validated_for_employees.return_value = [
            {
                "type": "conge_paye",
                "selected_days": _jours_ouvres(date(2025, 7, 7), 15),
            }
        ]

        n = rebaser_reprises_cp("co-1", OUVRABLE, OUVRE)

        assert n == 1
        payload = upsert.call_args.args[3]
        # Sous 2,083 ouvrés : N-1 = 25 − 15 = 10, cible 12 → écart +2 ;
        # N = 6,24 (3 mois), cible 6,24 → écart 0.
        assert payload["cp_n1_opening_balance"] == 2.0
        assert payload["cp_n_opening_balance"] == 0.0
        assert upsert.call_args.args[:3] == ("co-1", "girerd", 2026)

    @patch(f"{_CMD}.upsert_employee_adjustment")
    @patch(f"{_CMD}.absence_repository")
    @patch(f"{_QUERIES}.get_employee_hire_date")
    @patch(f"{_CMD}.list_company_adjustments_avec_reference")
    def test_sans_date_d_embauche_la_ligne_est_ignoree(self, lister, hire, repo, upsert):
        lister.return_value = [self._ligne_girerd()]
        hire.return_value = None

        assert rebaser_reprises_cp("co-1", OUVRABLE, OUVRE) == 0
        upsert.assert_not_called()

    @patch(f"{_CMD}.upsert_employee_adjustment")
    @patch(f"{_CMD}.absence_repository")
    @patch(f"{_QUERIES}.get_employee_hire_date")
    @patch(f"{_CMD}.list_company_adjustments_avec_reference")
    def test_un_ecart_inchange_n_est_pas_reecrit(self, lister, hire, repo, upsert):
        lister.return_value = [self._ligne_girerd()]
        hire.return_value = "2014-09-01"
        repo.list_validated_for_employees.return_value = []

        assert rebaser_reprises_cp("co-1", OUVRABLE, OUVRABLE) == 0
        upsert.assert_not_called()
