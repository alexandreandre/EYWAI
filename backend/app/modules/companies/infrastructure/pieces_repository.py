"""Accès au stockage des pièces de la société (aucune table)."""

from __future__ import annotations

from typing import Any

from app.core.database import get_supabase_admin_client

BUCKET = "generated_documents"
DUREE_DU_LIEN = 300


def lister_dossier(dossier: str) -> list[dict[str, Any]]:
    sb = get_supabase_admin_client()
    return sb.storage.from_(BUCKET).list(dossier, {"limit": 100}) or []


def deposer(chemin: str, contenu: bytes, format_fichier: str) -> None:
    sb = get_supabase_admin_client()
    sb.storage.from_(BUCKET).upload(
        path=chemin, file=contenu, file_options={"content-type": format_fichier}
    )


def lien_signe(chemin: str) -> str:
    sb = get_supabase_admin_client()
    reponse = sb.storage.from_(BUCKET).create_signed_url(chemin, DUREE_DU_LIEN)
    return reponse.get("signedURL") or reponse.get("signedUrl") or ""


def supprimer(chemin: str) -> None:
    sb = get_supabase_admin_client()
    sb.storage.from_(BUCKET).remove([chemin])


def a_une_convention(company_id: str) -> bool:
    sb = get_supabase_admin_client()
    lignes = (
        sb.table("company_collective_agreements")
        .select("id")
        .eq("company_id", company_id)
        .limit(1)
        .execute()
        .data
    )
    return bool(lignes)


def reglages_jei(company_id: str) -> dict[str, Any] | None:
    sb = get_supabase_admin_client()
    lignes = (
        sb.table("company_jei_settings")
        .select("jei_enabled, date_creation_etablissement")
        .eq("company_id", company_id)
        .limit(1)
        .execute()
        .data
    )
    return lignes[0] if lignes else None
