"""
Tests unitaires EmployeeUpdater (application des changements promotion sur l'employé).
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.modules.promotions.infrastructure.providers import EmployeeUpdater


COMPANY_ID = "company-promo-test"
EMPLOYEE_ID = "emp-promo-test"
PROMOTION_ID = "promo-statut-1"


def _promotion_mock(**kwargs):
    promo = MagicMock()
    promo.id = kwargs.get("id", PROMOTION_ID)
    promo.employee_id = kwargs.get("employee_id", EMPLOYEE_ID)
    promo.new_job_title = kwargs.get("new_job_title")
    promo.new_salary = kwargs.get("new_salary")
    promo.new_statut = kwargs.get("new_statut")
    promo.new_classification = kwargs.get("new_classification")
    promo.grant_rh_access = kwargs.get("grant_rh_access", False)
    promo.new_rh_access = kwargs.get("new_rh_access")
    return promo


class TestEmployeeUpdaterApplyPromotionChanges:
    """apply_promotion_changes : mise à jour employé selon le type de promotion."""

    @patch("app.modules.promotions.infrastructure.providers.supabase")
    def test_statut_non_cadre_to_cadre_updates_employee(self, mock_supabase):
        """Promotion statut Non-Cadre → Cadre : champ statut mis à jour en base."""
        mock_table = MagicMock()
        mock_supabase.table.return_value = mock_table
        mock_table.update.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{"id": EMPLOYEE_ID, "statut": "Cadre"}]
        )

        updater = EmployeeUpdater()
        promo = _promotion_mock(new_statut="Cadre")

        updater.apply_promotion_changes(promo, COMPANY_ID)

        mock_supabase.table.assert_called_with("employees")
        update_call = mock_table.update.call_args[0][0]
        assert update_call == {"statut": "Cadre"}

    @patch("app.modules.promotions.infrastructure.providers.supabase")
    def test_statut_cadre_to_non_cadre_updates_employee(self, mock_supabase):
        """Promotion statut Cadre → Non-Cadre."""
        mock_table = MagicMock()
        mock_supabase.table.return_value = mock_table
        mock_table.update.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{"id": EMPLOYEE_ID}]
        )

        updater = EmployeeUpdater()
        promo = _promotion_mock(new_statut="Non-Cadre")

        updater.apply_promotion_changes(promo, COMPANY_ID)

        assert mock_table.update.call_args[0][0] == {"statut": "Non-Cadre"}

    @patch("app.modules.promotions.infrastructure.providers.supabase")
    def test_poste_updates_job_title(self, mock_supabase):
        mock_table = MagicMock()
        mock_supabase.table.return_value = mock_table
        mock_table.update.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{"id": EMPLOYEE_ID}]
        )

        updater = EmployeeUpdater()
        updater.apply_promotion_changes(
            _promotion_mock(new_job_title="Responsable RH"),
            COMPANY_ID,
        )

        assert mock_table.update.call_args[0][0] == {"job_title": "Responsable RH"}

    @patch(
        "app.modules.employees.application.commands.apply_salary_update",
        return_value={"id": "hist-1"},
    )
    @patch("app.modules.promotions.infrastructure.providers.supabase")
    def test_salaire_updates_salaire_de_base(
        self, mock_supabase, mock_apply_salary_update
    ):
        new_salary = {"valeur": 4200, "devise": "EUR"}
        mock_table = MagicMock()
        mock_supabase.table.return_value = mock_table
        mock_table.update.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{"id": EMPLOYEE_ID}]
        )

        updater = EmployeeUpdater()
        updater.apply_promotion_changes(
            _promotion_mock(new_salary=new_salary),
            COMPANY_ID,
        )

        mock_apply_salary_update.assert_called_once()
        call_kw = mock_apply_salary_update.call_args.kwargs
        assert call_kw["employee_id"] == EMPLOYEE_ID
        assert call_kw["company_id"] == COMPANY_ID
        assert call_kw["nouveau_salaire"] == new_salary
        mock_table.update.assert_not_called()

    @patch("app.modules.promotions.infrastructure.providers.supabase")
    def test_classification_updates_classification_conventionnelle(self, mock_supabase):
        new_classif = {"coefficient": 280, "classe_emploi": 8}
        mock_table = MagicMock()
        mock_supabase.table.return_value = mock_table
        mock_table.update.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{"id": EMPLOYEE_ID}]
        )

        updater = EmployeeUpdater()
        updater.apply_promotion_changes(
            _promotion_mock(new_classification=new_classif),
            COMPANY_ID,
        )

        assert mock_table.update.call_args[0][0] == {
            "classification_conventionnelle": new_classif
        }

    @patch(
        "app.modules.employees.application.commands.apply_salary_update",
        return_value={"id": "hist-1"},
    )
    @patch("app.modules.promotions.infrastructure.providers.supabase")
    def test_mixte_updates_all_provided_fields(
        self, mock_supabase, mock_apply_salary_update
    ):
        new_salary = {"valeur": 5500, "devise": "EUR"}
        mock_table = MagicMock()
        mock_supabase.table.return_value = mock_table
        mock_table.update.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{"id": EMPLOYEE_ID}]
        )

        updater = EmployeeUpdater()
        updater.apply_promotion_changes(
            _promotion_mock(
                new_job_title="Directeur",
                new_salary=new_salary,
                new_statut="Cadre",
                new_classification={"coefficient": 300},
            ),
            COMPANY_ID,
        )

        update_data = mock_table.update.call_args[0][0]
        assert update_data["job_title"] == "Directeur"
        assert "salaire_de_base" not in update_data
        assert update_data["statut"] == "Cadre"
        assert update_data["classification_conventionnelle"]["coefficient"] == 300
        mock_apply_salary_update.assert_called_once()
        assert mock_apply_salary_update.call_args.kwargs["nouveau_salaire"] == new_salary

    @patch("app.modules.promotions.infrastructure.providers.supabase")
    def test_raises_500_when_employee_update_returns_empty(self, mock_supabase):
        mock_table = MagicMock()
        mock_supabase.table.return_value = mock_table
        mock_table.update.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[]
        )

        updater = EmployeeUpdater()
        with pytest.raises(HTTPException) as exc_info:
            updater.apply_promotion_changes(_promotion_mock(new_statut="Cadre"), COMPANY_ID)

        assert exc_info.value.status_code == 500
