from __future__ import annotations

from app.modules.support.infrastructure.repository import support_repository
from app.modules.support.infrastructure.email_service import send_support_ticket_email
from app.modules.audit.infrastructure.repository import audit_repository


def create_ticket(
    ticket_data: dict,
    user_id: str,
    user_role: str,
    company_id: str,
    user_email: str,
    user_name: str,
    company_name: str,
) -> dict:
    """
    Tente l'envoi email EN PREMIER.
    Si l'email échoue → raise RuntimeError, le ticket n'est PAS enregistré en base.
    Si l'email réussit → INSERT en base + historique statut initial.
    Retourne le ticket créé.
    """
    data_to_insert = {
        **ticket_data,
        "user_id": user_id,
        "user_role": user_role,
        "company_id": company_id,
        "status": "envoye",
    }
    email_ok = send_support_ticket_email(data_to_insert, user_email, user_name, company_name)
    if not email_ok:
        raise RuntimeError("L'envoi de l'email a échoué. Le ticket n'a pas été enregistré.")
    created = support_repository.create(data_to_insert)
    support_repository.add_status_history({
        "ticket_id": created["id"],
        "old_status": None,
        "new_status": "envoye",
        "changed_by": user_id,
    })
    return created


def update_ticket_status(ticket_id: str, new_status: str, changed_by: str) -> dict:
    """
    Transition manuelle de statut. Réservé Super Admin (contrôle dans le router).
    Raise LookupError si ticket inexistant.
    Raise RuntimeError si update échoue.
    Retourne le ticket mis à jour avec son historique.
    """
    ticket = support_repository.get_by_id(ticket_id)
    if not ticket:
        raise LookupError(f"Ticket {ticket_id} introuvable.")
    old_status = ticket["status"]
    updated = support_repository.update_status(ticket_id, new_status)
    if not updated:
        raise RuntimeError(f"Échec de la mise à jour du statut pour le ticket {ticket_id}.")
    support_repository.add_status_history({
        "ticket_id": ticket_id,
        "old_status": old_status,
        "new_status": new_status,
        "changed_by": changed_by,
    })
    updated["status_history"] = support_repository.get_status_history(ticket_id)
    company_id = str(ticket.get("company_id") or "")
    if company_id:
        audit_repository.log(
            company_id,
            changed_by,
            None,
            "support.ticket_status_change",
            "support_ticket",
            ticket_id,
            {"old_status": old_status, "new_status": new_status},
        )
    return updated
