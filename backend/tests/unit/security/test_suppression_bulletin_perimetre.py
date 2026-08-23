"""
DELETE /api/payslips/{id} : contrôle aligné sur ses routes voisines.

Audit Axe A : la suppression se contentait de `_require_rh_company_context`
(« êtes-vous RH quelque part ? ») sans jamais résoudre le bulletin visé,
alors que /validate et /preview utilisent `_require_payslip_scope`, qui
vérifie que le bulletin appartient bien à la société active. Une RH pouvait
donc supprimer le bulletin d'une AUTRE société.
"""

from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from app.core.security import get_current_user
from app.main import app
from app.modules.users.schemas.responses import CompanyAccess, User

MA_SOCIETE = "11111111-1111-1111-1111-111111111111"
AUTRE_SOCIETE = "99999999-9999-9999-9999-999999999999"
BULLETIN = "33333333-3333-3333-3333-333333333333"


def _rh() -> User:
    return User(
        id="22222222-2222-2222-2222-222222222222",
        email="rh@entreprise.fr",
        first_name="Rita",
        last_name="Aitch",
        is_platform_admin=False,
        is_group_admin=False,
        accessible_companies=[
            CompanyAccess(
                company_id=MA_SOCIETE,
                company_name="Ma société",
                role="rh",
                is_primary=True,
            ),
        ],
        active_company_id=MA_SOCIETE,
    )


class TestSuppressionBulletinPerimetre:
    def _supprimer(self, societe_du_bulletin: str):
        app.dependency_overrides[get_current_user] = _rh
        try:
            with (
                patch(
                    "app.modules.payslips.api.router.get_payslip_meta_for_access"
                ) as meta,
                patch("app.modules.payslips.api.router.delete_payslip") as suppr,
                patch(
                    "app.modules.payslips.api.router.access_control_service"
                ) as acces,
            ):
                meta.return_value = {
                    "company_id": societe_du_bulletin,
                    "employee_id": "44444444-4444-4444-4444-444444444444",
                    "status": "brouillon",
                }
                acces.require_employee_access.return_value = None
                reponse = TestClient(app).delete(f"/api/payslips/{BULLETIN}")
            return reponse, suppr
        finally:
            app.dependency_overrides.pop(get_current_user, None)

    def test_bulletin_d_une_autre_societe_introuvable(self):
        reponse, suppr = self._supprimer(AUTRE_SOCIETE)
        assert reponse.status_code == 404
        suppr.assert_not_called()

    def test_bulletin_de_ma_societe_supprime(self):
        reponse, suppr = self._supprimer(MA_SOCIETE)
        assert reponse.status_code == 204
        suppr.assert_called_once()
