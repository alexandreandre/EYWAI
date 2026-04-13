from __future__ import annotations

from app.modules.support.infrastructure.repository import support_repository


def get_tickets_super_admin(filters: dict) -> list[dict]:
    """Tous les tickets toutes entreprises. Filtres : company_id, urgency, status, module, date_from, date_to."""
    return support_repository.list_for_super_admin(filters)


def get_tickets_for_company(company_id: str, filters: dict) -> list[dict]:
    """Tickets de l'entreprise active. Filtres : urgency, status, module, date_from, date_to, user_id."""
    return support_repository.list_for_company(company_id, filters)


def get_tickets_for_user(user_id: str) -> list[dict]:
    """Uniquement les tickets créés par cet utilisateur."""
    return support_repository.list_for_user(user_id)


def get_ticket_detail(ticket_id: str) -> dict | None:
    """Détail d'un ticket avec historique de statuts. Retourne None si inexistant."""
    ticket = support_repository.get_by_id(ticket_id)
    if not ticket:
        return None
    ticket["status_history"] = support_repository.get_status_history(ticket_id)
    return ticket
