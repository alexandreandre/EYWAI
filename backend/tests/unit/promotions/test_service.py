"""
Tests unitaires du service applicatif promotions (application/service.py).

Dépendances (IEmployeeUpdater) mockées ; pas de DB.
"""
from unittest.mock import MagicMock, patch


from app.modules.promotions.application import service


COMPANY_ID = "company-promo-test"
PROMOTION_ID = "promo-1"
EMPLOYEE_ID = "emp-1"


class TestApplyPromotionChanges:
    """apply_promotion_changes."""

    @patch("app.modules.promotions.application.service.get_employee_updater")
    def test_delegates_to_employee_updater(self, mock_get_updater):
        """Délègue à IEmployeeUpdater.apply_promotion_changes."""
        mock_updater = MagicMock()
        mock_get_updater.return_value = mock_updater

        promotion = MagicMock()
        promotion.id = PROMOTION_ID
        promotion.employee_id = EMPLOYEE_ID
        promotion.new_job_title = "Lead Dev"
        promotion.new_salary = {"valeur": 4000}
        promotion.new_statut = None
        promotion.new_classification = None
        promotion.grant_rh_access = False
        promotion.new_rh_access = None

        service.apply_promotion_changes(promotion, COMPANY_ID)

        mock_updater.apply_promotion_changes.assert_called_once_with(
            promotion,
            COMPANY_ID,
        )


class TestUpdateEmployeeRhAccess:
    """update_employee_rh_access."""

    @patch("app.modules.promotions.application.service.get_employee_updater")
    def test_delegates_to_employee_updater(self, mock_get_updater):
        """Délègue à IEmployeeUpdater.update_employee_rh_access."""
        mock_updater = MagicMock()
        mock_get_updater.return_value = mock_updater

        service.update_employee_rh_access(
            employee_id=EMPLOYEE_ID,
            company_id=COMPANY_ID,
            new_rh_access="rh",
            promotion_id=PROMOTION_ID,
        )

        mock_updater.update_employee_rh_access.assert_called_once_with(
            employee_id=EMPLOYEE_ID,
            company_id=COMPANY_ID,
            new_rh_access="rh",
            promotion_id=PROMOTION_ID,
        )
