"""Demi-journées de CP — schéma, quotités et décompte de solde."""

from datetime import date

import pytest

from app.modules.absences.domain.rules import (
    count_absence_days_taken,
    quotite_demi_journees,
)
from app.modules.absences.schemas.requests import AbsenceRequestCreate

pytestmark = pytest.mark.unit


class TestSchemaDemiJournees:
    def test_cp_avec_demi_journee_valide(self):
        req = AbsenceRequestCreate(
            employee_id="emp-1",
            type="conge_paye",
            selected_days=[date(2026, 9, 14), date(2026, 9, 15)],
            demi_journees={date(2026, 9, 15): "matin"},
        )
        assert req.demi_journees == {date(2026, 9, 15): "matin"}

    def test_demi_journee_refusee_hors_cp(self):
        with pytest.raises(ValueError, match="congés payés"):
            AbsenceRequestCreate(
                employee_id="emp-1",
                type="rtt",
                selected_days=[date(2026, 9, 14)],
                demi_journees={date(2026, 9, 14): "matin"},
            )

    def test_demi_journee_hors_selection_refusee(self):
        with pytest.raises(ValueError, match="jour sélectionné"):
            AbsenceRequestCreate(
                employee_id="emp-1",
                type="conge_paye",
                selected_days=[date(2026, 9, 14)],
                demi_journees={date(2026, 9, 20): "apres_midi"},
            )

    def test_valeur_autre_que_matin_apres_midi_refusee(self):
        with pytest.raises(ValueError):
            AbsenceRequestCreate(
                employee_id="emp-1",
                type="conge_paye",
                selected_days=[date(2026, 9, 14)],
                demi_journees={date(2026, 9, 14): "soir"},
            )


class TestGardeForfaitJours:
    def test_demi_journee_refusee_pour_un_forfait_jours(self):
        """Le forfait-jours se décompte à la journée : la ½ CP est refusée à
        la création (sinon 0,5 débité au solde sans ligne fiable au bulletin)."""
        from unittest.mock import patch

        from app.modules.absences.application import commands

        req = AbsenceRequestCreate(
            employee_id="emp-1",
            type="conge_paye",
            selected_days=[date(2026, 9, 14)],
            demi_journees={date(2026, 9, 14): "matin"},
        )
        with patch(
            "app.modules.absences.application.commands.get_employee_statut",
            return_value="Cadre au forfait jour",
        ):
            with pytest.raises(ValueError, match="forfait"):
                commands.create_absence_request(req)


class TestQuotiteDemiJournees:
    def test_cles_date_et_iso(self):
        jours = [date(2026, 9, 14), date(2026, 9, 15), date(2026, 9, 16)]
        assert quotite_demi_journees(jours, {"2026-09-15": "matin"}) == 2.5
        assert quotite_demi_journees(jours, {date(2026, 9, 15): "matin"}) == 2.5

    def test_sans_demi_journees(self):
        jours = [date(2026, 9, 14), date(2026, 9, 15)]
        assert quotite_demi_journees(jours, None) == 2.0
        assert quotite_demi_journees(jours, {}) == 2.0


class TestCountAbsenceDaysTakenPondere:
    def test_demande_validee_avec_demi_journee(self):
        """3 jours dont un « matin » = 2,5 pris (jours_payes couvre tout)."""
        requests = [
            {
                "type": "conge_paye",
                "status": "validated",
                "selected_days": ["2026-08-10", "2026-08-11", "2026-08-12"],
                "demi_journees": {"2026-08-12": "matin"},
                "jours_payes": 2.5,
            }
        ]
        assert (
            count_absence_days_taken(requests, "conge_paye", date(2026, 12, 31))
            == 2.5
        )

    def test_pending_sans_jours_payes_pondere_aussi(self):
        requests = [
            {
                "type": "conge_paye",
                "status": "pending",
                "selected_days": ["2026-08-10", "2026-08-11"],
                "demi_journees": {"2026-08-10": "apres_midi"},
            }
        ]
        assert (
            count_absence_days_taken(requests, "conge_paye", date(2026, 12, 31))
            == 1.5
        )

    def test_jour_plein_inchange(self):
        requests = [
            {
                "type": "conge_paye",
                "status": "validated",
                "selected_days": ["2026-08-10", "2026-08-11"],
                "jours_payes": 2,
            }
        ]
        assert (
            count_absence_days_taken(requests, "conge_paye", date(2026, 12, 31))
            == 2.0
        )
