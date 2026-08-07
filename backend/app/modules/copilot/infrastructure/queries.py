"""
Requêtes Supabase du module copilot.

Accès DB : profiles (company_id), employees (recherche floue), company_collective_agreements,
collective_agreement_texts. Toutes les lectures RH exigent un périmètre explicite.
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


def get_employees_for_fuzzy_search(company_id: str) -> list[dict[str, Any]]:
    """Retourne la liste minimale des employés (id, first_name, last_name, job_title) pour la recherche floue.

    Le filtre entreprise est obligatoire afin d'éviter de matcher un homonyme
    d'une autre filiale.
    """
    if not company_id or not company_id.strip():
        raise ValueError("company_id obligatoire pour la recherche d'employés.")
    supabase = get_supabase_client()
    query = (
        supabase.table("employees")
        .select("id, first_name, last_name, job_title")
        .eq("company_id", company_id)
    )
    response = query.execute()
    return response.data or []


def _get_agreement_text(supabase: Any, agreement_id: str) -> str | None:
    """Texte de la convention : ``base_text`` si disponible, sinon ``full_text``.

    La colonne ``base_text`` peut ne pas encore exister (code déployé avant sa
    migration) : dans ce cas on retombe sur ``full_text`` plutôt que de faire
    tomber toute la branche convention.
    """
    for colonnes in ("full_text, base_text", "full_text"):
        try:
            reponse = (
                supabase.table("collective_agreement_texts")
                .select(colonnes)
                .eq("agreement_id", agreement_id)
                .maybe_single()
                .execute()
            )
        except Exception as exc:  # noqa: BLE001 - on retente sans base_text
            logging.warning(
                "Lecture du texte de convention (%s) impossible: %s", colonnes, exc
            )
            continue
        if not reponse.data:
            return None
        return (
            reponse.data.get("base_text") or reponse.data.get("full_text") or None
        )
    return None


def get_company_name(company_id: str) -> str:
    """Nom de l'entreprise active, pour ancrer les réponses.

    Sans lui, l'assistant reprend le nom d'entreprise énoncé dans la question.
    Éprouvé : demandé depuis MAJI « liste les salariés de Colorplast », il a
    renvoyé les salariés de MAJI — la bonne donnée, l'entreprise imposée par le
    serveur — mais en les présentant comme ceux de Colorplast. La donnée était
    juste, la phrase était fausse.
    """
    if not company_id or not str(company_id).strip():
        return ""
    try:
        reponse = (
            get_supabase_client()
            .table("companies")
            .select("company_name")
            .eq("id", company_id)
            .maybe_single()
            .execute()
        )
        if reponse and reponse.data:
            return str(reponse.data.get("company_name") or "")
    except Exception as exc:  # noqa: BLE001 - l'absence de nom n'est pas bloquante
        logging.warning("Nom d'entreprise introuvable pour le Copilot: %s", exc)
    return ""


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
            # ``base_text`` est le texte de base intégral de la convention ;
            # ``full_text`` est le corpus paie (avenants salaires, annexes), qui
            # ne contient ni période d'essai, ni préavis, ni congés. On préfère
            # donc le premier, avec repli sur le second tant qu'une convention
            # n'a pas encore été rapatriée.
            full_text = _get_agreement_text(supabase, agreement_id)
            agreements.append(
                {
                    "id": agreement_id,
                    "name": catalog_data.get("name"),
                    "idcc": catalog_data.get("idcc"),
                    "description": catalog_data.get("description"),
                    "sector": catalog_data.get("sector"),
                    "full_text": full_text,
                    "has_text_cached": full_text is not None,
                }
            )
        return agreements
    except Exception as e:
        logging.error(
            "Erreur lors de la récupération des conventions collectives: %s", e
        )
        return []
