# Orchestration login : résolution identifiant, sign_in, construction TokenWithUser.
# Utilise uniquement domain (règles) + infrastructure (ports). Comportement identique au legacy.

from __future__ import annotations

from fastapi import HTTPException

from app.core.logging import get_logger, is_app_debug_enabled
from app.core.supabase_resilience import is_transient_supabase_error
from app.modules.auth.domain.rules import is_email_like
from app.modules.auth.infrastructure import (
    auth_provider,
    user_from_token,
    user_resolver,
)

logger = get_logger("modules.auth")

# Une réponse distincte pour chaque cas, sans jamais dire si un compte existe :
# tant que le mot de passe n'est pas vérifié, un compte inconnu, un mauvais mot
# de passe et un compte bloqué dans Supabase Auth reçoivent la même réponse
# (Supabase répond « User is banned » avant de vérifier le mot de passe :
# le distinguer dirait à n'importe qui que l'adresse a un compte). Le corps suit
# la forme des refus métier : {"code", "message"} (lu par le front, voir
# frontend/src/lib/messageEchecConnexion.ts).
CODE_IDENTIFIANTS_INCORRECTS = "identifiants_incorrects"
CODE_EMAIL_NON_CONFIRMEE = "email_non_confirmee"
CODE_COMPTE_DESACTIVE = "compte_desactive"
CODE_TROP_DE_TENTATIVES = "trop_de_tentatives"
CODE_SERVICE_INDISPONIBLE = "service_indisponible"
CODE_CONNEXION_IMPOSSIBLE = "connexion_impossible"

MESSAGE_IDENTIFIANTS_INCORRECTS = "Identifiant ou mot de passe incorrect"

#: Codes de Supabase Auth qui disent « trop de demandes » (429).
_CODES_LIMITE = {"over_request_rate_limit", "over_email_send_rate_limit", "over_sms_send_rate_limit"}


def _refus(status: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status, detail={"code": code, "message": message})


def _identifiants_incorrects() -> HTTPException:
    return _refus(400, CODE_IDENTIFIANTS_INCORRECTS, MESSAGE_IDENTIFIANTS_INCORRECTS)


def _service_indisponible() -> HTTPException:
    return _refus(
        503,
        CODE_SERVICE_INDISPONIBLE,
        "Le service de connexion ne répond pas pour l'instant. Réessayez dans quelques "
        "secondes : votre mot de passe n'est pas en cause.",
    )


def _connexion_impossible() -> HTTPException:
    return _refus(
        500,
        CODE_CONNEXION_IMPOSSIBLE,
        "La connexion n'a pas abouti. Réessayez dans quelques instants.",
    )


def _refus_de_supabase(exc: Exception) -> HTTPException:
    """La réponse à un échec de `sign_in_with_password`."""
    code = str(getattr(exc, "code", "") or "")
    statut = getattr(exc, "status", None)
    if statut == 429 or code in _CODES_LIMITE:
        return _refus(
            429,
            CODE_TROP_DE_TENTATIVES,
            "Trop de tentatives de connexion. Patientez quelques minutes avant de réessayer.",
        )
    if is_transient_supabase_error(exc) or (isinstance(statut, int) and statut >= 500):
        logger.warning("Connexion : service d'authentification injoignable (%s)", type(exc).__name__)
        return _service_indisponible()
    if code == "email_not_confirmed":
        # Supabase ne le dit qu'une fois le mot de passe vérifié : rien n'est révélé.
        return _refus(
            400,
            CODE_EMAIL_NON_CONFIRMEE,
            "Votre adresse e-mail n'est pas encore confirmée : ouvrez le lien d'activation "
            "reçu par e-mail, puis reconnectez-vous.",
        )
    if code == "user_banned":
        logger.info("Connexion refusée : compte bloqué dans Supabase Auth")
        return _identifiants_incorrects()
    # Tout autre refus de Supabase Auth (mot de passe faux, compte inconnu, champ
    # vide refusé par le client) : la réponse commune.
    est_refus_auth = any(c.__name__ == "AuthError" for c in type(exc).__mro__)
    if est_refus_auth or (isinstance(statut, int) and 400 <= statut < 500):
        return _identifiants_incorrects()
    logger.exception("Échec de connexion inattendu")
    return _connexion_impossible()


def login(username_or_email: str, password: str) -> dict:
    """
    Connexion : si pas email (règle is_email_like), résout l’email via IUserByLoginResolver ;
    puis sign_in_with_password ; puis User via IUserFromToken.
    Retourne {"access_token", "token_type": "bearer", "user": User}.
    """
    debug = is_app_debug_enabled()
    try:
        login_input = username_or_email.strip().lower()

        if is_email_like(login_input):
            email_to_use = login_input
        else:
            if debug:

                logger.debug("Résolution username → email pour identifiant fourni")
            email_to_use = user_resolver.resolve_email(login_input)
            if not email_to_use:
                if debug:

                    logger.debug(
                        "Échec login : aucun employé pour cet identifiant (count=%s)",
                        _employee_count_hint(),
                    )
                raise _identifiants_incorrects()

        if not email_to_use:
            raise _identifiants_incorrects()

        try:
            session = auth_provider.sign_in_with_password(email_to_use, password)
        except Exception as exc:
            raise _refus_de_supabase(exc) from exc
        access_token = session["access_token"]
        user_info = user_from_token.get_user(access_token)

        # Mot de passe vérifié : on peut dire qu'un compte n'a plus aucun accès,
        # au lieu d'ouvrir une session vide.
        if not getattr(user_info, "is_platform_admin", False) and not getattr(
            user_info, "accessible_companies", None
        ):
            raise _refus(
                403,
                CODE_COMPTE_DESACTIVE,
                "Ce compte n'a plus accès à Martine : ses accès ont été retirés. "
                "Contactez votre service RH.",
            )

        if debug:

            logger.debug(
                "Connexion réussie (super_admin=%s)",
                user_info.is_platform_admin,
            )

        return {
            "access_token": access_token,
            "token_type": "bearer",
            "refresh_token": session.get("refresh_token"),
            "expires_in": session.get("expires_in"),
            "expires_at": session.get("expires_at"),
            "user": user_info,
        }

    except HTTPException:
        raise
    except Exception as e:
        # Résolution de l'identifiant ou lecture du compte en échec : jamais
        # « mot de passe incorrect » pour une panne.
        if is_transient_supabase_error(e):
            logger.warning("Connexion : base injoignable (%s)", type(e).__name__)
            raise _service_indisponible() from e
        logger.exception("Échec de connexion inattendu")
        raise _connexion_impossible() from e


def _employee_count_hint() -> str:
    """Indicateur agrégé pour le debug local (pas de dump PII)."""
    try:
        from app.modules.auth.infrastructure.queries import get_employees_debug_snapshot

        return str(len(get_employees_debug_snapshot()))
    except Exception:
        return "?"
