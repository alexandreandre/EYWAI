"""
Durcissement sécurité du lien d'activation (revue adversariale 21-22/08).

Failles couvertes :
- S1 : jeton brut dans la boîte de redirection (EMAIL_FORCE_REDIRECT_TO) —
  l'invitation doit être REFUSÉE si le destinataire n'est pas allowlisté.
- S2 : détournement de compte — complete_activation ne doit JAMAIS écraser le
  mot de passe d'un compte auth trouvé par simple correspondance d'e-mail.
- S3 : ré-invitation d'un salarié déjà activé (user_id posé) → refus.
- S4 : politique de mot de passe serveur alignée sur le front (4 règles).
- S6 : échec d'envoi → aucun jeton persisté (les anciens restent vivants).
- S7 : statuts actifs multiples (actif / active / en_onboarding) invitables.

Tout passe par les VRAIS points d'entrée HTTP (TestClient sur app.main.app).
"""

from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from app.core.security import get_current_user
from app.main import app
from app.modules.users.schemas.responses import CompanyAccess, User

COMPANY_ID = "550e8400-e29b-41d4-a716-446655440000"
RH_USER_ID = "660e8400-e29b-41d4-a716-446655440001"
EMPLOYEE_ID = "770e8400-e29b-41d4-a716-446655440099"
LINKED_UID = "880e8400-e29b-41d4-a716-446655440777"

INVITE_URL = f"/api/employees/{EMPLOYEE_ID}/invitation"
COMPLETE_URL = "/api/activation/complete"


def _user() -> User:
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
                role="rh",
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


def _as_rh():
    app.dependency_overrides[get_current_user] = lambda: _user()


def _teardown():
    app.dependency_overrides.pop(get_current_user, None)


def _token_row(**overrides) -> dict:
    from datetime import datetime, timedelta, timezone

    from app.modules.activation.domain.rules import hash_activation_token

    row = {
        "id": "990e8400-e29b-41d4-a716-446655440111",
        "employee_id": EMPLOYEE_ID,
        "company_id": COMPANY_ID,
        "token_hash": hash_activation_token("jeton-test"),
        "email_envoye": "jean.dupont@exemple.fr",
        "expires_at": (
            datetime.now(timezone.utc) + timedelta(days=3)
        ).isoformat(),
        "used_at": None,
        "invalidated_at": None,
    }
    row.update(overrides)
    return row


VALID_PASSWORD = "Motdepasse1"


# ----- S1 : refus d'invitation quand le jeton partirait dans la boîte redirigée -----


class TestRedirectionBloqueInvitation:
    def test_redirect_actif_hors_allowlist_refuse_sans_jeton(self):
        _as_rh()
        try:
            with (
                patch(
                    "app.modules.activation.application.commands._token_repository"
                ) as repo,
                patch(
                    "app.modules.activation.application.commands.providers"
                ) as providers,
                patch(
                    "app.modules.activation.application.commands.activation_email"
                ) as mail,
                patch(
                    "app.core.settings.EMAIL_FORCE_REDIRECT_TO",
                    "boite-interne@eywai.fr",
                ),
                patch("app.core.settings.ACTIVATION_EMAIL_ALLOWLIST", ""),
            ):
                providers.get_employee_for_activation.return_value = _employee()
                resp = TestClient(app).post(INVITE_URL)

                assert resp.status_code == 422
                assert (
                    resp.json()["detail"]["code"] == "envoi_direct_non_autorise"
                )
                repo.create.assert_not_called()
                repo.invalidate_pending.assert_not_called()
                mail.send_activation_email.assert_not_called()
        finally:
            _teardown()

    def test_redirect_actif_adresse_allowlistee_part(self):
        _as_rh()
        try:
            with (
                patch(
                    "app.modules.activation.application.commands._token_repository"
                ) as repo,
                patch(
                    "app.modules.activation.application.commands.providers"
                ) as providers,
                patch(
                    "app.modules.activation.application.commands.activation_email"
                ) as mail,
                patch(
                    "app.core.settings.EMAIL_FORCE_REDIRECT_TO",
                    "boite-interne@eywai.fr",
                ),
                patch(
                    "app.core.settings.ACTIVATION_EMAIL_ALLOWLIST",
                    "Jean.Dupont@exemple.fr",
                ),
            ):
                providers.get_employee_for_activation.return_value = _employee()
                providers.get_company_name.return_value = "Entreprise Test"
                mail.send_activation_email.return_value = True
                resp = TestClient(app).post(INVITE_URL)

                assert resp.status_code == 200
                mail.send_activation_email.assert_called_once()
                repo.create.assert_called_once()
        finally:
            _teardown()

    def test_sans_redirect_invitation_part_normalement(self):
        _as_rh()
        try:
            with (
                patch(
                    "app.modules.activation.application.commands._token_repository"
                ) as repo,
                patch(
                    "app.modules.activation.application.commands.providers"
                ) as providers,
                patch(
                    "app.modules.activation.application.commands.activation_email"
                ) as mail,
                patch("app.core.settings.EMAIL_FORCE_REDIRECT_TO", None),
                patch("app.core.settings.ACTIVATION_EMAIL_ALLOWLIST", ""),
            ):
                providers.get_employee_for_activation.return_value = _employee()
                providers.get_company_name.return_value = "Entreprise Test"
                mail.send_activation_email.return_value = True
                resp = TestClient(app).post(INVITE_URL)

                assert resp.status_code == 200
                repo.create.assert_called_once()
        finally:
            _teardown()


