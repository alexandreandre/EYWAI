"""R-665 : un e-mail de bulletin en échec ne marque pas le salarié comme prévenu."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.modules.notifications.application import employee_document_alerts as mod
from app.modules.payslips.application.commands import _notify_payslip_available

LIBELLE = "Bulletin de paie — mars 2026"


def _base(contact: dict | None, deja_posee: list | None = None):
    """Doublure : le contact du salarié et les alertes déjà posées."""
    sb = MagicMock()
    contact_chain = MagicMock()
    contact_chain.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(
        data=contact
    )
    notifications = MagicMock()
    (
        notifications.select.return_value.eq.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value
    ) = MagicMock(data=deja_posee or [])
    employes = MagicMock()
    employes.select.return_value = contact_chain
    sb.table.side_effect = lambda nom: {"employees": employes, "notifications": notifications}[nom]
    return sb, notifications


def _notifier(notifications_sb, *, envoi_ok: bool = True):
    with patch.object(mod, "supabase", notifications_sb), patch.object(
        mod, "_send_email", return_value=envoi_ok
    ) as envoi, patch.object(mod, "PAYSLIP_EMAIL_REDIRECT", None):
        resultat = mod.notify_employee_new_document(
            "emp-1", "co-1", LIBELLE, page_path="payslips", notification_type=mod.NOTIFICATION_TYPE_PAYSLIP
        )
    return resultat, envoi


def test_email_parti_le_salarie_est_prevenu():
    sb, _ = _base({"email": "a@example.com", "first_name": "A"})
    resultat, envoi = _notifier(sb, envoi_ok=True)
    assert resultat is True
    envoi.assert_called_once()


def test_email_en_echec_le_salarie_n_est_pas_prevenu():
    sb, _ = _base({"email": "a@example.com", "first_name": "A"})
    resultat, _envoi = _notifier(sb, envoi_ok=False)
    assert resultat is False


def test_le_marqueur_n_est_pas_pose_si_l_email_echoue():
    sb, _ = _base({"email": "a@example.com", "first_name": "A"})
    with patch.object(mod, "supabase", sb), patch.object(mod, "_send_email", return_value=False), patch.object(
        mod, "PAYSLIP_EMAIL_REDIRECT", None
    ):
        assert _notify_payslip_available("emp-1", "co-1", 2026, 3) is False


def test_relance_sans_seconde_alerte_mais_l_email_repart():
    message = f"Votre bulletin de paie est disponible : « {LIBELLE} »."
    sb, notifications = _base({"email": "a@example.com", "first_name": "A"}, deja_posee=[{"id": "n1"}])
    resultat, envoi = _notifier(sb, envoi_ok=True)
    assert resultat is True
    notifications.insert.assert_not_called()
    envoi.assert_called_once()
    filtre = notifications.select.return_value.eq.return_value.eq.return_value.eq
    assert filtre.call_args.args == ("message", message)


def test_premiere_notification_pose_l_alerte():
    sb, notifications = _base({"email": "a@example.com", "first_name": "A"})
    _notifier(sb)
    notifications.insert.assert_called_once()


def test_sans_adresse_l_alerte_suffit():
    sb, _ = _base({"email": "", "first_name": "A"})
    resultat, envoi = _notifier(sb)
    assert resultat is True
    envoi.assert_not_called()


def test_sans_adresse_ni_alerte_personne_n_est_prevenu():
    sb, notifications = _base({"email": "", "first_name": "A"})
    notifications.insert.side_effect = RuntimeError("base indisponible")
    resultat, _envoi = _notifier(sb)
    assert resultat is False
