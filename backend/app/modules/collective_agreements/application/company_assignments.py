"""
Tri et résolution des conventions collectives affiliées à une entreprise.
"""

from __future__ import annotations

from typing import Any, List, Optional


def is_active_affiliated_assignment(row: dict[str, Any]) -> bool:
    """Une assignation est valide si le catalogue associé est actif."""
    details = row.get("agreement_details") or {}
    return details.get("is_active", True) is not False


def sort_assignments_chronologically(rows: List[dict[str, Any]]) -> List[dict[str, Any]]:
    """Première CC ajoutée en premier (assigned_at croissant)."""
    return sorted(rows, key=lambda row: str(row.get("assigned_at") or ""))


def normalize_company_assignments(rows: List[dict[str, Any]]) -> List[dict[str, Any]]:
    """CC affiliées actives, triées par ordre d'ajout."""
    active = [row for row in rows if is_active_affiliated_assignment(row)]
    return sort_assignments_chronologically(active)


def fetch_first_company_collective_agreement_id(
    company_id: str,
    *,
    supabase_client: Any,
) -> Optional[str]:
    """Retourne l'ID catalogue de la première CC affiliée (chronologique)."""
    if not company_id:
        return None
    try:
        response = (
            supabase_client.table("company_collective_agreements")
            .select(
                "collective_agreement_id, assigned_at, "
                "agreement_details:collective_agreement_id(is_active)"
            )
            .eq("company_id", company_id)
            .order("assigned_at")
            .execute()
        )
        rows = normalize_company_assignments(list(response.data or []))
        if not rows:
            return None
        return rows[0].get("collective_agreement_id")
    except Exception:
        return None
