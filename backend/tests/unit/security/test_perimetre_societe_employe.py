"""
Périmètre société de require_employee_access (IDOR fermé le 23/08/2026).

Audit Axe A : la fonction ne vérifiait JAMAIS que l'employee_id visé
appartenait à la société de l'appelant. Le company_id qu'elle reçoit est
toujours la société ACTIVE de l'appelant, jamais celle du salarié — une RH
de la société A obtenait donc les bulletins, pointages, contrats et notes
de frais d'un salarié de la société B (10 routes concernées, un seul point
de correction).
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi import HTTPException

from app.modules.access_control.application.service import (
    get_access_control_service,
)
from app.modules.users.schemas.responses import CompanyAccess, User

SOCIETE_A = "aaaaaaaa-1111-1111-1111-111111111111"
SOCIETE_B = "bbbbbbbb-2222-2222-2222-222222222222"
SALARIE_DE_B = "cccccccc-3333-3333-3333-333333333333"
PERMISSION = "payslips.view"


def _user(role: str = "rh", *, platform_admin: bool = False) -> User:
    return User(
        id="dddddddd-4444-4444-4444-444444444444",
        email="rh@societe-a.fr",
        first_name="Rita",
        last_name="Aitch",
        is_platform_admin=platform_admin,
        is_group_admin=False,
        accessible_companies=[
            CompanyAccess(
                company_id=SOCIETE_A,
                company_name="Société A",
                role=role,
                is_primary=True,
            ),
        ],
        active_company_id=SOCIETE_A,
    )


class TestPerimetreSocieteSalarie:
    def test_rh_ne_peut_pas_viser_un_salarie_d_une_autre_societe(self):
        """Le raccourci « rôle RH » ne doit plus ouvrir les fiches d'ailleurs."""
        service = get_access_control_service()
        with patch(
            "app.modules.access_control.application.service.providers"
        ) as providers:
            providers.get_employee_company_id.return_value = SOCIETE_B
            with pytest.raises(HTTPException) as exc:
                service.require_employee_access(
                    _user(), SOCIETE_A, PERMISSION, SALARIE_DE_B
                )
        # 404 et non 403 : on ne révèle pas l'existence du salarié.
        assert exc.value.status_code == 404

    def test_salarie_introuvable_refuse_aussi(self):
        """Société illisible ou salarié inexistant → refus (fail-closed)."""
        service = get_access_control_service()
        with patch(
            "app.modules.access_control.application.service.providers"
        ) as providers:
            providers.get_employee_company_id.return_value = None
            with pytest.raises(HTTPException) as exc:
                service.require_employee_access(
                    _user(), SOCIETE_A, PERMISSION, SALARIE_DE_B
                )
        assert exc.value.status_code == 404

    def test_meme_societe_reste_autorise(self):
        """Non-régression : le cas nominal (salarié de sa société) passe."""
        service = get_access_control_service()
        with patch(
            "app.modules.access_control.application.service.providers"
        ) as providers:
            providers.get_employee_company_id.return_value = SOCIETE_A
            service.require_employee_access(
                _user(), SOCIETE_A, PERMISSION, SALARIE_DE_B
            )  # ne lève pas

    def test_platform_admin_reste_hors_perimetre(self):
        """L'administrateur plateforme conserve son accès transverse."""
        service = get_access_control_service()
        with patch(
            "app.modules.access_control.application.service.providers"
        ) as providers:
            providers.get_employee_company_id.return_value = SOCIETE_B
            service.require_employee_access(
                _user(platform_admin=True), SOCIETE_A, PERMISSION, SALARIE_DE_B
            )  # ne lève pas


# ----- credentials-pdf : la route qui RÉINITIALISE le mot de passe -----


class TestCredentialsPdfGardee:
    """GET /api/employees/{id}/credentials-pdf n'avait AUCUN contrôle RH ni
    société — et sa chaîne d'appel provisionne un compte, donc réinitialise
    le mot de passe du salarié visé. Tout utilisateur connecté pouvait ainsi
    prendre le contrôle du compte de n'importe quel salarié."""

    def _appel(self, url: str, role: str):
        from fastapi.testclient import TestClient

        from app.core.security import get_current_user
        from app.main import app

        app.dependency_overrides[get_current_user] = lambda: _user(role=role)
        try:
            with patch(
                "app.modules.employees.api.router.queries"
            ) as queries:
                queries.get_credentials_pdf_urls.return_value = ("u", "p")
                queries.get_credentials_pdf_content.return_value = (b"%PDF", "f.pdf")
                reponse = TestClient(app).get(url)
            return reponse, queries
        finally:
            app.dependency_overrides.pop(get_current_user, None)

    def test_collaborateur_ne_peut_pas_declencher_le_pdf_identifiants(self):
        reponse, queries = self._appel(
            f"/api/employees/{SALARIE_DE_B}/credentials-pdf", "collaborateur"
        )
        assert reponse.status_code == 403
        # Le plus important : la chaîne mutante n'a jamais démarré.
        queries.get_credentials_pdf_urls.assert_not_called()

    def test_collaborateur_ne_peut_pas_streamer_le_pdf_identifiants(self):
        reponse, queries = self._appel(
            f"/api/employees/{SALARIE_DE_B}/credentials-pdf/content", "collaborateur"
        )
        assert reponse.status_code == 403
        queries.get_credentials_pdf_content.assert_not_called()

    def test_rh_d_une_autre_societe_refuse(self):
        from fastapi.testclient import TestClient

        from app.core.security import get_current_user
        from app.main import app

        app.dependency_overrides[get_current_user] = lambda: _user(role="rh")
        try:
            with (
                patch("app.modules.employees.api.router.queries") as queries,
                patch(
                    "app.modules.access_control.application.service.providers"
                ) as providers,
            ):
                providers.get_employee_company_id.return_value = SOCIETE_B
                queries.get_credentials_pdf_urls.return_value = ("u", "p")
                reponse = TestClient(app).get(
                    f"/api/employees/{SALARIE_DE_B}/credentials-pdf"
                )
            assert reponse.status_code == 404
            queries.get_credentials_pdf_urls.assert_not_called()
        finally:
            app.dependency_overrides.pop(get_current_user, None)
