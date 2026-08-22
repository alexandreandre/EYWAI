"""Lectures du lien d'activation (état d'invitation côté fiche RH)."""

from __future__ import annotations

from typing import Any, Dict

from app.modules.activation.application.commands import EmployeeNotFoundError
from app.modules.activation.domain.rules import is_token_expired, mask_email
from app.modules.activation.infrastructure import providers
from app.modules.activation.infrastructure.repository import (
    ActivationTokenRepository,
)

_token_repository = ActivationTokenRepository()


def get_invitation_status(employee_id: str, company_id: str) -> Dict[str, Any]:
    """
    État du dernier jeton pour la fiche RH :
    - "active"        : la fiche est liée à un compte (employees.user_id posé) ;
    - "invite"        : un jeton existe (invited_at, expired) ;
    - "jamais_invite" : rien n'est jamais parti.
    """
    employee = providers.get_employee_for_activation(employee_id)
    if not employee or str(employee.get("company_id")) != str(company_id):
        raise EmployeeNotFoundError("Salarié introuvable.")

    email = (employee.get("email") or "").strip()

    if employee.get("user_id"):
        return {
            "status": "active",
            "invited_at": None,
            "expires_at": None,
            "expired": False,
            "email": mask_email(email) if email else None,
        }

    latest = _token_repository.get_latest_for_employee(str(employee["id"]))
    if not latest:
        return {
            "status": "jamais_invite",
            "invited_at": None,
            "expires_at": None,
            "expired": False,
            "email": mask_email(email) if email else None,
        }

    return {
        "status": "invite",
        "invited_at": latest.get("created_at"),
        "expires_at": latest.get("expires_at"),
        "expired": is_token_expired(latest),
        "email": mask_email(latest.get("email_envoye") or email or ""),
    }
