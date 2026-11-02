"""Persistance des formules de prévoyance (company_prevoyance_formules)."""

from __future__ import annotations

from typing import Any

from app.core.database import supabase

TABLE = "company_prevoyance_formules"


class DepotFormulesPrevoyance:
    def lister(self, company_id: str) -> list[dict[str, Any]]:
        r = supabase.table(TABLE).select("*").eq("company_id", company_id).order("libelle").execute()
        return list(r.data or [])

    def lire(self, formule_id: str, company_id: str) -> dict[str, Any] | None:
        r = (
            supabase.table(TABLE)
            .select("*")
            .eq("id", formule_id)
            .eq("company_id", company_id)
            .limit(1)
            .execute()
        )
        return (r.data or [None])[0]

    def creer(self, row: dict[str, Any]) -> dict[str, Any]:
        r = supabase.table(TABLE).insert(row).execute()
        if not r.data:
            raise RuntimeError("Création de la formule de prévoyance sans données retournées")
        return r.data[0]

    def modifier(self, formule_id: str, company_id: str, patch: dict[str, Any]) -> dict[str, Any]:
        r = (
            supabase.table(TABLE)
            .update({**patch, "updated_at": "now()"})
            .eq("id", formule_id)
            .eq("company_id", company_id)
            .execute()
        )
        if not r.data:
            raise RuntimeError("Modification de la formule de prévoyance sans données retournées")
        return r.data[0]

    def fiches_de_la_societe(self, company_id: str) -> list[dict[str, Any]]:
        r = supabase.table("employees").select("id, specificites_paie").eq("company_id", company_id).execute()
        return list(r.data or [])


depot_formules_prevoyance = DepotFormulesPrevoyance()
