"""Pose d'un RTT : le solde est contrôlé, comme pour les congés payés."""

from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from app.modules.absences.application import commands
from app.modules.absences.domain.rules import message_solde_rtt_insuffisant


class TestMessageSoldeRttInsuffisant:
    def test_solde_nul(self):
        assert (
            message_solde_rtt_insuffisant(0.0, 1.0) == "Solde RTT insuffisant : 0 jour"
        )

    def test_solde_partiel(self):
        message = message_solde_rtt_insuffisant(1.0, 2.0)
        assert message.startswith("Solde RTT insuffisant : 1 jour")
        assert "2 jours" in message

    def test_solde_suffisant(self):
        assert message_solde_rtt_insuffisant(2.0, 2.0) is None

    def test_solde_negatif_compte_pour_zero(self):
        assert (
            message_solde_rtt_insuffisant(-1.0, 1.0) == "Solde RTT insuffisant : 0 jour"
        )


class TestCommandeRtt:
    def _demande(self):
        demande = MagicMock()
        demande.selected_days = [date(2026, 10, 20)]
        demande.type = "rtt"
        demande.employee_id = "emp-1"
        demande.event_subtype = None
        demande.demi_journees = None
        return demande

    def test_salarie_sans_solde_est_refuse(self):
        with patch(
            "app.modules.absences.application.queries.rtt_shortfall_message",
            return_value="Solde RTT insuffisant : 0 jour",
        ):
            with pytest.raises(ValueError, match="Solde RTT insuffisant"):
                commands.create_absence_request(
                    self._demande(), enforce_conge_paye_balance=True
                )
