"""Saisie RH d'un solde cible (RTT / JTC) → écart d'ouverture.

Les CP sont volontairement exclus : l'inversion cible→écart est piégeuse
(bascule N→N-1 du 1er juin, mode « fidèle au bulletin », CP planning,
ancienneté) — le recalage CP passe par apply_cp_solde_import.
"""

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


class TestApplyLeaveSoldeManual:
    def test_cp_refuse_avec_message_explicite(self):
        with pytest.raises(ValueError, match="reprise d'un bulletin"):
            apply_leave_solde_manual(
                "co-1", "emp-1", 2026, compteur="cp_n1", solde_cible=14.46
            )

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
        avec 3 pris → droit 8 (le solde affiché redevient exactement 5)."""
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
        assert "note" not in payload  # sans note utilisateur, rien n'est touché

    @patch(f"{_CMD}.upsert_employee_adjustment")
    @patch(f"{_RULES}.compute_jtc_balance")
    @patch(f"{_CMD}.get_employee_adjustment")
    @patch(f"{_CMD}.absence_repository")
    @patch(f"{_CMD}.get_leave_policy")
    @patch(f"{_CMD}._ensure_employee_in_company")
    def test_jtc_note_preserve_le_marqueur_d_import(
        self, _ensure, mock_policy, repo, get_adj, mock_jtc, mock_upsert
    ):
        """La note d'un salarié repris commence par « Import CP bulletin … » :
        elle DOIT rester en tête telle quelle (elle ancre le mode « fidèle au
        bulletin » des CP/RTT), la note d'ajustement s'appose après."""
        mock_policy.return_value = MagicMock(jtc_enabled=True)
        repo.list_validated_for_employees.return_value = []
        ancienne = "Import CP bulletin Mai 2026 (05-2026 COLORPLAST.pdf)"
        get_adj.return_value = EmployeeLeaveAdjustment(
            cp_n1_opening_balance=-15.0,
            cp_n_opening_balance=-5.04,
            rtt_opening_balance=0.0,
            jtc_opening_balance=0.0,
            note=ancienne,
        )
        mock_jtc.return_value = {"acquis": 0.0, "pris": 0.0, "solde": 0.0}
        mock_upsert.return_value = _row()

        apply_leave_solde_manual(
            "co-1", "emp-1", 2026, compteur="jtc", solde_cible=4.0, note="recalage"
        )

        payload = mock_upsert.call_args[0][3]
        assert payload["note"].startswith(ancienne)
        assert "Ajustement manuel RH" in payload["note"]

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
