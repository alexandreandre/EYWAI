"""Sous la redirection du test, les comptes côté RH reçoivent leurs e-mails en direct (03/11).

Décision d'Alexandre : « Faut que ça parte sur les vrais emails côté RH. Les collaborateurs pour
l'instant redirection. » Côté RH = un accès actif admin, rh ou collaborateur_rh, ou un rôle custom
qui porte une permission RH. Une lecture impossible ferme : l'e-mail part à la boîte de renvoi.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.core import settings
from app.modules.platform_settings.domain.value_objects import ResolvedEmailConfig
from app.shared.domain.email_delivery import est_compte_rh
from app.shared.infrastructure.email import destinataires_rh
from app.shared.infrastructure.email import smtp_sender as mod

pytestmark = pytest.mark.unit


# --- la règle ---------------------------------------------------------------------------------

def test_un_acces_rh_ou_admin_actif_est_cote_rh():
    for role in ("admin", "rh", "collaborateur_rh"):
        assert est_compte_rh([{"role": role, "is_active": True, "company_id": "c"}], set())


def test_un_collaborateur_n_est_pas_cote_rh():
    assert not est_compte_rh([{"role": "collaborateur", "is_active": True, "company_id": "c"}], set())


def test_un_acces_inactif_ne_compte_pas():
    assert not est_compte_rh([{"role": "admin", "is_active": False, "company_id": "c"}], set())


def test_un_role_custom_est_cote_rh_seulement_avec_une_permission_rh():
    acces = [{"role": "custom", "is_active": True, "company_id": "c"}]
    assert not est_compte_rh(acces, set())
    assert est_compte_rh(acces, {"c"})


# --- la lecture -------------------------------------------------------------------------------

def test_une_lecture_impossible_renvoie_tout_a_la_boite_de_renvoi(monkeypatch):
    def panne():
        raise RuntimeError("base injoignable")

    monkeypatch.setattr(destinataires_rh, "get_supabase_admin_client", panne)
    assert destinataires_rh.adresses_rh(["rh@maji.fr"]) == frozenset()


def test_la_lecture_rend_les_adresses_cote_rh_seulement(monkeypatch):
    class Compte:
        def __init__(self, uid, email):
            self.id, self.email = uid, email

    monkeypatch.setattr(destinataires_rh, "get_supabase_admin_client", lambda: object())
    monkeypatch.setattr(destinataires_rh, "tous_les_comptes",
                        lambda _c: iter([Compte("u1", "RH@Maji.fr"), Compte("u2", "salarie@maji.fr")]))
    monkeypatch.setattr(destinataires_rh, "_acces_et_permissions", lambda _c, ids: (
        {"u1": [{"role": "rh", "is_active": True, "company_id": "c"}],
         "u2": [{"role": "collaborateur", "is_active": True, "company_id": "c"}]},
        {},
    ))
    assert destinataires_rh.adresses_rh(["rh@maji.fr", "salarie@maji.fr", "inconnu@x.fr"]) == {"rh@maji.fr"}


# --- l'envoi ----------------------------------------------------------------------------------

@pytest.fixture
def sender():
    config = ResolvedEmailConfig(
        smtp_host="smtp.test", smtp_port=587, smtp_user="u", smtp_password="p",
        smtp_security="starttls", from_email="no-reply@eywai.fr", from_name="MARTINE",
        reply_to=None, support_recipients=("contact@eywai.fr",),
        frontend_url="https://app.eywai.fr", source="environment",
    )
    s = mod.SmtpMailSender()
    with patch.object(s, "_load_config", return_value=config):
        yield s


def _envoyer(sender, a):
    serveur = MagicMock()
    serveur.__enter__ = MagicMock(return_value=serveur)
    serveur.__exit__ = MagicMock(return_value=False)
    with patch.object(sender, "_connect", return_value=serveur):
        sender.send_multipart_email(a, "Sujet", "texte", "<p>html</p>")
    return serveur.send_message.call_args[0][0]


def test_sous_redirection_un_compte_rh_recoit_en_direct(sender, monkeypatch):
    monkeypatch.setattr(settings, "EMAIL_FORCE_REDIRECT_TO", "bac-a-sable@eywai.fr")
    monkeypatch.setattr(settings, "ACTIVATION_EMAIL_ALLOWLIST", "")
    monkeypatch.setattr(mod, "adresses_rh", lambda emails: frozenset({"rh@maji.fr"}))
    msg = _envoyer(sender, "RH@maji.fr")
    assert msg["To"] == "RH@maji.fr"
    assert msg["Subject"] == "Sujet"


def test_sous_redirection_un_collaborateur_reste_redirige(sender, monkeypatch):
    monkeypatch.setattr(settings, "EMAIL_FORCE_REDIRECT_TO", "bac-a-sable@eywai.fr")
    monkeypatch.setattr(settings, "ACTIVATION_EMAIL_ALLOWLIST", "")
    monkeypatch.setattr(mod, "adresses_rh", lambda emails: frozenset({"rh@maji.fr"}))
    msg = _envoyer(sender, "salarie@maji.fr")
    assert msg["To"] == "bac-a-sable@eywai.fr"
    assert msg["Subject"] == "[dest. salarie@maji.fr] Sujet"
