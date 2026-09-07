"""Saisie RH d'un solde cible (CP N-1 / CP N / RTT / JTC) → écart d'ouverture."""

from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from app.modules.absences.application.leave_settings_commands import (
    apply_leave_solde_manual,
)
from app.modules.absences.domain.leave_policy import EmployeeLeaveAdjustment

_CMD = "app.modules.absences.application.leave_settings_commands"
_RULES = "app.modules.absences.domain.rules"


def _row(**kw):
    base = {
        "cp_n1_opening_balance": 0,
        "cp_n_opening_balance": 0,
        "rtt_opening_balance": 0,
        "rtt_forfeited_at": None,
        "rtt_forfeited_days": 0,
        "note": None,
    }
    base.update(kw)
    return base


class TestApplyLeaveSoldeManualCp:
    @patch(f"{_CMD}.upsert_employee_adjustment")
    @patch(f"{_RULES}.compute_cp_period_balances")
    @patch(f"{_CMD}.get_employee_hire_date", return_value="2021-09-13")
    @patch(f"{_CMD}.get_employee_adjustment")
    @patch(f"{_CMD}.absence_repository")
    @patch(f"{_CMD}.get_leave_policy")
    @patch(f"{_CMD}._ensure_employee_in_company")
    def test_cp_n1_cible_reecrit_le_couple_en_absolu(
        self,
        _ensure,
        _policy,
        repo,
        get_adj,
        _hire,
        mock_periods,
        mock_upsert,
    ):
        """Cible 14,46 avec théorique N-1 = 20 → écart −5,54 ; le CP N garde
        son affiché (2,0 pour un théorique 6,0 → écart −4,0) ; la date de
        référence est posée à aujourd'hui."""
        repo.list_validated_for_employees.return_value = []
        get_adj.return_value = EmployeeLeaveAdjustment.empty()
        # 1er appel = affiché (ajustement actuel), 2e = théorique (neutre).
        mock_periods.side_effect = [
            {"n1_remaining": 5.0, "n_remaining": 2.0},
            {"n1_remaining": 20.0, "n_remaining": 6.0},
        ]
        mock_upsert.return_value = _row(
            cp_n1_opening_balance=-5.54, cp_n_opening_balance=-4.0
        )

        apply_leave_solde_manual(
            "co-1", "emp-1", 2026, compteur="cp_n1", solde_cible=14.46
        )

        payload = mock_upsert.call_args[0][3]
        assert payload["cp_n1_opening_balance"] == pytest.approx(14.46 - 20.0)
        assert payload["cp_n_opening_balance"] == pytest.approx(2.0 - 6.0)
        assert payload["cp_opening_reference_date"] == date.today().isoformat()
        assert "Ajustement manuel RH" in payload["note"]

    @patch(f"{_CMD}.upsert_employee_adjustment")
    @patch(f"{_RULES}._bulletin_faithful_cp_solde")
    @patch(f"{_RULES}.compute_cp_period_balances")
    @patch(f"{_CMD}.get_employee_hire_date", return_value="2021-09-13")
    @patch(f"{_CMD}.get_employee_adjustment")
    @patch(f"{_CMD}.absence_repository")
    @patch(f"{_CMD}.get_leave_policy")
    @patch(f"{_CMD}._ensure_employee_in_company")
    def test_mode_fidele_au_bulletin_utilise_et_marqueur_neutralise(
        self,
        _ensure,
        _policy,
        repo,
        get_adj,
        _hire,
        mock_periods,
        mock_fidele,
        mock_upsert,
    ):
        """Salarié repris (note « Import CP bulletin ») : l'affiché vient du
        mode fidèle, et la nouvelle note NE contient PLUS le marqueur (sinon
        l'ajustement serait ré-ancré sur l'ancien mois d'import)."""
        repo.list_validated_for_employees.return_value = []
        get_adj.return_value = EmployeeLeaveAdjustment(
            cp_n1_opening_balance=-15.0,
            cp_n_opening_balance=-5.04,
            rtt_opening_balance=0.0,
            jtc_opening_balance=0.0,
            note="Import CP bulletin Mai 2026 (05-2026 COLORPLAST.pdf)",
        )
        mock_periods.side_effect = [
            {"n1_remaining": 9.0, "n_remaining": 1.0},  # affiché (non fidèle)
            {"n1_remaining": 20.0, "n_remaining": 6.0},  # théorique neutre
        ]
        mock_fidele.return_value = {"n1_remaining": 14.46, "n_remaining": 5.0}
        mock_upsert.return_value = _row()

        apply_leave_solde_manual(
            "co-1", "emp-1", 2026, compteur="cp_n", solde_cible=3.0
        )

        payload = mock_upsert.call_args[0][3]
        # cp_n1 non modifié = affiché FIDÈLE (14,46), pas 9,0.
        assert payload["cp_n1_opening_balance"] == pytest.approx(14.46 - 20.0)
        assert payload["cp_n_opening_balance"] == pytest.approx(3.0 - 6.0)
        assert "Import CP bulletin" not in payload["note"]
        assert "reprise bulletin (archivée)" in payload["note"]


class TestApplyLeaveSoldeManualJtcEtRtt:
    @patch(f"{_CMD}.upsert_employee_adjustment")
    @patch(f"{_RULES}.compute_jtc_balance")
    @patch(f"{_CMD}.get_employee_adjustment")
    @patch(f"{_CMD}.absence_repository")
    @patch(f"{_CMD}.get_leave_policy")
    @patch(f"{_CMD}._ensure_employee_in_company")
    def test_jtc_cible_est_convertie_en_droit_absolu(
        self, _ensure, mock_policy, repo, get_adj, mock_jtc, mock_upsert
    ):
        """jtc_opening_balance est un DROIT, pas un écart : cible 5 restants
        avec 3 pris → droit 8."""
        mock_policy.return_value = MagicMock(jtc_enabled=True)
        repo.list_validated_for_employees.return_value = []
        get_adj.return_value = EmployeeLeaveAdjustment.empty()
        mock_jtc.return_value = {"acquis": 0.0, "pris": 3.0, "solde": 0.0}
        mock_upsert.return_value = _row()

        apply_leave_solde_manual(
            "co-1", "emp-1", 2026, compteur="jtc", solde_cible=5.0
        )

        payload = mock_upsert.call_args[0][3]
        assert payload["jtc_opening_balance"] == pytest.approx(8.0)

    @patch(f"{_CMD}.apply_rtt_solde_manual")
    def test_rtt_delegue_a_la_commande_existante(self, mock_rtt):
        mock_rtt.return_value = "ok"
        out = apply_leave_solde_manual(
            "co-1", "emp-1", 2026, compteur="rtt", solde_cible=2.0, note="n"
        )
        assert out == "ok"
        mock_rtt.assert_called_once_with(
            "co-1", "emp-1", 2026, rtt_solde=2.0, note="n"
        )

    @patch(f"{_CMD}.get_employee_adjustment")
    @patch(f"{_CMD}.absence_repository")
    @patch(f"{_CMD}.get_leave_policy")
    @patch(f"{_CMD}._ensure_employee_in_company")
    def test_jtc_refuse_si_non_actives(self, _ensure, mock_policy, repo, get_adj):
        mock_policy.return_value = MagicMock(jtc_enabled=False)
        repo.list_validated_for_employees.return_value = []
        get_adj.return_value = EmployeeLeaveAdjustment.empty()
        with pytest.raises(ValueError, match="JTC"):
            apply_leave_solde_manual(
                "co-1", "emp-1", 2026, compteur="jtc", solde_cible=5.0
            )
