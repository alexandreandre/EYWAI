"""Tests des overrides what-if de la simulation d'arrêt maladie (parties pures)."""

from __future__ import annotations

from datetime import date

from unittest.mock import patch

from app.modules.payroll.application.simulation_arret_maladie import (
    _employee_payload_for_contexte,
    _hire_date_pour_anciennete,
)
from app.modules.payroll.engine.maintien_salaire_service import _mois_anciennete, calculer_maintien
from .helpers import build_test_contexte


class TestHireDatePourAnciennete:
    def test_roundtrip_anciennete(self):
        ref = date(2026, 6, 1)
        for mois in (0, 12, 47, 72, 132, 372):
            hire = _hire_date_pour_anciennete(ref, mois)
            assert _mois_anciennete(hire, ref) == mois

    def test_anciennete_negative_clampee(self):
        ref = date(2026, 6, 1)
        hire = _hire_date_pour_anciennete(ref, -5)
        assert _mois_anciennete(hire, ref) == 0


class TestEmployeePayloadSalaireTimeline:
    @patch("app.modules.payroll.application.simulation_arret_maladie.EmployeeRepository")
    def test_resout_salaire_depuis_historique(self, mock_repo_cls):
        mock_repo_cls.return_value.get_salary_history.return_value = [
            {
                "id": "h1",
                "effective_date": "2025-01-01",
                "nouveau_salaire": {"valeur": 2800},
            }
        ]
        emp = {
            "id": "emp-1",
            "company_id": "co-1",
            "first_name": "Ada",
            "last_name": "Lovelace",
            "hire_date": "2024-01-01",
            "salaire_de_base": {"valeur": 0},
        }
        payload = _employee_payload_for_contexte(
            emp,
            {"id": "co-1"},
            salaire_a_date=date(2026, 6, 1),
        )
        assert payload["salaire_base"] == 2800.0


class TestAlerteIjssSalaireAbsent:
    def test_alerte_explicite_si_salaire_zero(self):
        ctx = build_test_contexte(salaire_base=0.0)
        result = calculer_maintien(
            {
                "arret_type": "maladie_simple",
                "date_debut": "2026-06-01",
                "date_fin": "2026-06-07",
                "subrogation_active": True,
                "nombre_enfants": 0,
                "historique_arrets_annee": [],
            },
            ctx,
            {},
            date(2026, 6, 1),
            date(2026, 6, 7),
        )
        assert any("salaire de base absent" in a.lower() for a in result["alertes"])
