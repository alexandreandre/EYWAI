# Cas d'usage en écriture du module auth.
# Utilise uniquement domain (règles) + infrastructure (ports, queries). Comportement identique au legacy.

from __future__ import annotations

import secrets
import traceback
from datetime import datetime, timezone, timedelta

from fastapi import HTTPException

from app.modules.auth.domain.rules import RESET_TOKEN_VALIDITY_HOURS
from app.modules.auth.infrastructure import (
    auth_provider,
    email_sender,
    reset_token_repository,
)
from app.modules.auth.infrastructure.queries import get_profile_display_name


def request_password_reset(email: str) -> dict:
    """
    Demande de réinitialisation : recherche user par email (IAuthProvider), profil (queries),
    token (règle durée), stockage (IResetTokenStore), envoi email (IEmailSender).
    Retourne toujours le même message (sécurité).
    """
    try:
        print("\n" + "=" * 80)
        print("🔐 [PASSWORD RESET] DEMANDE DE RÉINITIALISATION")
        print("=" * 80)
        print(f"📧 Email reçu: {email}")

        try:
            user_id = auth_provider.find_user_id_by_email(email)
            if not user_id:
                print(f"⚠️  [PASSWORD RESET] Email non trouvé dans auth.users: {email}")
                return {
                    "message": "Si cet e-mail existe, un lien de réinitialisation a été envoyé"
                }
            print(f"✅ [PASSWORD RESET] Utilisateur trouvé (ID: {user_id})")
        except Exception as e:
            print(
                f"⚠️  [PASSWORD RESET] Erreur lors de la recherche de l'utilisateur: {e}"
            )
            return {
                "message": "Si cet e-mail existe, un lien de réinitialisation a été envoyé"
            }

        user_name = get_profile_display_name(user_id, email.split("@")[0])
        print(f"✅ [PASSWORD RESET] Profil / nom: {user_name}")

        reset_token = secrets.token_urlsafe(32)
        print(f"🔑 [PASSWORD RESET] Token généré: {reset_token[:10]}...")

        expires_at = datetime.now(timezone.utc) + timedelta(
            hours=RESET_TOKEN_VALIDITY_HOURS
        )
        print(f"⏰ [PASSWORD RESET] Expiration: {expires_at}")

        reset_token_repository.create(
            user_id=user_id,
            email=email.lower(),
            token=reset_token,
            expires_at=expires_at.isoformat(),
        )
        print("✅ [PASSWORD RESET] Token sauvegardé dans la BDD")

        email_sent = email_sender.send_password_reset(
            to_email=email,
            reset_token=reset_token,
            user_name=user_name,
        )
        if email_sent:
            print(f"✅ [PASSWORD RESET] E-mail envoyé avec succès à {email}")
        else:
            print("⚠️  [PASSWORD RESET] Échec de l'envoi de l'e-mail")

        print("=" * 80 + "\n")
        return {
            "message": "Si cet e-mail existe, un lien de réinitialisation a été envoyé"
        }

    except Exception as e:
        print(f"❌ [PASSWORD RESET] Erreur: {e}")
        print(traceback.format_exc())
        return {
            "message": "Si cet e-mail existe, un lien de réinitialisation a été envoyé"
        }


def reset_password(token: str, new_password: str) -> dict:
    """
    Confirmation reset : token via IResetTokenStore, vérif expiration, update password (IAuthProvider), mark_used.
    """
    try:
        print("\n" + "=" * 80)
        print("🔐 [PASSWORD RESET] CONFIRMATION DE RÉINITIALISATION")
        print("=" * 80)
        print(f"🔑 Token reçu: {token[:10]}...")

        token_data = reset_token_repository.get_valid(token)
        if not token_data:
            print("❌ [PASSWORD RESET] Token invalide ou déjà utilisé")
            raise HTTPException(status_code=400, detail="Token invalide ou expiré")

        print(f"✅ [PASSWORD RESET] Token trouvé pour user_id: {token_data['user_id']}")

        expires_at = datetime.fromisoformat(
            token_data["expires_at"].replace("Z", "+00:00")
        )
        if datetime.now(expires_at.tzinfo) > expires_at:
            print(f"❌ [PASSWORD RESET] Token expiré (expiration: {expires_at})")
            raise HTTPException(status_code=400, detail="Token expiré")

        print(f"✅ [PASSWORD RESET] Token valide (expire à {expires_at})")
        print(
            f"🔄 [PASSWORD RESET] Mise à jour du mot de passe pour user_id: {token_data['user_id']}"
        )

        auth_provider.update_user_password(token_data["user_id"], new_password)
        print("✅ [PASSWORD RESET] Mot de passe mis à jour avec succès")

        reset_token_repository.mark_used(token)
        print("✅ [PASSWORD RESET] Token marqué comme utilisé")
        print("=" * 80 + "\n")

        return {"message": "Mot de passe réinitialisé avec succès"}

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ [PASSWORD RESET] Erreur: {e}")
        print(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail="Erreur lors de la réinitialisation du mot de passe",
        )


def change_password(
    user_id: str,
    user_email: str,
    current_password: str,
    new_password: str,
) -> dict:
    """
    Changement mot de passe (utilisateur connecté) : vérifie current via sign_in, puis update via IAuthProvider.
    """
    try:
        print("\n" + "=" * 80)
        print("🔐 [CHANGE PASSWORD] CHANGEMENT DE MOT DE PASSE")
        print("=" * 80)
        print(f"👤 Utilisateur: {user_email} (ID: {user_id})")
        print("🔍 [CHANGE PASSWORD] Vérification du mot de passe actuel...")

        try:
            auth_provider.sign_in_with_password(user_email, current_password)
            print("✅ [CHANGE PASSWORD] Mot de passe actuel vérifié")
        except HTTPException:
            raise
        except Exception as auth_error:
            print(f"❌ [CHANGE PASSWORD] Échec de la vérification: {auth_error}")
            raise HTTPException(
                status_code=400,
                detail="Mot de passe actuel incorrect",
            )

        print("🔄 [CHANGE PASSWORD] Mise à jour du mot de passe...")
        auth_provider.update_user_password(user_id, new_password)
        print("✅ [CHANGE PASSWORD] Mot de passe mis à jour avec succès")
        print("=" * 80 + "\n")
        return {"message": "Mot de passe modifié avec succès"}

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ [CHANGE PASSWORD] Erreur: {e}")
        print(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail="Erreur lors du changement de mot de passe",
        )


def logout() -> dict:
    """Déconnexion : IAuthProvider.sign_out."""
    try:
        auth_provider.sign_out()
        return {"message": "Déconnexion réussie"}
    except Exception:
        return {"message": "Déconnexion réussie"}