# ----- S3 : salarié déjà activé -----


class TestDejaActive:
    def test_user_id_pose_refuse_la_reinvitation(self):
        _as_rh()
        try:
            with (
                patch(
                    "app.modules.activation.application.commands._token_repository"
                ) as repo,
                patch(
                    "app.modules.activation.application.commands.providers"
                ) as providers,
                patch(
                    "app.modules.activation.application.commands.activation_email"
                ) as mail,
                patch("app.core.settings.EMAIL_FORCE_REDIRECT_TO", None),
            ):
                providers.get_employee_for_activation.return_value = _employee(
                    user_id=LINKED_UID
                )
                resp = TestClient(app).post(INVITE_URL)

                assert resp.status_code == 409
                assert resp.json()["detail"]["code"] == "deja_active"
                repo.create.assert_not_called()
                mail.send_activation_email.assert_not_called()
        finally:
            _teardown()


# ----- S7 : statuts actifs multiples -----


class TestStatutsInvitables:
    def _invite_avec_statut(self, statut: str) -> int:
        _as_rh()
        try:
            with (
                patch(
                    "app.modules.activation.application.commands._token_repository"
                ),
                patch(
                    "app.modules.activation.application.commands.providers"
                ) as providers,
                patch(
                    "app.modules.activation.application.commands.activation_email"
                ) as mail,
                patch("app.core.settings.EMAIL_FORCE_REDIRECT_TO", None),
            ):
                providers.get_employee_for_activation.return_value = _employee(
                    employment_status=statut
                )
                providers.get_company_name.return_value = "Entreprise Test"
                mail.send_activation_email.return_value = True
                return TestClient(app).post(INVITE_URL).status_code
        finally:
            _teardown()

    def test_actif_active_en_onboarding_sont_invitables(self):
        assert self._invite_avec_statut("actif") == 200
        assert self._invite_avec_statut("active") == 200
        assert self._invite_avec_statut("en_onboarding") == 200

    def test_sorti_reste_refuse(self):
        assert self._invite_avec_statut("sorti") == 422


# ----- S6 : échec d'envoi → aucun jeton persisté -----


class TestEchecEnvoiSansJeton:
    def test_envoi_echoue_ne_persiste_rien(self):
        _as_rh()
        try:
            with (
                patch(
                    "app.modules.activation.application.commands._token_repository"
                ) as repo,
                patch(
                    "app.modules.activation.application.commands.providers"
                ) as providers,
                patch(
                    "app.modules.activation.application.commands.activation_email"
                ) as mail,
                patch("app.core.settings.EMAIL_FORCE_REDIRECT_TO", None),
            ):
                providers.get_employee_for_activation.return_value = _employee()
                providers.get_company_name.return_value = "Entreprise Test"
                mail.send_activation_email.return_value = False
                resp = TestClient(app).post(INVITE_URL)

                assert resp.status_code == 502
                # L'envoi a échoué AVANT toute écriture : les anciens jetons
                # restent vivants, aucun jeton fantôme n'est créé.
                repo.create.assert_not_called()
                repo.invalidate_pending.assert_not_called()
        finally:
            _teardown()


# ----- S2 : anti-détournement de compte à l'activation -----


