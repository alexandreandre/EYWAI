"""
Task 2 (lien d'activation) : routes RH d'invitation.

Tout passe par les VRAIS points d'entrée HTTP (TestClient sur app.main.app).
Supabase est moqué aux frontières infrastructure (repository / providers /
e-mail) — jamais deux fonctions dont l'interaction est le sujet.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.core.security import get_current_user
from app.main import app
from app.modules.users.schemas.responses import CompanyAccess, User

COMPANY_ID = "550e8400-e29b-41d4-a716-446655440000"
OTHER_COMPANY_ID = "550e8400-e29b-41d4-a716-446655449999"
RH_USER_ID = "660e8400-e29b-41d4-a716-446655440001"
EMPLOYEE_ID = "770e8400-e29b-41d4-a716-446655440099"

INVITE_URL = f"/api/employees/{EMPLOYEE_ID}/invitation"


def _user(role: str) -> User:
    return User(
        id=RH_USER_ID,
        email="rh@entreprise.fr",
        first_name="Rita",
        last_name="Aitch",
        is_platform_admin=False,
        is_group_admin=False,
        accessible_companies=[
            CompanyAccess(
                company_id=COMPANY_ID,
                company_name="Entreprise Test",
                role=role,
                is_primary=True,
            ),
        ],
        active_company_id=COMPANY_ID,
    )


def _employee(**overrides) -> dict:
    row = {
        "id": EMPLOYEE_ID,
        "company_id": COMPANY_ID,
        "first_name": "Jean",
        "last_name": "Dupont",
        "email": "jean.dupont@exemple.fr",
        "employment_status": "actif",
        "user_id": None,
        "job_title": "Technicien",
    }
    row.update(overrides)
    return row


def _as(role: str):
    app.dependency_overrides[get_current_user] = lambda: _user(role)


def _teardown():
    app.dependency_overrides.pop(get_current_user, None)


def _patches():
    return (
        patch("app.modules.activation.application.commands._token_repository"),
        patch("app.modules.activation.application.commands.providers"),
        patch("app.modules.activation.application.commands.activation_email"),
    )


class TestInvitationRhAcces:
    def test_collaborateur_sans_profil_rh_403(self, client: TestClient):
        _as("collaborateur")
        try:
            p_repo, p_prov, p_mail = _patches()
            with p_repo, p_prov as prov, p_mail as mail:
                prov.get_employee_for_activation.return_value = _employee()
                response = client.post(INVITE_URL)
        finally:
            _teardown()
        assert response.status_code == 403
        mail.send_activation_email.assert_not_called()

    def test_salarie_autre_societe_404(self, client: TestClient):
        _as("rh")
        try:
            p_repo, p_prov, p_mail = _patches()
            with p_repo, p_prov as prov, p_mail as mail:
                prov.get_employee_for_activation.return_value = _employee(
                    company_id=OTHER_COMPANY_ID
                )
                response = client.post(INVITE_URL)
        finally:
            _teardown()
        assert response.status_code == 404
        mail.send_activation_email.assert_not_called()


class TestInvitationRhGardesEmail:
    def test_email_vide_422_code_email_manquant(self, client: TestClient):
        _as("rh")
        try:
            p_repo, p_prov, p_mail = _patches()
            with p_repo as repo, p_prov as prov, p_mail as mail:
                prov.get_employee_for_activation.return_value = _employee(email="")
                response = client.post(INVITE_URL)
        finally:
            _teardown()
        assert response.status_code == 422
        assert response.json()["detail"]["code"] == "email_manquant"
        repo.create.assert_not_called()
        mail.send_activation_email.assert_not_called()

    def test_email_fabrique_422_code_email_manquant(self, client: TestClient):
        _as("rh")
        try:
            p_repo, p_prov, p_mail = _patches()
            with p_repo as repo, p_prov as prov, p_mail as mail:
                prov.get_employee_for_activation.return_value = _employee(
                    email="import.jdupont@dsn-import.eywai.fr"
                )
                response = client.post(INVITE_URL)
        finally:
            _teardown()
        assert response.status_code == 422
        assert response.json()["detail"]["code"] == "email_manquant"
        repo.create.assert_not_called()
        mail.send_activation_email.assert_not_called()

    def test_salarie_inactif_422(self, client: TestClient):
        _as("rh")
        try:
            p_repo, p_prov, p_mail = _patches()
            with p_repo as repo, p_prov as prov, p_mail as mail:
                prov.get_employee_for_activation.return_value = _employee(
                    employment_status="sorti"
                )
                response = client.post(INVITE_URL)
        finally:
            _teardown()
        assert response.status_code == 422
        assert response.json()["detail"]["code"] == "salarie_inactif"
        repo.create.assert_not_called()
        mail.send_activation_email.assert_not_called()


class TestInvitationRhSucces:
    def test_jeton_hache_stocke_et_email_envoye(self, client: TestClient):
        _as("rh")
        try:
            p_repo, p_prov, p_mail = _patches()
            with p_repo as repo, p_prov as prov, p_mail as mail:
                prov.get_employee_for_activation.return_value = _employee()
                prov.get_company_name.return_value = "Entreprise Test"
                mail.send_activation_email.return_value = True
                response = client.post(INVITE_URL)
        finally:
            _teardown()

        assert response.status_code == 200, response.text

        # Les jetons antérieurs meurent AVANT la création du nouveau.
        repo.invalidate_pending.assert_called_once()
        repo.create.assert_called_once()
        created = repo.create.call_args.kwargs

        # L'e-mail part avec le jeton en CLAIR ; la base ne voit que le sha256.
        mail.send_activation_email.assert_called_once()
        sent = mail.send_activation_email.call_args.kwargs
        raw_token = sent["raw_token"]
        assert len(raw_token) >= 32
        assert (
            created["token_hash"]
            == hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
        )
        assert created["employee_id"] == EMPLOYEE_ID
        assert created["company_id"] == COMPANY_ID
        assert created["email_envoye"] == "jean.dupont@exemple.fr"
        assert created["created_by"] == RH_USER_ID

        # Expiration à +7 jours.
        expires_at = datetime.fromisoformat(created["expires_at"])
        delta = expires_at - datetime.now(timezone.utc)
        assert timedelta(days=6, hours=23) < delta < timedelta(days=7, hours=1)

        # La réponse expose l'e-mail MASQUÉ et jamais le jeton en clair.
        body = response.json()
        assert body["email"] == "j***@exemple.fr"
        assert raw_token not in response.text
        assert body["invited_at"]
        assert body["expires_at"]

    def test_reenvoi_meme_commande_invalide_les_anciens(self, client: TestClient):
        _as("rh")
        try:
            p_repo, p_prov, p_mail = _patches()
            with p_repo as repo, p_prov as prov, p_mail as mail:
                prov.get_employee_for_activation.return_value = _employee()
                prov.get_company_name.return_value = "Entreprise Test"
                mail.send_activation_email.return_value = True
                first = client.post(INVITE_URL)
                second = client.post(INVITE_URL)
        finally:
            _teardown()

        assert first.status_code == 200
        assert second.status_code == 200
        assert repo.invalidate_pending.call_count == 2
        assert repo.create.call_count == 2
        # Deux jetons distincts.
        hashes = [c.kwargs["token_hash"] for c in repo.create.call_args_list]
        assert hashes[0] != hashes[1]


class TestEtatInvitation:
    def test_jamais_invite(self, client: TestClient):
        _as("rh")
        try:
            with (
                patch(
                    "app.modules.activation.application.queries._token_repository"
                ) as repo,
                patch(
                    "app.modules.activation.application.queries.providers"
                ) as prov,
            ):
                prov.get_employee_for_activation.return_value = _employee()
                repo.get_latest_for_employee.return_value = None
                response = client.get(INVITE_URL)
        finally:
            _teardown()
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "jamais_invite"

    def test_invite_avec_jeton_vivant(self, client: TestClient):
        _as("rh")
        expires = (datetime.now(timezone.utc) + timedelta(days=3)).isoformat()
        created = (datetime.now(timezone.utc) - timedelta(days=4)).isoformat()
        try:
            with (
                patch(
                    "app.modules.activation.application.queries._token_repository"
                ) as repo,
                patch(
                    "app.modules.activation.application.queries.providers"
                ) as prov,
            ):
                prov.get_employee_for_activation.return_value = _employee()
                repo.get_latest_for_employee.return_value = {
                    "created_at": created,
                    "expires_at": expires,
                    "used_at": None,
                    "invalidated_at": None,
                    "email_envoye": "jean.dupont@exemple.fr",
                }
                response = client.get(INVITE_URL)
        finally:
            _teardown()
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "invite"
        assert body["expired"] is False
        assert body["invited_at"] == created
        # E-mail masqué, jamais l'adresse complète.
        assert body["email"] == "j***@exemple.fr"

    def test_invite_jeton_expire(self, client: TestClient):
        _as("rh")
        expires = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        created = (datetime.now(timezone.utc) - timedelta(days=8)).isoformat()
        try:
            with (
                patch(
                    "app.modules.activation.application.queries._token_repository"
                ) as repo,
                patch(
                    "app.modules.activation.application.queries.providers"
                ) as prov,
            ):
                prov.get_employee_for_activation.return_value = _employee()
                repo.get_latest_for_employee.return_value = {
                    "created_at": created,
                    "expires_at": expires,
                    "used_at": None,
                    "invalidated_at": None,
                    "email_envoye": "jean.dupont@exemple.fr",
                }
                response = client.get(INVITE_URL)
        finally:
            _teardown()
        assert response.status_code == 200
        assert response.json()["status"] == "invite"
        assert response.json()["expired"] is True

    def test_active_quand_fiche_liee_a_un_compte(self, client: TestClient):
        _as("rh")
        try:
            with (
                patch(
                    "app.modules.activation.application.queries._token_repository"
                ) as repo,
                patch(
                    "app.modules.activation.application.queries.providers"
                ) as prov,
            ):
                prov.get_employee_for_activation.return_value = _employee(
                    user_id="880e8400-e29b-41d4-a716-446655440777"
                )
                repo.get_latest_for_employee.return_value = None
                response = client.get(INVITE_URL)
        finally:
            _teardown()
        assert response.status_code == 200
        assert response.json()["status"] == "active"

    def test_etat_403_sans_profil_rh(self, client: TestClient):
        _as("collaborateur")
        try:
            with (
                patch(
                    "app.modules.activation.application.queries._token_repository"
                ),
                patch(
                    "app.modules.activation.application.queries.providers"
                ),
            ):
                response = client.get(INVITE_URL)
        finally:
            _teardown()
        assert response.status_code == 403
