"""Alignement de l'adresse d'un compte Auth sur l'adresse réelle de la fiche salarié.

Deux objets distincts cohabitent dans la plateforme :

- ``employees.email`` est l'**adresse de contact** de la personne : réelle ou vide ;
- ``auth.users.email`` est l'**identifiant technique** du compte, jamais affiché.

La connexion se fait par identifiant ``prenom.nom``, pas par adresse. L'adresse du compte
reste néanmoins le canal de réinitialisation de mot de passe : tant qu'elle pointe vers un
domaine fabriqué, ce canal est mort. Ce module réaligne le compte dès qu'une adresse réelle
apparaît sur la fiche.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, Optional

from app.core.logging import get_logger
from app.modules.employees.domain.rules import is_dsn_import_placeholder_email

logger = get_logger("modules.employees.application.auth_email_sync")


class SyncOutcome(str, Enum):
    """Issue d'une tentative de réalignement, exploitable par les scripts de reprise."""

    REALIGNED = "realigned"
    SKIPPED_NO_ACCOUNT = "skipped_no_account"
    SKIPPED_NO_REAL_EMAIL = "skipped_no_real_email"
    SKIPPED_REAL_LOGIN = "skipped_real_login"
    FAILED = "failed"


def sync_auth_email_for_employee(
    employee: Dict[str, Any],
    *,
    auth: Optional[Any] = None,
) -> SyncOutcome:
    """Aligne l'adresse du compte Auth sur celle de la fiche, si et seulement si :

    - le salarié a un compte ;
    - sa fiche porte une adresse réelle ;
    - l'adresse actuelle du compte est fabriquée — une adresse réelle déjà en place a été
      choisie par la personne et n'est jamais écrasée.

    Ne lève jamais : corriger une adresse de contact ne doit pas pouvoir faire échouer
    l'enregistrement d'une fiche.
    """
    employee_id = str(employee.get("id") or "?")
    user_id = str(employee.get("user_id") or "").strip()
    if not user_id:
        return SyncOutcome.SKIPPED_NO_ACCOUNT

    email = str(employee.get("email") or "").strip()
    if not email or is_dsn_import_placeholder_email(email):
        return SyncOutcome.SKIPPED_NO_REAL_EMAIL

    if auth is None:
        from app.modules.employees.infrastructure.providers import get_auth_provider

        auth = get_auth_provider()

    try:
        current = auth.get_user_email(user_id)
    except Exception as exc:
        logger.warning(
            "Compte Auth %s illisible pour le salarié %s : %s", user_id, employee_id, exc
        )
        return SyncOutcome.FAILED

    if not is_dsn_import_placeholder_email(current):
        return SyncOutcome.SKIPPED_REAL_LOGIN

    try:
        auth.update_user_email(user_id, email)
    except Exception as exc:
        # Cas courant : l'adresse est déjà portée par un autre compte (doublon). On ne
        # force rien, la fiche reste à jour et l'arbitrage revient à un humain.
        logger.warning(
            "Réalignement du compte Auth impossible pour le salarié %s (%s → %s) : %s",
            employee_id,
            current,
            email,
            exc,
        )
        return SyncOutcome.FAILED

    logger.info(
        "Compte Auth du salarié %s réaligné : %s → %s", employee_id, current, email
    )
    return SyncOutcome.REALIGNED
