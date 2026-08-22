"""
Task 3 (lien d'activation) : e-mail d'invitation et levée CIBLÉE du redirect.

L'allowlist est testée À TRAVERS LE VRAI SENDER (SmtpMailSender réel,
_apply_forced_redirect réel) avec EMAIL_FORCE_REDIRECT_TO simulé : seuls la
connexion SMTP et la config résolue sont moqués. AUCUNE connexion réseau.
"""

from __future__ import annotations

from email.message import Message
from unittest.mock import MagicMock, patch

import pytest

from app.modules.activation.infrastructure.email import send_activation_email
from app.modules.platform_settings.domain.value_objects import ResolvedEmailConfig
from app.shared.infrastructure.email.smtp_sender import SmtpMailSender

DESTINATAIRE = "jean.dupont@exemple.fr"
REDIRECT = "redirige@eywai-interne.fr"
RAW_TOKEN = "jeton-en-clair-0123456789"


def _config() -> ResolvedEmailConfig:
    return ResolvedEmailConfig(
        smtp_host="smtp.exemple.fr",
        smtp_port=587,
        smtp_user="expediteur@exemple.fr",
        smtp_password="secret-smtp-de-test",
        smtp_security="starttls",
        from_email="noreply@exemple.fr",
        from_name="EYWAI",
        reply_to=None,
        support_recipients=("contact@exemple.fr",),
        frontend_url="https://app.exemple.fr",
        source="environment",
    )


@pytest.fixture
def sent_messages():
    """Envoie via le VRAI sender ; capture les messages au lieu du réseau."""
    messages: list[Message] = []
    server = MagicMock()
    server.send_message.side_effect = lambda msg: messages.append(msg)
    context = MagicMock()
    context.__enter__ = MagicMock(return_value=server)
    context.__exit__ = MagicMock(return_value=False)
    with (
        patch.object(SmtpMailSender, "_connect", return_value=context),
        patch(
            "app.shared.infrastructure.email.smtp_sender.get_resolved_email_config",
            return_value=_config(),
        ),
    ):
        yield messages


def _send(**overrides) -> bool:
    kwargs = {
        "to_email": DESTINATAIRE,
        "prenom": "Jean",
        "societe": "Entreprise Test",
        "raw_token": RAW_TOKEN,
    }
    kwargs.update(overrides)
    return send_activation_email(**kwargs)


class TestLeveeCibleeRedirect:
    def test_allowlist_envoi_direct_sans_redirect(self, sent_messages):
        with (
            patch("app.core.settings.EMAIL_FORCE_REDIRECT_TO", REDIRECT),
            # Casse différente : la comparaison est casse-insensible.
            patch(
                "app.core.settings.ACTIVATION_EMAIL_ALLOWLIST",
                "Autre@Exemple.fr, Jean.DUPONT@Exemple.FR",
            ),
        ):
            ok = _send()
        assert ok is True
        assert len(sent_messages) == 1
        msg = sent_messages[0]
        assert msg["To"] == DESTINATAIRE
        assert "[dest." not in msg["Subject"]

    def test_hors_allowlist_flux_normal_redirige(self, sent_messages):
        with (
            patch("app.core.settings.EMAIL_FORCE_REDIRECT_TO", REDIRECT),
            patch(
                "app.core.settings.ACTIVATION_EMAIL_ALLOWLIST",
                "autre@exemple.fr",
            ),
        ):
            ok = _send()
        assert ok is True
        msg = sent_messages[0]
        assert msg["To"] == REDIRECT
        assert DESTINATAIRE in msg["Subject"]  # dest. prévu reporté dans le sujet

    def test_allowlist_vide_par_defaut_redirige(self, sent_messages):
        with (
            patch("app.core.settings.EMAIL_FORCE_REDIRECT_TO", REDIRECT),
            patch("app.core.settings.ACTIVATION_EMAIL_ALLOWLIST", ""),
        ):
            ok = _send()
        assert ok is True
        assert sent_messages[0]["To"] == REDIRECT

    def test_sans_redirect_global_envoi_normal(self, sent_messages):
        with (
            patch("app.core.settings.EMAIL_FORCE_REDIRECT_TO", None),
            patch("app.core.settings.ACTIVATION_EMAIL_ALLOWLIST", ""),
        ):
            ok = _send()
        assert ok is True
        assert sent_messages[0]["To"] == DESTINATAIRE


