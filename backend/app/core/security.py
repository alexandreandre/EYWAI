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

import traceback
from typing import Annotated, Optional

from fastapi import Depends, HTTPException, Header, status
from fastapi.security import OAuth2PasswordBearer
from gotrue.errors import AuthApiError

from app.core.database import supabase
from app.modules.users.schemas.responses import CompanyAccess, User

# Schéma OAuth2 pour l'endpoint de login
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


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
    try:
        print("--- 🕵️ [get_current_user] Validation du token...")
        print(f"--- 🏢 [get_current_user] X-Active-Company header: {x_active_company}")

        # 1. Authentifier l'utilisateur
        user_response = supabase.auth.get_user(token)
        user = user_response.user
        if not user:
            print("--- ❌ [get_current_user] Token valide mais aucun utilisateur trouvé.")
            raise HTTPException(status_code=401, detail="Utilisateur non trouvé")

        print(f"--- ✅ [get_current_user] Utilisateur authentifié: {user.email} (ID: {user.id})")

        # 2. Récupérer le profil de base
        print("--- 🕵️ [get_current_user] Récupération du profil...")
        profile_response = (
            supabase.table("profiles").select("first_name, last_name").eq("id", user.id).execute()
        )

        if not profile_response.data or len(profile_response.data) == 0:
            print(f"--- ❌ [get_current_user] Profil non trouvé pour l'utilisateur ID: {user.id}")
            raise HTTPException(status_code=404, detail="Profil utilisateur non trouvé")

        profile_data = profile_response.data[0]

        # 3. Vérifier si super admin
        print("--- 🕵️ [get_current_user] Vérification statut super admin...")
        super_admin_response = (
            supabase.table("super_admins")
            .select("*")
            .eq("user_id", user.id)
            .eq("is_active", True)
            .execute()
        )
        is_super_admin = bool(super_admin_response.data and len(super_admin_response.data) > 0)
        print(f"--- {'👑' if is_super_admin else '👤'} [get_current_user] Super admin: {is_super_admin}")

        # 4. Charger les accès multi-entreprises
        print("--- 🕵️ [get_current_user] Chargement des accès multi-entreprises...")
        accesses_response = (
            supabase.table("user_company_accesses")
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
                    group_logo_scale = company_data["company_groups"].get("logo_scale", 1.0)

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

        print(f"--- 📊 [get_current_user] Entreprises accessibles: {len(accessible_companies)}")

        # 5. Déterminer l'entreprise active
        active_company_id = None

        if is_super_admin and x_active_company:
            active_company_id = x_active_company
            print(f"--- 👑 [get_current_user] Super admin - Entreprise active depuis header: {active_company_id}")
        elif x_active_company:
            if any(acc.company_id == x_active_company for acc in accessible_companies):
                active_company_id = x_active_company
                print(f"--- ✅ [get_current_user] Entreprise active depuis header (validée): {active_company_id}")
            else:
                print(
                    f"--- ⚠️  [get_current_user] Header X-Active-Company invalide (entreprise non accessible): {x_active_company}"
                )
                print("--- 🔄 [get_current_user] Utilisation de l'entreprise primaire à la place...")

        if not active_company_id and accessible_companies:
            primary = next((acc for acc in accessible_companies if acc.is_primary), None)
            if primary:
                active_company_id = primary.company_id
                print(f"--- 📍 [get_current_user] Entreprise active: primaire par défaut ({primary.company_name})")
            else:
                active_company_id = accessible_companies[0].company_id
                print("--- 📍 [get_current_user] Entreprise active: première de la liste")

        # 6. Définir le contexte d'entreprise dans PostgreSQL (lecture/écriture du contexte)
        print("")
        print("=" * 80)
        print(f"🎯 [get_current_user] ENTREPRISE ACTIVE FINALE: {active_company_id}")
        print("=" * 80)
        print("")

        if active_company_id:
            print(f"--- 🔧 [get_current_user] Définition du contexte PostgreSQL: {active_company_id}")
            try:
                supabase.rpc("set_session_company", {"p_company_id": active_company_id}).execute()
                print(
                    f"--- ✅ [get_current_user] Contexte PostgreSQL défini avec succès pour: {active_company_id}"
                )
            except Exception as e:
                print(f"--- ⚠️  [get_current_user] Erreur lors de la définition du contexte: {e}")
        else:
            print(
                "--- ⚠️  [get_current_user] AUCUNE ENTREPRISE ACTIVE - Contexte PostgreSQL NON défini"
            )

        # 7. Vérifier si group admin
        is_group_admin = False
        if not is_super_admin and len(accessible_companies) > 1:
            admin_companies = [acc for acc in accessible_companies if acc.role == "admin"]
            if len(admin_companies) >= 2:
                groups = set(acc.group_id for acc in admin_companies if acc.group_id)
                is_group_admin = len(groups) > 0

        print(f"--- {'🏢' if is_group_admin else '👤'} [get_current_user] Group admin: {is_group_admin}")

        # 8. Construire l'objet User complet
        user_data = User(
            id=str(user.id),
            email=user.email,
            first_name=profile_data.get("first_name"),
            last_name=profile_data.get("last_name"),
            is_super_admin=is_super_admin,
            is_group_admin=is_group_admin,
            accessible_companies=accessible_companies,
            active_company_id=active_company_id,
        )

        print(
            f"--- ✅ [get_current_user] Utilisateur complet: {user_data.email} | Rôle actif: {user_data.role} | Entreprise: {active_company_id}"
        )
        return user_data

    except HTTPException:
        raise
    except AuthApiError as e:
        print(f"--- ❌ [get_current_user] Erreur d'API Supabase Auth: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token invalide ou expiré: {e.message}",
        )
    except Exception as e:
        print(f"--- ❌ [get_current_user] Erreur inattendue: {e}")
        traceback.print_exc()
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
