"""
Task 2 (lien d'activation) : endpoints publics /api/activation/*.

Tout passe par les VRAIS points d'entrée HTTP, sans authentification.
Le même message d'erreur générique couvre tous les cas d'échec de jeton
(pas d'énumération). Supabase moqué aux frontières infrastructure.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from fastapi.testclient import TestClient

COMPANY_ID = "550e8400-e29b-41d4-a716-446655440000"
EMPLOYEE_ID = "770e8400-e29b-41d4-a716-446655440099"
AUTH_UID = "990e8400-e29b-41d4-a716-446655440555"

RAW_TOKEN = "jeton-de-test-suffisamment-long-0123456789abcdef"
TOKEN_HASH = hashlib.sha256(RAW_TOKEN.encode("utf-8")).hexdigest()

MESSAGE_GENERIQUE = "Lien invalide ou expiré"


def _token_row(**overrides) -> dict:
    row = {
        "id": "aa0e8400-e29b-41d4-a716-446655440111",
        "employee_id": EMPLOYEE_ID,
        "company_id": COMPANY_ID,
        "token_hash": TOKEN_HASH,
        "email_envoye": "jean.dupont@exemple.fr",
        "expires_at": (
            datetime.now(timezone.utc) + timedelta(days=3)
        ).isoformat(),
        "used_at": None,
        "invalidated_at": None,
    }
    row.update(overrides)
    return row


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


def _patches():
    return (
        patch("app.modules.activation.application.commands._token_repository"),
        patch("app.modules.activation.application.commands.providers"),
    )


class TestVerify:
    def test_jeton_valide_200_prenom_societe(self, client: TestClient):
        p_repo, p_prov = _patches()
        with p_repo as repo, p_prov as prov:
            repo.get_by_hash.return_value = _token_row()
            prov.get_employee_for_activation.return_value = _employee()
            prov.get_company_name.return_value = "Entreprise Test"
            response = client.post(
                "/api/activation/verify", json={"token": RAW_TOKEN}
            )
        assert response.status_code == 200, response.text
        assert response.json() == {"prenom": "Jean", "societe": "Entreprise Test"}

    def test_verify_sans_auth_ni_donnee_sensible(self, client: TestClient):
        p_repo, p_prov = _patches()
        with p_repo as repo, p_prov as prov:
            repo.get_by_hash.return_value = _token_row()
            prov.get_employee_for_activation.return_value = _employee()
            prov.get_company_name.return_value = "Entreprise Test"
            response = client.post(
                "/api/activation/verify", json={"token": RAW_TOKEN}
            )
        body = response.json()
        # Rien d'autre que prénom + société : ni e-mail, ni nom, ni ids.
        assert set(body.keys()) == {"prenom", "societe"}
        lower = response.text.lower()
        assert "supabase" not in lower
        assert EMPLOYEE_ID not in response.text

    def test_jeton_inconnu_expire_utilise_invalide_meme_message(
        self, client: TestClient
    ):
        cas = {
            "inconnu": None,
            "expire": _token_row(
                expires_at=(
                    datetime.now(timezone.utc) - timedelta(hours=1)
                ).isoformat()
            ),
            "utilise": _token_row(
                used_at=datetime.now(timezone.utc).isoformat()
            ),
            "invalide": _token_row(
                invalidated_at=datetime.now(timezone.utc).isoformat()
            ),
        }
        details = set()
        for nom, row in cas.items():
            p_repo, p_prov = _patches()
            with p_repo as repo, p_prov as prov:
                repo.get_by_hash.return_value = row
                prov.get_employee_for_activation.return_value = _employee()
                prov.get_company_name.return_value = "Entreprise Test"
                response = client.post(
                    "/api/activation/verify", json={"token": RAW_TOKEN}
                )
            assert response.status_code == 400, f"cas {nom} : {response.text}"
            details.add(response.json()["detail"])
        # Un seul et même message pour TOUS les cas.
        assert details == {MESSAGE_GENERIQUE}


class TestComplete:
    def _happy_patches(self, employee=None):
        p_repo, p_prov = _patches()
        repo = p_repo.start()
        prov = p_prov.start()
        repo.get_by_hash.return_value = _token_row()
        prov.get_employee_for_activation.return_value = employee or _employee()
        prov.get_company_name.return_value = "Entreprise Test"
        prov.create_auth_user.return_value = AUTH_UID
        return repo, prov, (p_repo, p_prov)

    def _stop(self, patches):
        for p in patches:
            p.stop()

    def test_compte_absent_cree_et_cable(self, client: TestClient):
        repo, prov, patches = self._happy_patches()
        try:
            response = client.post(
                "/api/activation/complete",
                json={"token": RAW_TOKEN, "password": "MotDePasse!2026"},
            )
        finally:
            self._stop(patches)

        assert response.status_code == 200, response.text
        prov.create_auth_user.assert_called_once_with(
            "jean.dupont@exemple.fr", "MotDePasse!2026"
        )
        prov.update_auth_user_password.assert_not_called()
        # Câblage salarié : profil, accès société, lien employees.user_id.
        prov.ensure_profile.assert_called_once()
        assert prov.ensure_profile.call_args.args[0] == AUTH_UID
        prov.ensure_company_access.assert_called_once_with(AUTH_UID, COMPANY_ID)
        prov.link_employee_to_user.assert_called_once_with(EMPLOYEE_ID, AUTH_UID)
        # Jeton consommé.
        repo.mark_used.assert_called_once()
        lower = response.text.lower()
        assert "supabase" not in lower

    def test_compte_deja_lie_update_password_sans_create(self, client: TestClient):
        """Seul le compte DÉJÀ lié à la fiche (employees.user_id) peut voir
        son mot de passe mis à jour — jamais un compte trouvé par e-mail."""
        repo, prov, patches = self._happy_patches(
            employee=_employee(user_id=AUTH_UID)
        )
        try:
            response = client.post(
                "/api/activation/complete",
                json={"token": RAW_TOKEN, "password": "MotDePasse!2026"},
            )
        finally:
            self._stop(patches)

        assert response.status_code == 200, response.text
        prov.create_auth_user.assert_not_called()
        prov.update_auth_user_password.assert_called_once_with(
            AUTH_UID, "MotDePasse!2026"
        )
        prov.link_employee_to_user.assert_called_once_with(EMPLOYEE_ID, AUTH_UID)
        repo.mark_used.assert_called_once()

    def test_mot_de_passe_trop_court_422_sans_effet(self, client: TestClient):
        repo, prov, patches = self._happy_patches()
        try:
            response = client.post(
                "/api/activation/complete",
                json={"token": RAW_TOKEN, "password": "court"},
            )
        finally:
            self._stop(patches)

        assert response.status_code == 422
        assert response.json()["detail"]["code"] == "mot_de_passe_invalide"
        prov.create_auth_user.assert_not_called()
        prov.link_employee_to_user.assert_not_called()
        repo.mark_used.assert_not_called()

    def test_second_complete_meme_jeton_400_generique(self, client: TestClient):
        repo, prov, patches = self._happy_patches()
        try:
            # Le premier passage consomme le jeton…
            first = client.post(
                "/api/activation/complete",
                json={"token": RAW_TOKEN, "password": "MotDePasse!2026"},
            )
            # …le second retrouve un jeton marqué utilisé.
            repo.get_by_hash.return_value = _token_row(
                used_at=datetime.now(timezone.utc).isoformat()
            )
            second = client.post(
                "/api/activation/complete",
                json={"token": RAW_TOKEN, "password": "MotDePasse!2026"},
            )
        finally:
            self._stop(patches)

        assert first.status_code == 200
        assert second.status_code == 400
        assert second.json()["detail"] == MESSAGE_GENERIQUE
        # Un seul câblage, pas deux.
        prov.link_employee_to_user.assert_called_once()

    def test_jeton_expire_400_generique_sans_effet(self, client: TestClient):
        p_repo, p_prov = _patches()
        with p_repo as repo, p_prov as prov:
            repo.get_by_hash.return_value = _token_row(
                expires_at=(
                    datetime.now(timezone.utc) - timedelta(hours=1)
                ).isoformat()
            )
            prov.get_employee_for_activation.return_value = _employee()
            response = client.post(
                "/api/activation/complete",
                json={"token": RAW_TOKEN, "password": "MotDePasse!2026"},
            )
        assert response.status_code == 400
        assert response.json()["detail"] == MESSAGE_GENERIQUE
        prov.create_auth_user.assert_not_called()
        prov.link_employee_to_user.assert_not_called()
        repo.mark_used.assert_not_called()