class TestContenuEmail:
    def _payload(self, msg: Message) -> str:
        parts = []
        for part in msg.walk():
            if part.get_content_type() in ("text/plain", "text/html"):
                parts.append(part.get_payload(decode=True).decode("utf-8"))
        return "\n".join(parts)

    def test_lien_frontend_avec_jeton(self, sent_messages):
        with (
            patch("app.core.settings.EMAIL_FORCE_REDIRECT_TO", None),
            patch("app.core.settings.ACTIVATION_EMAIL_ALLOWLIST", ""),
            patch(
                "app.modules.activation.infrastructure.email.settings.FRONTEND_URL",
                "https://app.exemple.fr/",
            ),
        ):
            _send()
        payload = self._payload(sent_messages[0])
        lien = f"https://app.exemple.fr/activation?token={RAW_TOKEN}"
        # Le lien exact figure dans le texte ET le HTML.
        assert payload.count(lien) >= 2

    def test_texte_et_html_sobres_eywai(self, sent_messages):
        with (
            patch("app.core.settings.EMAIL_FORCE_REDIRECT_TO", None),
            patch("app.core.settings.ACTIVATION_EMAIL_ALLOWLIST", ""),
        ):
            _send()
        msg = sent_messages[0]
        payload = self._payload(msg)
        assert "Jean" in payload
        assert "Entreprise Test" in payload
        assert "EYWAI" in payload
        assert "7 jours" in payload
        content_types = [p.get_content_type() for p in msg.walk()]
        assert "text/plain" in content_types
        assert "text/html" in content_types

    def test_jamais_le_mot_supabase(self, sent_messages):
        with (
            patch("app.core.settings.EMAIL_FORCE_REDIRECT_TO", None),
            patch("app.core.settings.ACTIVATION_EMAIL_ALLOWLIST", ""),
        ):
            _send()
        msg = sent_messages[0]
        tout = (msg["Subject"] or "") + self._payload(msg)
        assert "supabase" not in tout.lower()


class TestLeveeValableTousFlux:
    """La levée n'est pas propre à l'activation : un utilisateur de la
    vague 0 doit aussi recevoir son RESET de mot de passe en direct —
    sinon il est joignable à l'invitation mais sourd au reset."""

    def test_reset_password_allowliste_part_en_direct(self, sent_messages):
        with (
            patch("app.core.settings.EMAIL_FORCE_REDIRECT_TO", REDIRECT),
            patch(
                "app.core.settings.ACTIVATION_EMAIL_ALLOWLIST",
                DESTINATAIRE,
            ),
        ):
            ok = SmtpMailSender().send_password_reset_email(
                to_email=DESTINATAIRE,
                reset_token="jeton-reset-0123",
                user_name="Jean",
            )
        assert ok is True
        assert sent_messages[0]["To"] == DESTINATAIRE
        assert "[dest." not in sent_messages[0]["Subject"]

    def test_reset_password_hors_allowlist_reste_redirige(self, sent_messages):
        with (
            patch("app.core.settings.EMAIL_FORCE_REDIRECT_TO", REDIRECT),
            patch("app.core.settings.ACTIVATION_EMAIL_ALLOWLIST", ""),
        ):
            ok = SmtpMailSender().send_password_reset_email(
                to_email=DESTINATAIRE,
                reset_token="jeton-reset-0123",
            )
        assert ok is True
        assert sent_messages[0]["To"] == REDIRECT