class TestAntiDetournementCompte:
    def test_email_deja_utilise_par_un_autre_compte_refus_generique(self):
        """Un compte auth existant NON lié à ce salarié ne doit JAMAIS voir
        son mot de passe écrasé (l'e-mail seul ne prouve rien)."""
        from app.modules.activation.infrastructure.providers import (
            EmailAlreadyRegisteredError,
        )

        with (
            patch(
                "app.modules.activation.application.commands._token_repository"
            ) as repo,
            patch(
                "app.modules.activation.application.commands.providers"
            ) as providers,
        ):
            repo.get_by_hash.return_value = _token_row()
            providers.get_employee_for_activation.return_value = _employee()
            providers.create_auth_user.side_effect = EmailAlreadyRegisteredError(
                "existe déjà"
            )
            resp = TestClient(app).post(
                COMPLETE_URL,
                json={"token": "jeton-test", "password": VALID_PASSWORD},
            )

            assert resp.status_code == 400
            providers.update_auth_user_password.assert_not_called()
            providers.ensure_profile.assert_not_called()
            providers.ensure_company_access.assert_not_called()
            providers.link_employee_to_user.assert_not_called()
            repo.mark_used.assert_not_called()

    def test_salarie_deja_lie_met_a_jour_ce_compte_uniquement(self):
        """user_id déjà posé → mise à jour du mot de passe de CE compte,
        sans aucune recherche par e-mail."""
        with (
            patch(
                "app.modules.activation.application.commands._token_repository"
            ) as repo,
            patch(
                "app.modules.activation.application.commands.providers"
            ) as providers,
        ):
            repo.get_by_hash.return_value = _token_row()
            providers.get_employee_for_activation.return_value = _employee(
                user_id=LINKED_UID
            )
            resp = TestClient(app).post(
                COMPLETE_URL,
                json={"token": "jeton-test", "password": VALID_PASSWORD},
            )

            assert resp.status_code == 200
            providers.update_auth_user_password.assert_called_once_with(
                LINKED_UID, VALID_PASSWORD, email=None
            )
            providers.create_auth_user.assert_not_called()
            repo.mark_used.assert_called_once()

    def test_flux_nominal_cree_le_compte_directement(self):
        """Pas de compte lié → création directe (jamais de scan list_users)."""
        with (
            patch(
                "app.modules.activation.application.commands._token_repository"
            ) as repo,
            patch(
                "app.modules.activation.application.commands.providers"
            ) as providers,
        ):
            repo.get_by_hash.return_value = _token_row()
            providers.get_employee_for_activation.return_value = _employee()
            providers.create_auth_user.return_value = "nouveau-uid"
            resp = TestClient(app).post(
                COMPLETE_URL,
                json={"token": "jeton-test", "password": VALID_PASSWORD},
            )

            assert resp.status_code == 200
            providers.create_auth_user.assert_called_once()
            providers.update_auth_user_password.assert_not_called()
            providers.link_employee_to_user.assert_called_once_with(
                EMPLOYEE_ID, "nouveau-uid"
            )


# ----- S4 : politique de mot de passe serveur = celle du front -----


class TestPolitiqueMotDePasse:
    def _complete(self, password: str) -> int:
        with (
            patch(
                "app.modules.activation.application.commands._token_repository"
            ) as repo,
            patch(
                "app.modules.activation.application.commands.providers"
            ) as providers,
        ):
            repo.get_by_hash.return_value = _token_row()
            providers.get_employee_for_activation.return_value = _employee()
            providers.create_auth_user.return_value = "nouveau-uid"
            return (
                TestClient(app)
                .post(
                    COMPLETE_URL,
                    json={"token": "jeton-test", "password": password},
                )
                .status_code
            )

    def test_minuscules_seules_refusees(self):
        assert self._complete("aaaaaaaa") == 422

    def test_sans_chiffre_refuse(self):
        assert self._complete("Aaaaaaaa") == 422

    def test_sans_majuscule_refuse(self):
        assert self._complete("aaaaaaa1") == 422

    def test_trop_court_refuse(self):
        assert self._complete("Aa1") == 422

    def test_conforme_accepte(self):
        assert self._complete("Motdepasse1") == 200


# ----- Raffinement S3 : comptes placeholder DSN ré-invitables -----
#
# ~227 des 245 salariés actifs portent un compte auth créé par l'import DSN
# avec une adresse FABRIQUÉE (jamais utilisable par le salarié). Refuser leur
# invitation rendrait le module inerte. Règle : compte lié à adresse réelle →
# refus (protection takeover) ; compte lié à adresse fabriquée → invitable,
# et le complete bascule l'e-mail auth vers l'adresse vérifiée par le clic.


