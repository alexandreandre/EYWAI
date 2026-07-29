"""Garde-fou : ne jamais notifier vers une adresse fabriquée, et le dire.

La notification de dépôt de document porte l'obligation « coffre-fort électronique ». Elle
ne testait que `if email:` : une adresse `…@…dsn-import.local` passait ce test, l'envoi
échouait côté SMTP, et la fonction étant `best effort`, l'échec était perdu. On croyait
avoir notifié des salariés qui ne l'avaient jamais été.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.modules.notifications.application import employee_document_alerts as mod

pytestmark = pytest.mark.unit


@pytest.fixture
def supabase_table():
    with patch.object(mod, "supabase") as sb:
        table = MagicMock()
        sb.table.return_value = table
        insert_chain = MagicMock()
        table.insert.return_value = insert_chain
        insert_chain.execute.return_value = MagicMock(data=[{"id": "n1"}])
        yield table


def _contact(email: str | None):
    return patch.object(mod, "_load_employee_contact", return_value=(email, "Alice"))


def _sender():
    sender = MagicMock()
    sender.send_multipart_email.return_value = (True, None)
    return sender


def test_adresse_fabriquee_bloque_l_envoi(supabase_table) -> None:
    sender = _sender()
    with (
        _contact("import.alice.martin.123456@534386495.dsn-import.local"),
        patch.object(mod, "get_resolved_email_config") as cfg,
        patch.object(mod, "get_smtp_mail_sender", return_value=sender),
        patch.object(mod, "logger") as journal,
    ):
        cfg.return_value = MagicMock(frontend_url="http://localhost:8080")
        mod.notify_employee_new_document("emp-1", "co-1", "Bulletin de juin")

    sender.send_multipart_email.assert_not_called()
    journal.warning.assert_called_once()
    trace = " ".join(str(a) for a in journal.warning.call_args[0])
    assert "emp-1" in trace, "L'échec doit être traçable jusqu'au salarié concerné"
    assert "dsn-import.local" in trace


def test_la_notification_in_app_reste_emise(supabase_table) -> None:
    """Seul canal disponible pour un salarié sans adresse : il ne doit pas disparaître."""
    with (
        _contact("import.alice.martin.123456@534386495.dsn-import.local"),
        patch.object(mod, "get_resolved_email_config") as cfg,
        patch.object(mod, "get_smtp_mail_sender", return_value=_sender()),
    ):
        cfg.return_value = MagicMock(frontend_url="http://localhost:8080")
        mod.notify_employee_new_document("emp-1", "co-1", "Bulletin de juin")

    supabase_table.insert.assert_called_once()
    assert "Bulletin de juin" in supabase_table.insert.call_args[0][0]["message"]


@pytest.mark.parametrize(
    "adresse",
    [
        "import.x.y.1@534386495.dsn-import.local",
        "import.abc@dsn-import.eywai.fr",
        "gaelle.bouali@eywai.access.local",
        "vanessa.amate@users.eywai",
    ],
)
def test_toutes_les_familles_fabriquees_sont_bloquees(supabase_table, adresse) -> None:
    sender = _sender()
    with (
        _contact(adresse),
        patch.object(mod, "get_resolved_email_config") as cfg,
        patch.object(mod, "get_smtp_mail_sender", return_value=sender),
    ):
        cfg.return_value = MagicMock(frontend_url="http://localhost:8080")
        mod.notify_employee_new_document("emp-1", "co-1", "Document")

    sender.send_multipart_email.assert_not_called()


def test_adresse_reelle_envoie_normalement(supabase_table) -> None:
    sender = _sender()
    with (
        _contact("alice.martin@exemple.fr"),
        patch.object(mod, "get_resolved_email_config") as cfg,
        patch.object(mod, "get_smtp_mail_sender", return_value=sender),
    ):
        cfg.return_value = MagicMock(frontend_url="http://localhost:8080")
        mod.notify_employee_new_document("emp-1", "co-1", "Document")

    sender.send_multipart_email.assert_called_once()
    assert sender.send_multipart_email.call_args.kwargs["to_email"] == "alice.martin@exemple.fr"
