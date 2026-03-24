"""
Tests unitaires du service applicatif repos_compensateur (application/service.py).

Dépendances infrastructure (get_company_effectif, get_employees_for_company,
get_bulletins_par_mois_par_employe, upsert_credit) mockées.
"""
from unittest.mock import patch

import pytest

from app.modules.repos_compensateur.application.dto import CalculerCreditsResult
from app.modules.repos_compensateur.application.service import (
    calculer_credits_repos,
    recalculer_credits_repos_employe,
)


class TestCalculerCreditsRepos:
    """Service calculer_credits_repos."""

    def test_no_employees_returns_zero_processed_and_credits(self):
        """Entreprise sans employés → employees_processed=0, credits_created=0."""
        with patch(
            "app.modules.repos_compensateur.application.service.get_company_effectif",
            return_value=25,
        ), patch(
            "app.modules.repos_compensateur.application.service.get_employees_for_company",
            return_value=[],
        ):
            result = calculer_credits_repos(
                year=2025,
                month=6,
                target_company_id="comp-vide",
            )
            assert isinstance(result, CalculerCreditsResult)
            assert result.company_id == "comp-vide"
            assert result.year == 2025
            assert result.month == 6
            assert result.employees_processed == 0
            assert result.credits_created == 0

    def test_employees_with_no_hs_no_credits_created(self):
        """Employés sans heures sup ce mois → credits_created=0, employees_processed>0."""
        with patch(
            "app.modules.repos_compensateur.application.service.get_company_effectif",
            return_value=30,
        ), patch(
            "app.modules.repos_compensateur.application.service.get_employees_for_company",
            return_value=[
                {"id": "emp-1", "company_id": "comp-1"},
                {"id": "emp-2", "company_id": "comp-1"},
            ],
        ), patch(
            "app.modules.repos_compensateur.application.service.get_bulletins_par_mois_par_employe",
            return_value={
                "emp-1": {6: {}},  # pas de calcul_du_brut HS
                "emp-2": {6: {}},
            },
        ), patch(
            "app.modules.repos_compensateur.application.service.upsert_credit",
            return_value=True,
        ):
            result = calculer_credits_repos(
                year=2025,
                month=6,
                target_company_id="comp-1",
            )
            assert result.employees_processed == 2
            assert result.credits_created == 0

    def test_employee_with_hs_above_contingent_creates_credit(self):
        """Un employé avec cumul HS au-dessus du contingent → 1 crédit créé (upsert appelé)."""
        # Cumul fin mai = 200, cumul fin juin = 250 → 30 h COR ce mois → 30/7 jours
        bulletins_emp1 = {
            5: {"calcul_du_brut": [{"libelle": "Heures suppl", "quantite": 200.0}]},
            6: {"calcul_du_brut": [{"libelle": "Heures suppl", "quantite": 50.0}]},
        }
        for m in list(range(1, 5)) + list(range(7, 13)):
            bulletins_emp1[m] = {}

        with patch(
            "app.modules.repos_compensateur.application.service.get_company_effectif",
            return_value=25,
        ), patch(
            "app.modules.repos_compensateur.application.service.get_employees_for_company",
            return_value=[{"id": "emp-1", "company_id": "comp-1"}],
        ), patch(
            "app.modules.repos_compensateur.application.service.get_bulletins_par_mois_par_employe",
            return_value={"emp-1": bulletins_emp1},
        ), patch(
            "app.modules.repos_compensateur.application.service.upsert_credit",
            return_value=True,
        ) as upsert:
            result = calculer_credits_repos(
                year=2025,
                month=6,
                target_company_id="comp-1",
            )
            assert result.employees_processed == 1
            assert result.credits_created == 1
            assert upsert.called
            call_args = upsert.call_args[0][0]
            assert call_args.employee_id == "emp-1"
            assert call_args.company_id == "comp-1"
            assert call_args.year == 2025
            assert call_args.month == 6
            assert call_args.source == "cor"
            assert call_args.heures == 30.0
            assert call_args.jours == round(30.0 / 7.0, 2)

    def test_effectif_under_20_uses_taux_demi(self):
        """Effectif < 20 → taux COR 0.5 → moins d'heures COR pour même dépassement."""
        bulletins_emp1 = {
            5: {"calcul_du_brut": [{"libelle": "Heures suppl", "quantite": 200.0}]},
            6: {"calcul_du_brut": [{"libelle": "Heures suppl", "quantite": 50.0}]},
        }
        for m in range(1, 5):
            bulletins_emp1[m] = {}
        for m in range(7, 13):
            bulletins_emp1[m] = {}

        with patch(
            "app.modules.repos_compensateur.application.service.get_company_effectif",
            return_value=15,
        ), patch(
            "app.modules.repos_compensateur.application.service.get_employees_for_company",
            return_value=[{"id": "emp-1", "company_id": "comp-1"}],
        ), patch(
            "app.modules.repos_compensateur.application.service.get_bulletins_par_mois_par_employe",
            return_value={"emp-1": bulletins_emp1},
        ), patch(
            "app.modules.repos_compensateur.application.service.upsert_credit",
            return_value=True,
        ) as upsert:
            calculer_credits_repos(
                year=2025,
                month=6,
                target_company_id="comp-1",
            )
            call_args = upsert.call_args[0][0]
            # 30 * 0.5 = 15 h COR
            assert call_args.heures == 15.0
            assert call_args.jours == round(15.0 / 7.0, 2)


class TestRecalculerCreditsReposEmploye:
    """Service recalculer_credits_repos_employe."""

    def test_returns_number_of_upserts(self):
        """Retourne le nombre de mois pour lesquels upsert_credit a retourné True."""
        bulletins = {}
        for m in range(1, 13):
            bulletins[m] = {} if m != 6 else {"calcul_du_brut": [{"libelle": "Heures suppl", "quantite": 230.0}]}

        with patch(
            "app.modules.repos_compensateur.application.service.get_company_effectif",
            return_value=25,
        ), patch(
            "app.modules.repos_compensateur.application.service.get_bulletins_par_mois_par_employe",
            return_value={"emp-1": bulletins},
        ), patch(
            "app.modules.repos_compensateur.application.service.upsert_credit",
            return_value=True,
        ):
            result = recalculer_credits_repos_employe(
                employee_id="emp-1",
                company_id="comp-1",
                year=2025,
            )
            assert result == 12

    def test_exception_returns_zero(self):
        """En cas d'exception, retourne 0 (log warning côté service)."""
        with patch(
            "app.modules.repos_compensateur.application.service.get_company_effectif",
            side_effect=Exception("DB error"),
        ):
            result = recalculer_credits_repos_employe(
                employee_id="emp-1",
                company_id="comp-1",
                year=2025,
            )
            assert result == 0
