"""
Justificatifs de notes de frais : URL signée au lieu du bucket public.

Audit Axe A : le bucket `expense_receipts` est PUBLIC et le frontend
construisait lui-même l'URL publique — n'importe qui connaissant le chemin
téléchargeait le justificatif (achats personnels, adresses, identités).
Le bucket ne peut être fermé qu'une fois cette route en place.
"""

from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from app.core.security import get_current_user
from app.main import app
from app.modules.users.schemas.responses import CompanyAccess, User

SOCIETE = "11111111-1111-1111-1111-111111111111"
CHEMIN = "salarie-42/2026-05/ticket.pdf"
URL = f"/api/expenses/receipt-url?path={CHEMIN}"


def _user(role: str = "rh") -> User:
    return User(
        id="22222222-2222-2222-2222-222222222222",
        email="rh@entreprise.fr",
        first_name="Rita",
        last_name="Aitch",
        is_platform_admin=False,
        is_group_admin=False,
        accessible_companies=[
            CompanyAccess(
                company_id=SOCIETE,
                company_name="Entreprise",
                role=role,
                is_primary=True,
            ),
        ],
        active_company_id=SOCIETE,
    )


def _teardown():
    app.dependency_overrides.pop(get_current_user, None)


class TestUrlSigneeJustificatif:
    def test_sans_jeton_refuse(self):
        assert TestClient(app).get(URL).status_code in (401, 403)

    def test_rh_obtient_une_url_signee(self):
        app.dependency_overrides[get_current_user] = lambda: _user()
        try:
            with patch(
                "app.modules.expenses.application.queries.ExpenseStorageProvider"
            ) as provider:
                provider.return_value.create_signed_urls.return_value = [
                    {"path": CHEMIN, "signedURL": "https://signe/xyz"}
                ]
                reponse = TestClient(app).get(URL)

            assert reponse.status_code == 200
            assert reponse.json()["url"] == "https://signe/xyz"
            provider.return_value.create_signed_urls.assert_called_once()
        finally:
            _teardown()

    def test_collaborateur_refuse(self):
        """Écran RH : un simple salarié n'ouvre pas les justificatifs des autres."""
        app.dependency_overrides[get_current_user] = lambda: _user("collaborateur")
        try:
            with patch(
                "app.modules.expenses.application.queries.ExpenseStorageProvider"
            ) as provider:
                reponse = TestClient(app).get(URL)
            assert reponse.status_code == 403
            provider.assert_not_called()
        finally:
            _teardown()

    def test_chemin_hors_bucket_refuse(self):
        """Pas de remontée d'arborescence via le paramètre `path`."""
        app.dependency_overrides[get_current_user] = lambda: _user()
        try:
            with patch(
                "app.modules.expenses.application.queries.ExpenseStorageProvider"
            ) as provider:
                reponse = TestClient(app).get(
                    "/api/expenses/receipt-url?path=../payslips/secret.pdf"
                )
            assert reponse.status_code == 400
            provider.assert_not_called()
        finally:
            _teardown()


class TestSocieteActiveManquante:
    """Compte sans société active (ex. administrateur plateforme) : les
    routes doivent répondre 403, pas 500 en laissant fuir une erreur SQL
    (« invalid input syntax for type uuid: "None" » observé en réel)."""

    def _sans_societe(self) -> User:
        return User(
            id="33333333-3333-3333-3333-333333333333",
            email="admin@eywai.fr",
            first_name="Admin",
            last_name="Plateforme",
            is_platform_admin=False,
            is_group_admin=False,
            accessible_companies=[],
            active_company_id=None,
        )

    def test_liste_des_notes_de_frais_403_et_non_500(self):
        app.dependency_overrides[get_current_user] = self._sans_societe
        try:
            reponse = TestClient(app).get("/api/expenses/")
            assert reponse.status_code == 403
            assert "uuid" not in reponse.text.lower()
        finally:
            _teardown()
