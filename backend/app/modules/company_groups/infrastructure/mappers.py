"""
Mappers DB -> DTOs pour company_groups.
Agrège les lignes Supabase (plusieurs lignes par groupe si join companies) en une liste de groupes avec companies.
"""

from __future__ import annotations

from typing import Any, Dict, List


def _normalize_companies_entry(company: Dict[str, Any]) -> Dict[str, Any]:
    """Une entrée company pour la liste (id, company_name, siret, is_active)."""
    return {
        "id": company["id"],
        "company_name": company["company_name"],
        "siret": company.get("siret"),
        "is_active": company.get("is_active", True),
    }


def rows_to_groups_with_companies(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Déduplique et agrège les lignes (plusieurs lignes par groupe si join companies).
    Comportement identique au router : groups_dict[group_id], append companies sans doublon.
    """
    groups_dict: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        group_id = row["id"]
        if group_id not in groups_dict:
            groups_dict[group_id] = {
                "id": row["id"],
                "group_name": row["group_name"],
                "siren": row.get("siren"),
                "description": row.get("description"),
                "logo_url": row.get("logo_url"),
                "is_active": row["is_active"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
                "companies": [],
            }
        companies_data = row.get("companies")
        if companies_data:
            if isinstance(companies_data, dict):
                companies_list = [companies_data]
            else:
                companies_list = companies_data
            for company in companies_list:
                entry = _normalize_companies_entry(company)
                if entry not in groups_dict[group_id]["companies"]:
                    groups_dict[group_id]["companies"].append(entry)
    return list(groups_dict.values())


def row_to_group_with_companies(row: Dict[str, Any]) -> Dict[str, Any]:
    """Une seule ligne groupe + companies (déjà une liste ou un objet) -> structure groupe."""
    companies = row.get("companies") or []
    if isinstance(companies, dict):
        companies = [companies]
    return {
        "id": row["id"],
        "group_name": row["group_name"],
        "siren": row.get("siren"),
        "description": row.get("description"),
        "logo_url": row.get("logo_url"),
        "is_active": row["is_active"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "companies": [_normalize_companies_entry(c) for c in companies],
    }
