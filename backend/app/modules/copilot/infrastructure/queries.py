"""
Requêtes Supabase du module copilot.

Accès DB : profiles (company_id), employees (recherche floue), company_collective_agreements,
collective_agreement_texts. Comportement strictement identique au legacy.
"""
from __future__ import annotations

import logging
from typing import Any

from app.core.database import get_supabase_client


def get_company_id_for_user(user_id: str) -> str | None:
    """Récupère le company_id du profil utilisateur."""
    supabase = get_supabase_client()
    response = (
        supabase.table("profiles")
        .select("company_id")
        .eq("id", user_id)
        .single()
        .execute()
    )
    if not response.data or not response.data.get("company_id"):
        return None
    return response.data["company_id"]


def get_employees_for_fuzzy_search() -> list[dict[str, Any]]:
    """Retourne la liste minimale des employés (id, first_name, last_name, job_title) pour la recherche floue."""
    supabase = get_supabase_client()
    response = supabase.table("employees").select(
        "id, first_name, last_name, job_title"
    ).execute()
    return response.data or []


def get_company_collective_agreements(company_id: str) -> list[dict[str, Any]]:
    """
    Récupère les conventions collectives assignées à l'entreprise avec texte en cache.
    Retourne une liste de dicts avec id, name, idcc, description, sector, full_text, has_text_cached.
    """
    try:
        supabase = get_supabase_client()
        response = (
            supabase.table("company_collective_agreements")
            .select("*, collective_agreements_catalog(*)")
            .eq("company_id", company_id)
            .execute()
        )
        if not response.data:
            return []

        agreements = []
        for assignment in response.data:
            catalog_data = assignment.get("collective_agreements_catalog")
            if not catalog_data:
                continue
            agreement_id = catalog_data["id"]
            text_response = (
                supabase.table("collective_agreement_texts")
                .select("full_text")
                .eq("agreement_id", agreement_id)
                .maybe_single()
                .execute()
            )
            full_text = None
            if text_response.data and text_response.data.get("full_text"):
                full_text = text_response.data["full_text"]
            agreements.append({
                "id": agreement_id,
                "name": catalog_data.get("name"),
                "idcc": catalog_data.get("idcc"),
                "description": catalog_data.get("description"),
                "sector": catalog_data.get("sector"),
                "full_text": full_text,
                "has_text_cached": full_text is not None,
            })
        return agreements
    except Exception as e:
        logging.error("Erreur lors de la récupération des conventions collectives: %s", e)
        return []
