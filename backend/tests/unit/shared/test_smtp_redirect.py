"""Redirection forcée de tous les e-mails sortants en environnement de test."""

from unittest.mock import MagicMock, patch

import pytest

from app.core import settings
from app.modules.platform_settings.domain.value_objects import ResolvedEmailConfig
from app.shared.infrastructure.email import smtp_sender as mod


@pytest.fixture
def config_smtp():
    return ResolvedEmailConfig(
        smtp_host="smtp.test",
        smtp_port=587,
        smtp_user="u",
        smtp_password="p",
        smtp_security="starttls",
        from_email="no-reply@eywai.fr",
        from_name="EYWAI",
        reply_to=None,
        support_recipients=("contact@eywai.fr",),
        frontend_url="https://app.eywai.fr",
        source="environment",
    )


@pytest.fixture
def sender(config_smtp):
    s = mod.SmtpMailSender()
    with patch.object(s, "_load_config", return_value=config_smtp):
        yield s


def _serveur_mock():
    serveur = MagicMock()
    serveur.__enter__ = MagicMock(return_value=serveur)
    serveur.__exit__ = MagicMock(return_value=False)
    return serveur


def test_sans_redirection_le_destinataire_est_conserve(sender, monkeypatch):
    monkeypatch.setattr(settings, "EMAIL_FORCE_REDIRECT_TO", None)
    serveur = _serveur_mock()
    with patch.object(sender, "_connect", return_value=serveur):
        ok, err = sender.send_multipart_email(
            "salarie@exemple.fr", "Sujet", "texte", "<p>html</p>"
        )
    assert (ok, err) == (True, None)
    msg = serveur.send_message.call_args[0][0]
    assert msg["To"] == "salarie@exemple.fr"
    assert msg["Subject"] == "Sujet"


def test_redirection_remplace_le_destinataire_et_prefixe_le_sujet(sender, monkeypatch):
    monkeypatch.setattr(settings, "EMAIL_FORCE_REDIRECT_TO", "bac-a-sable@eywai.fr")
    serveur = _serveur_mock()
    with patch.object(sender, "_connect", return_value=serveur):
        sender.send_multipart_email(
            "salarie@exemple.fr", "Sujet", "texte", "<p>html</p>"
        )
    msg = serveur.send_message.call_args[0][0]
    assert msg["To"] == "bac-a-sable@eywai.fr"
    assert msg["Subject"] == "[dest. salarie@exemple.fr] Sujet"


def test_redirection_couvre_les_envois_avec_pieces_jointes(sender, monkeypatch):
    monkeypatch.setattr(settings, "EMAIL_FORCE_REDIRECT_TO", "bac-a-sable@eywai.fr")
    serveur = _serveur_mock()
    with patch.object(sender, "_connect", return_value=serveur):
        sender.send_email_with_attachments(
            ["a@exemple.fr", "b@exemple.fr"],
            "Bulletin",
            "texte",
            "<p>html</p>",
            [("b.pdf", b"%PDF", "application/pdf")],
        )
    msg = serveur.send_message.call_args[0][0]
    assert msg["To"] == "bac-a-sable@eywai.fr"
    assert msg["Subject"] == "[dest. a@exemple.fr, b@exemple.fr] Bulletin"


def test_redirection_ne_depend_pas_de_l_origine_de_la_config(sender, monkeypatch):
    """La config SMTP vient de la base : la redirection s'applique quand même."""
    monkeypatch.setattr(settings, "EMAIL_FORCE_REDIRECT_TO", "bac-a-sable@eywai.fr")
    serveur = _serveur_mock()
    with patch.object(sender, "_connect", return_value=serveur):
        sender.send_multipart_email("salarie@exemple.fr", "Sujet", "t", "<p>h</p>")
    assert serveur.send_message.call_args[0][0]["To"] == "bac-a-sable@eywai.fr"
