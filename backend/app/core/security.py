"""
Logique transverse de sécurité : authentification, contexte utilisateur et entreprise.

Contenu :
- get_current_user : validation JWT, chargement profil + accès multi-entreprises, entreprise active.
- get_current_user_role : dépendance dérivée (rôle pour l'entreprise active).
- oauth2_scheme : schéma OAuth2 pour extraction du token.
- set_session_company (via Supabase RPC) : définition du contexte entreprise en base.

Les permissions métier spécifiques (vérifications par module) restent dans les routers
ou seront migrées plus tard dans les modules. Ne pas les déplacer ici.
"""

from __future__ import annotations

import threading
import time
from typing import Annotated, Optional

from fastapi import Depends, HTTPException, Header, status
from fastapi.security import OAuth2PasswordBearer

try:
    from supabase_auth.errors import AuthApiError
except ImportError:  # compat anciennes installs
    from gotrue.errors import AuthApiError  # type: ignore[no-redef]

from app.core.database import get_supabase_admin_client, supabase
from app.core.logging import get_logger, is_app_debug_enabled
from app.core.supabase_resilience import (
    execute_with_retry,
    is_transient_supabase_error,
)
from app.modules.users.schemas.responses import CompanyAccess, User

logger = get_logger("core.security")

# Schéma OAuth2 pour l'endpoint de login
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

_session_company_lock = threading.Lock()


def _set_session_company(company_id: str) -> bool:
    """
    Définit le contexte entreprise PostgreSQL (RLS).
    Sérialise les appels (client Supabase partagé) et réessaie sur erreurs réseau passagères.
    """
    last_error: BaseException | None = None
    for attempt in range(3):
        try:
            with _session_company_lock:
                supabase.rpc(
                    "set_session_company", {"p_company_id": company_id}
                ).execute()
            return True
        except Exception as e:
            last_error = e
            if is_transient_supabase_error(e) and attempt < 2:
                time.sleep(0.03 * (attempt + 1))
                continue
            break
    if last_error is not None:
        if is_transient_supabase_error(last_error):
            if is_app_debug_enabled():
                logger.debug(
                    "set_session_company indisponible (transitoire) pour %s: %s",
                    company_id,
                    last_error,
                )
        else:
            logger.warning(
                "set_session_company échoué pour %s: %s",
                company_id,
                last_error,
            )
    return False


