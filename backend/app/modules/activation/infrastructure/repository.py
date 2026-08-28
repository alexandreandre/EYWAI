"""Persistance des jetons d'activation (table employee_activation_tokens)."""

from __future__ import annotations

from typing import Any, Dict, Optional

from app.core.database import supabase

_TABLE = "employee_activation_tokens"


class ActivationTokenRepository:
    """Accès service (service_role) : la table est en RLS sans policy publique."""

    def invalidate_pending(self, employee_id: str, now_iso: str) -> None:
        """Tue les jetons encore vivants du salarié (ré-envoi = anciens morts)."""
        (
            supabase.table(_TABLE)
            .update({"invalidated_at": now_iso})
            .eq("employee_id", str(employee_id))
            .is_("used_at", "null")
            .is_("invalidated_at", "null")
            .execute()
        )

    def create(
        self,
        *,
        employee_id: str,
        company_id: str,
        token_hash: str,
        email_envoye: str,
        expires_at: str,
        created_by: Optional[str],
    ) -> None:
        (
            supabase.table(_TABLE)
            .insert(
                {
                    "employee_id": str(employee_id),
                    "company_id": str(company_id),
                    "token_hash": token_hash,
                    "email_envoye": email_envoye,
                    "expires_at": expires_at,
                    "created_by": str(created_by) if created_by else None,
                }
            )
            .execute()
        )

    def get_by_hash(self, token_hash: str) -> Optional[Dict[str, Any]]:
        response = (
            supabase.table(_TABLE)
            .select("*")
            .eq("token_hash", token_hash)
            .maybe_single()
            .execute()
        )
        data = getattr(response, "data", None) if response else None
        return dict(data) if data else None

    def list_live_by_lien_partage(self, lien_partage: str) -> list:
        """Tous les jetons encore ouverts qui partagent le même identifiant de lien."""
        value = (lien_partage or "").strip()
        if not value:
            return []
        response = (
            supabase.table(_TABLE)
            .select("*")
            .eq("lien_partage", value)
            .is_("used_at", "null")
            .is_("invalidated_at", "null")
            .execute()
        )
        rows = getattr(response, "data", None) or []
        return [dict(row) for row in rows]

    def mark_used(self, token_id: str, now_iso: str) -> None:
        (
            supabase.table(_TABLE)
            .update({"used_at": now_iso})
            .eq("id", str(token_id))
            .execute()
        )

    def get_latest_for_employee(self, employee_id: str) -> Optional[Dict[str, Any]]:
        response = (
            supabase.table(_TABLE)
            .select("*")
            .eq("employee_id", str(employee_id))
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        rows = getattr(response, "data", None) or []
        return dict(rows[0]) if rows else None
