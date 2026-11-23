"""Connexion par lien, sans mot de passe.

Deux façons d'obtenir un lien :
- l'invitation : un lien créé pour un compte et remis à la main (valable 7 jours) ;
- la demande : sur la page de connexion, « Recevoir un lien de connexion » envoie par e-mail
  un lien valable 30 minutes.

Un lien sert une fois. Seule l'empreinte SHA-256 du jeton est gardée en base
(`liens_de_connexion`). À l'ouverture, le serveur fait émettre par Supabase Auth un jeton
magique pour ce compte et le vérifie aussitôt : la session obtenue est la même qu'après un
mot de passe (jeton d'accès et de renouvellement).

La demande répond toujours la même chose, que l'adresse ait un compte ou non.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Optional

from app.core.logging import get_logger

logger = get_logger("modules.auth.liens")

DUREE_INVITATION = timedelta(days=7)
DUREE_DEMANDE = timedelta(minutes=30)

MESSAGE_DEMANDE = (
    "Si un compte existe pour cette adresse, un lien de connexion vient d'y être envoyé. "
    "Il est valable 30 minutes."
)
CODE_LIEN_INVALIDE = "lien_invalide"
MESSAGE_LIEN_INVALIDE = (
    "Ce lien de connexion n'est plus valable : il a déjà servi ou il a expiré. "
    "Demandez-en un nouveau sur la page de connexion."
)


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


def _compte_par_adresse(client, email: str) -> Optional[Any]:
    from app.modules.auth.infrastructure import auth_provider

    user_id = auth_provider.find_user_id_by_email(email)
    if not user_id:
        return None
    acces = (
        client.table("user_company_accesses")
        .select("company_id")
        .eq("user_id", user_id)
        .eq("is_active", True)
        .limit(1)
        .execute()
        .data
    )
    return user_id if acces else None


def demander_lien(email: str, envoyer: Optional[Callable[..., bool]] = None, client=None) -> dict:
    """Envoie un lien de connexion à cette adresse si elle a un compte avec des accès."""
    email = (email or "").strip().lower()
    reponse = {"message": MESSAGE_DEMANDE}
    if "@" not in email:
        return reponse
    client = client or _client()
    try:
        user_id = _compte_par_adresse(client, email)
        if not user_id:
            return reponse
        jeton = creer_lien(user_id, "demande", DUREE_DEMANDE, client)
        if envoyer is None:
            from app.shared.infrastructure.email import send_lien_de_connexion_email as envoyer
        envoyer(to_email=email, jeton=jeton)
    except Exception:
        logger.warning("Lien de connexion : demande non aboutie", exc_info=True)
    return reponse


class LienInvalide(Exception):
    """Lien inconnu, déjà servi ou expiré (traduit en 400 `lien_invalide` par le service)."""


def _refus_lien() -> LienInvalide:
    return LienInvalide(MESSAGE_LIEN_INVALIDE)


def consommer_lien(jeton: str, client=None) -> str:
    """Marque le lien servi et rend son compte ; refuse un lien inconnu, servi ou expiré."""
    if not jeton or len(jeton) > 200:
        raise _refus_lien()
    client = client or _client()
    maintenant = _maintenant().isoformat()
    # Une seule mise à jour conditionnelle : deux clics simultanés ne servent pas deux fois.
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
        raise _refus_lien()
    return lignes[0]["user_id"]


def session_du_compte(user_id: str, client=None) -> dict:
    """Ouvre une session Supabase pour ce compte, sans mot de passe (jeton magique vérifié)."""
    from supabase import create_client

    from app.core.settings import get_supabase_anon_env

    client = client or _client()
    email = client.auth.admin.get_user_by_id(user_id).user.email
    lien = client.auth.admin.generate_link({"type": "magiclink", "email": email})
    anon_url, anon_key = get_supabase_anon_env()
    res = create_client(anon_url, anon_key).auth.verify_otp(
        {"token_hash": lien.properties.hashed_token, "type": "magiclink"}
    )
    session = res.session
    return {
        "access_token": session.access_token,
        "refresh_token": session.refresh_token,
        "expires_in": session.expires_in,
        "expires_at": session.expires_at,
    }
