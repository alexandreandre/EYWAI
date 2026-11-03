"""Les destinataires « côté RH », servis en direct malgré la redirection du test (03/11/2026).

Sous `EMAIL_FORCE_REDIRECT_TO`, un e-mail part à la boîte de renvoi, sauf pour les adresses de
`ACTIVATION_EMAIL_ALLOWLIST` et, depuis le 03/11, pour les comptes côté RH (`est_compte_rh`).
Les collaborateurs restent redirigés. Toute panne de lecture ferme : rien n'est servi en direct.
"""

from __future__ import annotations

from typing import Any, Iterable

from app.core.database import get_supabase_admin_client
from app.core.logging import get_logger
from app.shared.domain.email_delivery import est_compte_rh
from app.shared.infrastructure.comptes_auth import tous_les_comptes

logger = get_logger("shared.email.destinataires_rh")


def _acces_et_permissions(client: Any, user_ids: list[str]) -> tuple[dict[str, list[dict]], dict[str, set[str]]]:
    """Accès par compte, et sociétés où un rôle custom porte une permission RH active."""
    lignes = (
        client.table("user_company_accesses")
        .select("user_id, company_id, role, is_active")
        .in_("user_id", user_ids)
        .execute()
        .data
        or []
    )
    acces: dict[str, list[dict]] = {}
    for ligne in lignes:
        acces.setdefault(str(ligne["user_id"]), []).append(ligne)
    custom = [u for u, ls in acces.items() if any(a.get("role") == "custom" for a in ls)]
    droits: dict[str, set[str]] = {}
    if custom:
        perms = (
            client.table("user_permissions")
            .select("user_id, company_id, permissions(required_role, is_active)")
            .in_("user_id", custom)
            .execute()
            .data
            or []
        )
        for p in perms:
            perm = p.get("permissions") or {}
            if perm.get("is_active", False) and perm.get("required_role") in ("rh", "admin"):
                droits.setdefault(str(p["user_id"]), set()).add(str(p.get("company_id")))
    return acces, droits


def adresses_rh(emails: Iterable[str]) -> frozenset[str]:
    """Parmi `emails`, celles (en minuscules) d'un compte côté RH ; vide en cas de panne."""
    voulues = {(e or "").strip().lower() for e in emails if (e or "").strip()}
    if not voulues:
        return frozenset()
    try:
        client = get_supabase_admin_client()
        par_email = {}
        for compte in tous_les_comptes(client):
            email = (getattr(compte, "email", None) or "").strip().lower()
            if email in voulues:
                par_email[email] = str(compte.id)
        if not par_email:
            return frozenset()
        acces, droits = _acces_et_permissions(client, list(par_email.values()))
        return frozenset(
            e for e, uid in par_email.items() if est_compte_rh(acces.get(uid, []), droits.get(uid, set()))
        )
    except Exception as exc:  # noqa: BLE001 - fermer : l'e-mail part à la boîte de renvoi
        logger.warning("Comptes côté RH non lus, e-mail redirigé : %s", exc)
        return frozenset()
