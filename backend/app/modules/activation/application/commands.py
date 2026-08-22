"""
Commandes du lien d'activation.

- invite_employee : commande RH (ré-envoi = même commande, anciens jetons morts).
- verify_activation_token / complete_activation : endpoints publics.

Toute erreur de jeton est loguée côté serveur mais renvoyée au client sous
UN SEUL message générique (pas d'énumération).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict

from app.core.logging import get_logger
from app.modules.activation.domain.rules import (
    GENERIC_TOKEN_ERROR_MESSAGE,
    TOKEN_VALIDITY_DAYS,
    generate_activation_token,
    hash_activation_token,
    is_invitable_email,
    is_token_alive,
    mask_email,
    token_matches,
    validate_activation_password,
)
from app.modules.activation.infrastructure import email as activation_email
from app.modules.activation.infrastructure import providers
from app.modules.activation.infrastructure.repository import (
    ActivationTokenRepository,
)

logger = get_logger("modules.activation.commands")

_token_repository = ActivationTokenRepository()


# ----- Erreurs applicatives (mapping par codes structurés côté router) -----


class ActivationError(Exception):
    """Base des erreurs métier du module activation."""

    code = "activation_erreur"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class EmployeeNotFoundError(ActivationError):
    code = "salarie_introuvable"


class EmailMissingError(ActivationError):
    code = "email_manquant"


class EmployeeInactiveError(ActivationError):
    code = "salarie_inactif"


class InvalidTokenError(ActivationError):
    """Jeton inconnu, expiré, consommé ou invalidé : même erreur pour tous."""

    code = "lien_invalide"

    def __init__(self) -> None:
        super().__init__(GENERIC_TOKEN_ERROR_MESSAGE)


class InvalidPasswordError(ActivationError):
    code = "mot_de_passe_invalide"


class EmailSendError(ActivationError):
    code = "envoi_email_echoue"


# ----- Commande RH -----


def invite_employee(
    employee_id: str,
    company_id: str,
    invited_by_user_id: str,
) -> Dict[str, Any]:
    """
    Invite (ou ré-invite) un salarié : invalide les jetons vivants, crée un
    jeton neuf (empreinte seule en base) et envoie l'e-mail d'activation.
    """
    employee = providers.get_employee_for_activation(employee_id)
    if not employee or str(employee.get("company_id")) != str(company_id):
        # 404 sans distinction : pas de fuite d'existence hors périmètre.
        raise EmployeeNotFoundError("Salarié introuvable.")

    status = (employee.get("employment_status") or "actif").strip().lower()
    if status != "actif":
        raise EmployeeInactiveError(
            "Ce salarié n'est plus actif : il n'est pas invitable."
        )

    email = (employee.get("email") or "").strip()
    if not is_invitable_email(email):
        raise EmailMissingError(
            "Aucune adresse e-mail réelle sur la fiche : renseignez l'adresse "
            "personnelle du salarié avant de l'inviter."
        )

    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(days=TOKEN_VALIDITY_DAYS)
    token = generate_activation_token()

    _token_repository.invalidate_pending(str(employee["id"]), now.isoformat())
    _token_repository.create(
        employee_id=str(employee["id"]),
        company_id=str(company_id),
        token_hash=token.token_hash,
        email_envoye=email,
        expires_at=expires_at.isoformat(),
        created_by=str(invited_by_user_id) if invited_by_user_id else None,
    )

    societe = providers.get_company_name(str(company_id))
    sent = activation_email.send_activation_email(
        to_email=email,
        prenom=employee.get("first_name") or "",
        societe=societe,
        raw_token=token.raw_token,
    )
    if not sent:
        raise EmailSendError(
            "L'e-mail d'invitation n'a pas pu être envoyé. Réessayez plus tard."
        )

    return {
        "invited_at": now.isoformat(),
        "email": mask_email(email),
        "expires_at": expires_at.isoformat(),
    }


# ----- Endpoints publics -----


def _get_live_token_row(raw_token: str) -> Dict[str, Any]:
    """Empreinte → ligne vivante, sinon InvalidTokenError (message unique)."""
    row = _token_repository.get_by_hash(hash_activation_token(raw_token))
    if not row or not token_matches(row.get("token_hash", ""), raw_token):
        logger.warning("Activation : jeton inconnu")
        raise InvalidTokenError()
    if not is_token_alive(row):
        logger.warning(
            "Activation : jeton mort (used=%s invalidated=%s expires=%s)",
            bool(row.get("used_at")),
            bool(row.get("invalidated_at")),
            row.get("expires_at"),
        )
        raise InvalidTokenError()
    return row


def verify_activation_token(raw_token: str) -> Dict[str, str]:
    """200 {prenom, societe} si le jeton est vivant — rien d'autre ne sort."""
    row = _get_live_token_row(raw_token)
    employee = providers.get_employee_for_activation(str(row["employee_id"]))
    if not employee:
        logger.warning("Activation : jeton vivant sans fiche salarié")
        raise InvalidTokenError()
    return {
        "prenom": employee.get("first_name") or "",
        "societe": providers.get_company_name(str(row["company_id"])),
    }


def complete_activation(raw_token: str, password: str) -> Dict[str, str]:
    """
    Valide le jeton, crée ou met à jour le compte auth, câble le compte au
    salarié (profil, accès société, employees.user_id) et consomme le jeton.
    """
    row = _get_live_token_row(raw_token)

    password_error = validate_activation_password(password)
    if password_error:
        raise InvalidPasswordError(password_error)

    employee = providers.get_employee_for_activation(str(row["employee_id"]))
    if not employee:
        logger.warning("Activation : jeton vivant sans fiche salarié")
        raise InvalidTokenError()

    email = (row.get("email_envoye") or "").strip()
    if not email:
        logger.warning("Activation : jeton sans adresse d'envoi")
        raise InvalidTokenError()

    existing_uid = providers.find_auth_user_id_by_email(email)
    if existing_uid:
        providers.update_auth_user_password(existing_uid, password)
        user_id = existing_uid
    else:
        user_id = providers.create_auth_user(email, password)

    # Câblage identique à un compte salarié créé par la RH : profil,
    # accès société (template collaborateur), lien employees.user_id.
    providers.ensure_profile(user_id, employee)
    providers.ensure_company_access(user_id, str(employee["company_id"]))
    providers.link_employee_to_user(str(employee["id"]), user_id)

    _token_repository.mark_used(
        str(row["id"]), datetime.now(timezone.utc).isoformat()
    )

    return {"message": "Compte activé. Vous pouvez maintenant vous connecter."}