def get_current_user(
    token: str = Depends(oauth2_scheme),
    x_active_company: Annotated[Optional[str], Header(alias="X-Active-Company")] = None,
) -> User:
    """
    Valide le token JWT, récupère l'utilisateur depuis Supabase Auth,
    charge ses accès multi-entreprises et définit le contexte d'entreprise active.

    Args:
        token: JWT token from Authorization header
        x_active_company: Optional company ID from X-Active-Company header

    Returns:
        User object with all company accesses and active company context
    """
    debug = is_app_debug_enabled()
    try:
        if debug:

            logger.debug(
                "Validation token (X-Active-Company=%s)",
                x_active_company,
            )

        # 1. Authentifier l'utilisateur
        user_response = execute_with_retry(lambda: supabase.auth.get_user(token))
        user = user_response.user
        if not user:
            raise HTTPException(status_code=401, detail="Utilisateur non trouvé")

        data_client = get_supabase_admin_client()

        # 2. Récupérer le profil de base
        profile_response = execute_with_retry(
            lambda: data_client.table("profiles")
            .select("first_name, last_name")
            .eq("id", user.id)
            .execute()
        )

        if not profile_response.data or len(profile_response.data) == 0:
            raise HTTPException(status_code=404, detail="Profil utilisateur non trouvé")

        profile_data = profile_response.data[0]

        # 3. Vérifier si super admin
        super_admin_response = execute_with_retry(
            lambda: data_client.table("super_admins")
            .select("*")
            .eq("user_id", user.id)
            .eq("is_active", True)
            .execute()
        )
        is_platform_admin = bool(
            super_admin_response.data and len(super_admin_response.data) > 0
        )

        # 4. Charger les accès multi-entreprises
        accesses_response = execute_with_retry(
            lambda: data_client.table("user_company_accesses")
            .select(
                "company_id, role, is_primary, companies(id, company_name, siret, logo_url, logo_scale, group_id, company_groups(group_name, logo_url, logo_scale))"
            )
            .eq("user_id", user.id)
            .execute()
        )

        accessible_companies = []
        for acc in accesses_response.data:
            company_data = acc.get("companies", {})
            if company_data:
                group_name = None
                group_logo_url = None
                group_logo_scale = 1.0
                if company_data.get("company_groups"):
                    group_name = company_data["company_groups"].get("group_name")
                    group_logo_url = company_data["company_groups"].get("logo_url")
                    group_logo_scale = company_data["company_groups"].get(
                        "logo_scale", 1.0
                    )

                accessible_companies.append(
                    CompanyAccess(
                        company_id=acc["company_id"],
                        company_name=company_data.get("company_name", "Unknown"),
                        role=acc["role"],
                        is_primary=acc["is_primary"],
                        siret=company_data.get("siret"),
                        logo_url=company_data.get("logo_url"),
                        logo_scale=company_data.get("logo_scale", 1.0),
                        group_id=company_data.get("group_id"),
                        group_name=group_name,
                        group_logo_url=group_logo_url,
                        group_logo_scale=group_logo_scale,
                    )
                )

        # 5. Déterminer l'entreprise active
        active_company_id = None

        if is_platform_admin and x_active_company:
            active_company_id = x_active_company
        elif x_active_company:
            if any(acc.company_id == x_active_company for acc in accessible_companies):
                active_company_id = x_active_company
            elif debug:

                logger.debug(
                    "X-Active-Company ignoré (non accessible): %s",
                    x_active_company,
                )

        if not active_company_id and accessible_companies:
            primary = next(
                (acc for acc in accessible_companies if acc.is_primary), None
            )
            if primary:
                active_company_id = primary.company_id
            else:
                active_company_id = accessible_companies[0].company_id

        # 6. Définir le contexte d'entreprise dans PostgreSQL (lecture/écriture du contexte)
        if active_company_id:
            _set_session_company(active_company_id)
        elif debug:

            logger.debug("Aucune entreprise active pour user_id=%s", user.id)

        # 7. Vérifier si group admin
        is_group_admin = False
        if not is_platform_admin and len(accessible_companies) > 1:
            admin_companies = [
                acc for acc in accessible_companies if acc.role == "admin"
            ]
            if len(admin_companies) >= 2:
                groups = set(acc.group_id for acc in admin_companies if acc.group_id)
                is_group_admin = len(groups) > 0

        # 8. Construire l'objet User complet
        user_data = User(
            id=str(user.id),
            email=user.email,
            first_name=profile_data.get("first_name"),
            last_name=profile_data.get("last_name"),
            is_platform_admin=is_platform_admin,
            is_group_admin=is_group_admin,
            accessible_companies=accessible_companies,
            active_company_id=active_company_id,
        )

        if debug:

            logger.debug(
                "Utilisateur chargé role=%s company=%s",
                user_data.role,
                active_company_id,
            )
        return user_data

    except HTTPException:
        raise
    except AuthApiError as e:

        logger.info("Auth Supabase refusée: %s", e)
        detail = getattr(e, "message", None) or str(e)
        if "expired" in detail.lower():
            detail = "Session expirée. Veuillez vous reconnecter."
        else:
            detail = f"Token invalide ou expiré : {detail}"
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
        )
    except Exception as e:
        if is_transient_supabase_error(e):
            logger.warning("get_current_user: erreur réseau transitoire Supabase: %s", e)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=(
                    "Connexion à la base temporairement indisponible. "
                    "Réessayez dans quelques secondes."
                ),
            ) from e
        logger.exception("get_current_user: erreur inattendue")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur interne du serveur: {str(e)}",
        )


def get_current_user_role(current_user: User = Depends(get_current_user)) -> str:
    """
    Dépendance qui retourne uniquement le rôle de l'utilisateur connecté
    pour l'entreprise active. Utile pour les vérifications de rôle dans les endpoints.
    """
    return current_user.role
