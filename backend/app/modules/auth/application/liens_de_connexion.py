"""Lien d'invitation : la personne invitée crée son mot de passe, puis se connecte.

Un lien est créé pour un compte et remis à la main (valable 7 jours, usage unique). Il ouvre
la page « Créez votre mot de passe » (/connexion?jeton=…) : l'ouvrir ne consomme rien, si
bien qu'un aperçu de messagerie ou un antivirus qui suit l'adresse ne le grille pas. Le lien
ne sert qu'au moment où le mot de passe est enregistré ; la session s'ouvre alors avec ce
mot de passe. Ensuite, la personne se connecte normalement (adresse et mot de passe).

Seule l'empreinte SHA-256 du jeton est gardée en base (`liens_de_connexion`).
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

DUREE_INVITATION = timedelta(days=7)

CODE_LIEN_INVALIDE = "lien_invalide"
MESSAGE_LIEN_INVALIDE = (
    "Ce lien d'invitation n'est plus valable : il a déjà servi ou il a expiré. "
    "Demandez-en un nouveau à la personne qui vous l'a envoyé."
)


class LienInvalide(Exception):
    """Lien inconnu, déjà servi ou expiré (traduit en 400 `lien_invalide` par le service)."""


def empreinte(jeton: str) -> str:
    return hashlib.sha256(jeton.encode("utf-8")).hexdigest()


def _maintenant() -> datetime:
    return datetime.now(timezone.utc)


def _client():
    from app.core.database import get_supabase_admin_client

    return get_supabase_admin_client()


def creer_lien(user_id: str, origine: str, duree: timedelta, client=None) -> str:
    """Enregistre un lien pour ce compte et rend le jeton en clair (à mettre dans l'URL)."""
    jeton = secrets.token_urlsafe(32)
    (client or _client()).table("liens_de_connexion").insert(
        {
            "user_id": user_id,
            "jeton_hash": empreinte(jeton),
            "origine": origine,
            "expires_at": (_maintenant() + duree).isoformat(),
        }
    ).execute()
    return jeton


def url_du_lien(frontend_url: str, jeton: str) -> str:
    return f"{frontend_url.rstrip('/')}/connexion?jeton={jeton}"


def _jeton_lisible(jeton: str) -> bool:
    return bool(jeton) and len(jeton) <= 200


def compte_du_lien(jeton: str, client=None) -> Optional[str]:
    """Le compte d'un lien encore valable (ni servi, ni expiré), sans le consommer."""
    if not _jeton_lisible(jeton):
        return None
    lignes = (
        (client or _client())
        .table("liens_de_connexion")
        .select("user_id")
        .eq("jeton_hash", empreinte(jeton))
        .is_("used_at", "null")
        .gt("expires_at", _maintenant().isoformat())
        .limit(1)
        .execute()
        .data
    )
    return lignes[0]["user_id"] if lignes else None


def email_du_compte(user_id: str, client=None) -> str:
    return (client or _client()).auth.admin.get_user_by_id(user_id).user.email


def verifier_lien(jeton: str, client=None) -> dict:
    """Pour la page d'invitation : le lien est-il valable, et pour qui (prénom, adresse) ?"""
    client = client or _client()
    user_id = compte_du_lien(jeton, client)
    if not user_id:
        return {"valide": False, "prenom": None, "email": None}
    profil = (
        client.table("profiles").select("first_name").eq("id", user_id).limit(1).execute().data
    )
    email = email_du_compte(user_id, client)
    return {
        "valide": True,
        "prenom": profil[0].get("first_name") if profil else None,
        "email": email,
    }


def consommer_lien(jeton: str, client=None) -> str:
    """Marque le lien servi et rend son compte ; refuse un lien inconnu, servi ou expiré."""
    if not _jeton_lisible(jeton):
        raise LienInvalide(MESSAGE_LIEN_INVALIDE)
    client = client or _client()
    maintenant = _maintenant().isoformat()
    # Une seule mise à jour conditionnelle : deux envois simultanés ne servent pas deux fois.
    lignes = (
        client.table("liens_de_connexion")
        .update({"used_at": maintenant})
        .eq("jeton_hash", empreinte(jeton))
        .is_("used_at", "null")
        .gt("expires_at", maintenant)
        .execute()
        .data
    )
    if not lignes:
        raise LienInvalide(MESSAGE_LIEN_INVALIDE)
    return lignes[0]["user_id"]