class TestComptePlaceholderReinvitable:
    def _invite(self, auth_email: str):
        _as_rh()
        try:
            with (
                patch(
                    "app.modules.activation.application.commands._token_repository"
                ) as repo,
                patch(
                    "app.modules.activation.application.commands.providers"
                ) as providers,
                patch(
                    "app.modules.activation.application.commands.activation_email"
                ) as mail,
                patch("app.core.settings.EMAIL_FORCE_REDIRECT_TO", None),
            ):
                providers.get_employee_for_activation.return_value = _employee(
                    user_id=LINKED_UID
                )
                providers.get_auth_user_email.return_value = auth_email
                providers.get_company_name.return_value = "Entreprise Test"
                mail.send_activation_email.return_value = True
                return TestClient(app).post(INVITE_URL), repo, mail
        finally:
            _teardown()

    def test_compte_place_holder_dsn_est_invitable(self):
        resp, repo, mail = self._invite("jean.dupont@951474782.dsn-import.local")
        assert resp.status_code == 200
        mail.send_activation_email.assert_called_once()
        repo.create.assert_called_once()

    def test_compte_adresse_reelle_reste_refuse(self):
        resp, repo, mail = self._invite("jean.dupont@exemple.fr")
        assert resp.status_code == 409
        assert resp.json()["detail"]["code"] == "deja_active"
        mail.send_activation_email.assert_not_called()

    def test_email_auth_illisible_refuse_fail_closed(self):
        resp, repo, mail = self._invite("")
        assert resp.status_code == 409
        mail.send_activation_email.assert_not_called()


class TestCompleteBasculeEmailAuth:
    def _complete(self, auth_email: str):
        with (
            patch(
                "app.modules.activation.application.commands._token_repository"
            ) as repo,
            patch(
                "app.modules.activation.application.commands.providers"
            ) as providers,
        ):
            repo.get_by_hash.return_value = _token_row()
            # Fiche VOLONTAIREMENT différente du jeton : la bascule doit viser
            # email_envoye (prouvée par le clic), jamais l'e-mail de la fiche,
            # que la RH peut avoir changé après l'envoi.
            providers.get_employee_for_activation.return_value = _employee(
                user_id=LINKED_UID, email="fiche.changee.apres@exemple.fr"
            )
            providers.get_auth_user_email.return_value = auth_email
            resp = TestClient(app).post(
                COMPLETE_URL,
                json={"token": "jeton-test", "password": VALID_PASSWORD},
            )
            return resp, providers, repo

    def test_compte_placeholder_recoit_adresse_verifiee_et_mot_de_passe(self):
        resp, providers, repo = self._complete(
            "jean.dupont@951474782.dsn-import.local"
        )
        assert resp.status_code == 200
        # L'e-mail auth bascule vers l'adresse d'ENVOI (prouvée par le clic),
        # jamais vers une autre.
        providers.update_auth_user_password.assert_called_once_with(
            LINKED_UID, VALID_PASSWORD, email="jean.dupont@exemple.fr"
        )
        providers.create_auth_user.assert_not_called()
        repo.mark_used.assert_called_once()

    def test_compte_adresse_reelle_garde_son_email(self):
        resp, providers, repo = self._complete("jean.dupont@exemple.fr")
        assert resp.status_code == 200
        providers.update_auth_user_password.assert_called_once_with(
            LINKED_UID, VALID_PASSWORD, email=None
        )
        repo.mark_used.assert_called_once()


class TestCollisionAdresseDejaPrise:
    """Cas réel (Elsa) : la bascule d'e-mail vise une adresse déjà portée
    par un AUTRE compte auth → refus générique propre, jamais de 500, et
    le jeton reste rejouable une fois la collision résolue."""

    def test_collision_bascule_refus_generique_sans_consommation(self):
        from app.modules.activation.infrastructure.providers import (
            EmailAlreadyRegisteredError,
        )

        with (
            patch(
                "app.modules.activation.application.commands._token_repository"
            ) as repo,
            patch(
                "app.modules.activation.application.commands.providers"
            ) as providers,
        ):
            repo.get_by_hash.return_value = _token_row()
            providers.get_employee_for_activation.return_value = _employee(
                user_id=LINKED_UID
            )
            providers.get_auth_user_email.return_value = (
                "import.x.y.123@951474782.dsn-import.local"
            )
            providers.update_auth_user_password.side_effect = (
                EmailAlreadyRegisteredError("email exists")
            )
            resp = TestClient(app).post(
                COMPLETE_URL,
                json={"token": "jeton-test", "password": VALID_PASSWORD},
            )

            assert resp.status_code == 400
            providers.ensure_profile.assert_not_called()
            providers.link_employee_to_user.assert_not_called()
            repo.mark_used.assert_not_called()
