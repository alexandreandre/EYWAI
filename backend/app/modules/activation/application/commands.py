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

from app.core import settings
from app.core.logging import get_logger
from app.modules.activation.domain.rules import (
    GENERIC_TOKEN_ERROR_MESSAGE,
    TOKEN_VALIDITY_DAYS,
    generate_activation_token,
    hash_activation_token,
    is_activable_employment_status,
    is_direct_delivery_allowed,
    is_invitable_email,
    is_token_alive,
    mask_email,
    parse_email_allowlist,
    token_matches,
    validate_activation_password,
)
from app.modules.activation.infrastructure import email as activation_email
from app.modules.activation.infrastructure import providers
from app.modules.activation.infrastructure.providers import (
    EmailAlreadyRegisteredError,
)
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


class AlreadyActivatedError(ActivationError):
    code = "deja_active"


class DirectDeliveryBlockedError(ActivationError):
    code = "envoi_direct_non_autorise"


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

    if not is_activable_employment_status(employee.get("employment_status")):
        raise EmployeeInactiveError(
            "Ce salarié n'est plus actif : il n'est pas invitable."
        )

    if employee.get("user_id"):
        raise AlreadyActivatedError(
            "Ce salarié a déjà activé son compte. Pour un mot de passe "
            "oublié, il doit passer par « Mot de passe oublié » sur l'écran "
            "de connexion."
        )

    email = (employee.get("email") or "").strip()
    if not is_invitable_email(email):
        raise EmailMissingError(
            "Aucune adresse e-mail réelle sur la fiche : renseignez l'adresse "
            "personnelle du salarié avant de l'inviter."
        )

    # Redirect global actif (prod) : refuser plutôt que laisser le lien
    # d'activation — donc le jeton en clair — atterrir dans la boîte de
    # redirection, lisible par d'autres que le salarié.
    if settings.EMAIL_FORCE_REDIRECT_TO and not is_direct_delivery_allowed(
        email, parse_email_allowlist(settings.ACTIVATION_EMAIL_ALLOWLIST)
    ):
        raise DirectDeliveryBlockedError(
            "Les e-mails sortants sont actuellement redirigés : cette adresse "
            "n'est pas encore autorisée à recevoir son invitation en direct. "
            "Ajoutez-la à la liste d'envoi direct avant d'inviter."
        )

    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(days=TOKEN_VALIDITY_DAYS)
    token = generate_activation_token()

    # Envoi AVANT persistance : en cas d'échec SMTP, rien n'a bougé (les
    # jetons précédents restent vivants, aucun jeton fantôme en base). Si la
    # persistance échoue après l'envoi, le lien reçu est simplement mort et
    # une ré-invitation répare.
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

    _token_repository.invalidate_pending(str(employee["id"]), now.isoformat())
    _token_repository.create(
        employee_id=str(employee["id"]),
        company_id=str(company_id),
        token_hash=token.token_hash,
        email_envoye=email,
        expires_at=expires_at.isoformat(),
        created_by=str(invited_by_user_id) if invited_by_user_id else None,
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

    # Le SEUL compte qu'une activation peut modifier est celui déjà lié à la
    # fiche (employees.user_id). Jamais de rapprochement par e-mail : une
    # adresse posée sur la fiche ne prouve pas que le compte qui la porte
    # appartient à ce salarié (sinon, escalade de privilèges possible).
    linked_uid = str(employee.get("user_id") or "").strip() or None
    if linked_uid:
        providers.update_auth_user_password(linked_uid, password)
        user_id = linked_uid
    else:
        try:
            user_id = providers.create_auth_user(email, password)
        except EmailAlreadyRegisteredError:
            logger.critical(
                "Activation REFUSÉE : l'adresse du salarié %s porte déjà un "
                "compte auth non lié à sa fiche — vérifier l'adresse saisie "
                "par la RH (tentative de détournement possible).",
                employee.get("id"),
            )
            raise InvalidTokenError()

    # Câblage identique à un compte salarié créé par la RH : profil,
    # accès société (template collaborateur), lien employees.user_id.
    providers.ensure_profile(user_id, employee)
    providers.ensure_company_access(user_id, str(employee["company_id"]))
    providers.link_employee_to_user(str(employee["id"]), user_id)

    _token_repository.mark_used(
        str(row["id"]), datetime.now(timezone.utc).isoformat()
    )

    return {"message": "Compte activé. Vous pouvez maintenant vous connecter."}
