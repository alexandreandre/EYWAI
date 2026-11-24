"""Sous la redirection du test, l'envoi direct « côté RH » se limite à la société d'envoi (24/11/2026).

Depuis le 03/11, un compte côté RH reçoit en direct malgré `EMAIL_FORCE_REDIRECT_TO`. Mais un
compte RH de N'IMPORTE QUELLE société comptait : un RH de la société A pouvait faire partir
en direct, vers le RH de la société B, ses exports planifiés ou ses copies d'absence (les
destinataires y sont libres). Désormais, quand l'envoi part d'une société connue, seul un
compte côté RH de CETTE société (accès actif) reçoit en direct ; les autres vont à la boîte
de renvoi. Sans société connue (activation, mot de passe oublié, alertes d'exploitation,
support, test SMTP) : rien ne change.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.core import settings
from app.modules.platform_settings.domain.value_objects import ResolvedEmailConfig
from app.shared.infrastructure.email import destinataires_rh
from app.shared.infrastructure.email import smtp_sender as mod

pytestmark = pytest.mark.unit


# --- la lecture -------------------------------------------------------------------------------


class _Compte:
    def __init__(self, uid, email):
        self.id, self.email = uid, email


@pytest.fixture
def base(monkeypatch):
    """rh-a : RH de A ; rh-b : RH de B ; custom-a : rôle custom à droits RH dans A ;
    custom-b : custom dans A mais droits RH dans B seulement ; ancien-a : accès RH à A révoqué."""
    monkeypatch.setattr(destinataires_rh, "get_supabase_admin_client", lambda: object())
    comptes = [
        _Compte("u-rh-a", "rh-a@exemple.fr"),
        _Compte("u-rh-b", "rh-b@exemple.fr"),
        _Compte("u-custom-a", "custom-a@exemple.fr"),
        _Compte("u-custom-b", "custom-b@exemple.fr"),
        _Compte("u-ancien-a", "ancien-a@exemple.fr"),
    ]
    monkeypatch.setattr(destinataires_rh, "tous_les_comptes", lambda _c: iter(comptes))
    monkeypatch.setattr(destinataires_rh, "_acces_et_permissions", lambda _c, ids: (
        {
            "u-rh-a": [{"role": "rh", "is_active": True, "company_id": "A"}],
            "u-rh-b": [
                {"role": "admin", "is_active": True, "company_id": "B"},
                {"role": "collaborateur", "is_active": True, "company_id": "A"},
            ],
            "u-custom-a": [{"role": "custom", "is_active": True, "company_id": "A"}],
            "u-custom-b": [
                {"role": "custom", "is_active": True, "company_id": "A"},
                {"role": "custom", "is_active": True, "company_id": "B"},
            ],
            "u-ancien-a": [
                {"role": "rh", "is_active": False, "company_id": "A"},
                {"role": "rh", "is_active": True, "company_id": "B"},
            ],
        },
        {"u-custom-a": {"A"}, "u-custom-b": {"B"}},
    ))


TOUS = ["rh-a@exemple.fr", "rh-b@exemple.fr", "custom-a@exemple.fr", "custom-b@exemple.fr", "ancien-a@exemple.fr"]


def test_sans_societe_tout_compte_rh_compte_comme_avant(base):
    assert destinataires_rh.adresses_rh(TOUS) == set(TOUS)


def test_avec_une_societe_seuls_ses_comptes_rh_actifs_comptent(base):
    assert destinataires_rh.adresses_rh(TOUS, company_id="A") == {"rh-a@exemple.fr", "custom-a@exemple.fr"}
    assert destinataires_rh.adresses_rh(TOUS, company_id="B") == {
        "rh-b@exemple.fr", "custom-b@exemple.fr", "ancien-a@exemple.fr",
    }


def test_une_societe_vide_ferme(base):
    assert destinataires_rh.adresses_rh(TOUS, company_id="") == frozenset()


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


@pytest.fixture
def redirection(monkeypatch):
    monkeypatch.setattr(settings, "EMAIL_FORCE_REDIRECT_TO", "bac-a-sable@eywai.fr")
    monkeypatch.setattr(settings, "ACTIVATION_EMAIL_ALLOWLIST", "")
    appels = []

    def adresses_rh(emails, company_id=None):
        appels.append(company_id)
        rh = {None: {"rh-a@exemple.fr", "rh-b@exemple.fr"}, "A": {"rh-a@exemple.fr"}}
        return frozenset(e for e in emails if e.lower() in rh.get(company_id, set()))

    monkeypatch.setattr(mod, "adresses_rh", adresses_rh)
    return appels


def _serveur():
    serveur = MagicMock()
    serveur.__enter__ = MagicMock(return_value=serveur)
    serveur.__exit__ = MagicMock(return_value=False)
    return serveur


def test_pieces_jointes_d_une_societe_le_rh_d_une_autre_est_redirige(sender, redirection):
    serveur = _serveur()
    with patch.object(sender, "_connect", return_value=serveur):
        sender.send_email_with_attachments(
            ["rh-a@exemple.fr", "rh-b@exemple.fr"], "Export", "t", "<p>h</p>", [], company_id="A",
        )
    msg = serveur.send_message.call_args[0][0]
    assert msg["To"] == "rh-a@exemple.fr, bac-a-sable@eywai.fr"
    assert msg["Subject"] == "[dest. rh-b@exemple.fr] Export"
    assert redirection == ["A"]


def test_message_simple_d_une_societe_le_rh_d_une_autre_est_redirige(sender, redirection):
    serveur = _serveur()
    with patch.object(sender, "_connect", return_value=serveur):
        sender.send_multipart_email("rh-b@exemple.fr", "Sujet", "t", "<p>h</p>", company_id="A")
    assert serveur.send_message.call_args[0][0]["To"] == "bac-a-sable@eywai.fr"


def test_sans_societe_le_comportement_est_inchange(sender, redirection):
    serveur = _serveur()
    with patch.object(sender, "_connect", return_value=serveur):
        sender.send_multipart_email("rh-b@exemple.fr", "Mot de passe", "t", "<p>h</p>")
    assert serveur.send_message.call_args[0][0]["To"] == "rh-b@exemple.fr"
    assert redirection == [None]


# --- les appelants qui connaissent la société -------------------------------------------------


def test_les_exports_passent_leur_societe():
    from app.modules.exports.application.notifications import notify_export_recipients

    cfg = MagicMock(is_configured=True)
    with patch(
        "app.modules.platform_settings.application.email_config.get_resolved_email_config", return_value=cfg,
    ), patch(
        "app.modules.exports.application.notifications._collect_export_files", return_value=([], []),
    ), patch("app.modules.exports.application.notifications.get_smtp_mail_sender") as fabrique:
        fabrique.return_value.send_email_with_attachments.return_value = (True, None)
        notify_export_recipients("co-A", ["x@exemple.fr"], ["exp-1"], period="2026-11")
    assert fabrique.return_value.send_email_with_attachments.call_args.kwargs["company_id"] == "co-A"


def test_les_demandes_d_absence_passent_leur_societe():
    from app.modules.absences.application import notifications as absences

    with patch.object(absences, "_employee_context", return_value={"first_name": "A", "last_name": "B"}), patch.object(
        absences, "_company_name", return_value="Société"
    ), patch.object(absences, "_build_absence_action_url", return_value="https://app/leaves"), patch.object(
        absences, "get_smtp_mail_sender"
    ) as fabrique:
        fabrique.return_value.send_email_with_attachments.return_value = (True, None)
        absences._send_leave_request_email(
            {"employee_id": "e1", "company_id": "co-A", "type": "conge_paye", "selected_days": ["2026-11-24"]},
            recipients=["x@exemple.fr"],
            stage_label="en attente",
        )
    assert fabrique.return_value.send_email_with_attachments.call_args.kwargs["company_id"] == "co-A"


def test_les_documents_du_salarie_passent_leur_societe():
    from app.modules.notifications.application import employee_document_alerts as docs

    with patch.object(docs, "_insert_notification", return_value=True), patch.object(
        docs, "_load_employee_contact", return_value=("x@exemple.fr", "Alice")
    ), patch.object(docs, "get_resolved_email_config", return_value=MagicMock(frontend_url="https://app")), patch.object(
        docs, "get_smtp_mail_sender"
    ) as fabrique:
        fabrique.return_value.send_multipart_email.return_value = (True, None)
        docs.notify_employee_new_document("e1", "co-A", "Attestation")
    assert fabrique.return_value.send_multipart_email.call_args.kwargs["company_id"] == "co-A"


def test_les_relances_rh_passent_leur_societe():
    from datetime import date

    from app.modules.employees.domain.deadline_reminders import REMINDER_TYPE_CDD, DeadlineCandidate
    from app.modules.notifications.application import hr_deadline_reminders as relances

    candidat = DeadlineCandidate(
        employee_id="e1", reminder_type=REMINDER_TYPE_CDD, deadline=date(2026, 12, 15),
        days_remaining=10, label="Fin de CDD", first_name="A", last_name="B",
    )
    with patch.object(relances, "fetch_employees_for_hr_deadline_reminders", return_value=[]), patch.object(
        relances, "list_hr_deadline_candidates", return_value=[candidat]
    ), patch.object(relances, "was_reminder_sent", return_value=False), patch.object(
        relances, "fetch_rh_recipient_emails", return_value=["x@exemple.fr"]
    ), patch.object(relances, "fetch_company_name", return_value="Société"), patch.object(
        relances, "log_reminder_sent", return_value=True
    ), patch.object(
        relances, "get_resolved_email_config", return_value=MagicMock(frontend_url="https://app")
    ), patch.object(relances, "get_smtp_mail_sender") as fabrique:
        fabrique.return_value.send_multipart_email.return_value = (True, None)
        relances.send_hr_deadline_reminders("co-A")
    assert fabrique.return_value.send_multipart_email.call_args.kwargs["company_id"] == "co-A"
