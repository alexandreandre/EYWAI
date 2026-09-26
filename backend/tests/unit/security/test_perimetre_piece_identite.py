"""
Pièce d'identité d'un salarié : périmètre société (audit du 25/09/2026, E4).

GET /api/employees/{id}/identity-document contrôlait la société ACTIVE de
l'appelant, puis signait l'URL dans la société DU SALARIÉ : une RH de la
société A obtenait la pièce d'identité d'un salarié de la société B. Le
salarié doit désormais appartenir à la société active. Le chemin « sa propre
fiche » (identifiant du compte = identifiant de la fiche) reste inchangé.
"""

from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from app.core.security import get_current_user
from app.main import app
from app.modules.users.schemas.responses import CompanyAccess, User

SOCIETE_A = "aaaaaaaa-1111-1111-1111-111111111111"
SOCIETE_B = "bbbbbbbb-2222-2222-2222-222222222222"
COMPTE = "dddddddd-4444-4444-4444-444444444444"
SALARIE = "cccccccc-3333-3333-3333-333333333333"


def _user(role: str = "rh", *, platform_admin: bool = False) -> User:
    return User(
        id=COMPTE,
        email="compte@societe-a.fr",
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


def _get(user: User, employee_id: str, societe_du_salarie: str | None):
    app.dependency_overrides[get_current_user] = lambda: user
    try:
        with (
            patch("app.modules.employees.api.router.queries") as queries,
            patch(
                "app.modules.access_control.application.service.providers"
            ) as providers,
        ):
            providers.get_employee_company_id.return_value = societe_du_salarie
            queries.get_identity_document_url.return_value = "https://signe/piece"
            queries.get_identity_document_preview_url.return_value = (
                "https://signe/apercu"
            )
            reponse = TestClient(app).get(
                f"/api/employees/{employee_id}/identity-document"
            )
        return reponse, queries, providers
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_rh_ne_lit_pas_la_piece_d_un_salarie_d_une_autre_societe():
    reponse, queries, _ = _get(_user("rh"), SALARIE, SOCIETE_B)
    # 404 comme require_employee_access : l'existence n'est pas révélée.
    assert reponse.status_code == 404
    queries.get_identity_document_url.assert_not_called()
    queries.get_identity_document_preview_url.assert_not_called()


def test_salarie_introuvable_refuse_aussi():
    reponse, queries, _ = _get(_user("rh"), SALARIE, None)
    assert reponse.status_code == 404
    queries.get_identity_document_url.assert_not_called()


def test_rh_lit_la_piece_d_un_salarie_de_sa_societe():
    reponse, queries, _ = _get(_user("rh"), SALARIE, SOCIETE_A)
    assert reponse.status_code == 200
    assert reponse.json() == {
        "url": "https://signe/piece",
        "preview_url": "https://signe/apercu",
    }
    queries.get_identity_document_url.assert_called_once_with(SALARIE)


def test_sa_propre_fiche_reste_accessible():
    """Chemin « sa propre fiche » : inchangé, sans contrôle supplémentaire."""
    reponse, queries, providers = _get(_user("collaborateur"), COMPTE, SOCIETE_B)
    assert reponse.status_code == 200
    queries.get_identity_document_url.assert_called_once_with(COMPTE)
    providers.get_employee_company_id.assert_not_called()


def test_collaborateur_ne_lit_pas_la_piece_d_un_collegue():
    reponse, queries, _ = _get(_user("collaborateur"), SALARIE, SOCIETE_A)
    assert reponse.status_code == 403
    queries.get_identity_document_url.assert_not_called()


def test_platform_admin_garde_son_acces_transverse():
    reponse, queries, _ = _get(_user(platform_admin=True), SALARIE, SOCIETE_B)
    assert reponse.status_code == 200
    queries.get_identity_document_url.assert_called_once_with(SALARIE)
