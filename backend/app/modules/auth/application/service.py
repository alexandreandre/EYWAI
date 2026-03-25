# Orchestration login : résolution identifiant, sign_in, construction TokenWithUser.
# Utilise uniquement domain (règles) + infrastructure (ports). Comportement identique au legacy.

from __future__ import annotations

import traceback

from fastapi import HTTPException

from app.modules.auth.domain.rules import is_email_like
from app.modules.auth.infrastructure import (
    auth_provider,
    user_from_token,
    user_resolver,
)


def login(username_or_email: str, password: str) -> dict:
    """
    Connexion : si pas email (règle is_email_like), résout l’email via IUserByLoginResolver ;
    puis sign_in_with_password ; puis User via IUserFromToken.
    Retourne {"access_token", "token_type": "bearer", "user": User}.
    """
    try:
        print("\n" + "=" * 80)
        print("🔐 [LOGIN DEBUG] NOUVELLE TENTATIVE DE CONNEXION")
        print("=" * 80)
        print(f"📥 [LOGIN DEBUG] Input reçu (brut): '{username_or_email}'")
        print(f"📥 [LOGIN DEBUG] Type de l'input: {type(username_or_email)}")
        print(f"📥 [LOGIN DEBUG] Longueur: {len(username_or_email)}")
        print(f"📥 [LOGIN DEBUG] Password fourni (longueur): {len(password)}")

        login_input = username_or_email.strip().lower()
        print(f"🔧 [LOGIN DEBUG] Input après strip().lower(): '{login_input}'")
        print(f"🔧 [LOGIN DEBUG] Longueur après traitement: {len(login_input)}")

        if is_email_like(login_input):
            email_to_use = login_input
            print(f"📧 [LOGIN DEBUG] Détecté comme EMAIL: '{email_to_use}'")
        else:
            print(f"👤 [LOGIN DEBUG] Détecté comme USERNAME: '{login_input}'")
            print(
                f"🔍 [LOGIN DEBUG] Recherche dans la table 'employees' pour username='{login_input}'"
            )
            email_to_use = user_resolver.resolve_email(login_input)
            if not email_to_use:
                _log_employees_debug()
                raise HTTPException(
                    status_code=400, detail="Identifiant ou mot de passe incorrect"
                )
            print(f"✅ [LOGIN DEBUG] EMPLOYÉ TROUVÉ - Email: '{email_to_use}'")

        if not email_to_use:
            print("❌ [LOGIN DEBUG] email_to_use est vide ou None!")
            raise HTTPException(
                status_code=400, detail="Identifiant ou mot de passe incorrect"
            )

        print("🔑 [LOGIN DEBUG] Tentative de connexion Supabase Auth avec:")
        print(f"   - Email: '{email_to_use}'")
        print(f"   - Password longueur: {len(password)}")
        print("🔧 [LOGIN DEBUG] Création d'un client Supabase frais pour l'auth...")

        session = auth_provider.sign_in_with_password(email_to_use, password)
        access_token = session["access_token"]

        print("✅ [LOGIN DEBUG] CONNEXION RÉUSSIE!")
        print(f"   - Email utilisé: {email_to_use}")
        print(f"   - Token généré (30 premiers car.): {access_token[:30]}...")
        print("🔍 [LOGIN DEBUG] Récupération des informations utilisateur...")

        user_info = user_from_token.get_user(access_token)
        print(
            f"✅ [LOGIN DEBUG] Utilisateur complet récupéré - Super admin: {user_info.is_super_admin}"
        )
        print("=" * 80 + "\n")

        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user": user_info,
        }

    except HTTPException:
        print("⚠️  [LOGIN DEBUG] HTTPException levée")
        print("=" * 80 + "\n")
        raise
    except Exception as e:
        print("💥 [LOGIN DEBUG] EXCEPTION INATTENDUE!")
        print(f"   - Type: {type(e).__name__}")
        print(f"   - Message: {str(e)}")
        print(f"   - Traceback:\n{traceback.format_exc()}")
        print("=" * 80 + "\n")
        raise HTTPException(
            status_code=400, detail="Identifiant ou mot de passe incorrect"
        )


def _log_employees_debug() -> None:
    """Log debug contenu table employees (via infrastructure)."""
    from app.modules.auth.infrastructure.queries import get_employees_debug_snapshot

    print("❌ [LOGIN DEBUG] AUCUN EMPLOYÉ TROUVÉ")
    print("💡 [LOGIN DEBUG] Recherchons TOUS les usernames pour débugger...")
    data = get_employees_debug_snapshot()
    print("📋 [LOGIN DEBUG] Contenu COMPLET de la table employees:")
    print(f"   - Nombre total d'employés: {len(data)}")
    if data:
        for idx, user in enumerate(data, 1):
            print(f"\n   Employé #{idx}:")
            print(f"      - ID: {user.get('id')}")
            print(f"      - first_name: '{user.get('first_name')}'")
            print(f"      - last_name: '{user.get('last_name')}'")
            print(f"      - email: '{user.get('email')}'")
            print(f"      - username: '{user.get('username')}'")
            print(f"      - employee_folder_name: '{user.get('employee_folder_name')}'")
    else:
        print("   ⚠️  LA TABLE EST VIDE! Aucun employé n'existe dans Supabase.")
        print("   💡 Vous devez d'abord créer des employés avec des usernames.")
