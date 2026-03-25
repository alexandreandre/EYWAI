"""
Requêtes Supabase pour collective_agreements.

Lecture convention_classifications (grille par IDCC). Utilise domain.rules.idcc_variants.
"""

from __future__ import annotations

from typing import Any, List

from app.modules.collective_agreements.domain.rules import idcc_variants


def get_classifications_for_idcc(supabase_client: Any, idcc: str) -> List[Any]:
    """
    Récupère la grille convention_classifications pour un idcc donné.
    Essaie les variantes (brut, sans zéros, zfill(4)).
    """
    idcc_raw = (idcc or "").strip()
    for variant in idcc_variants(idcc_raw):
        if not variant:
            continue
        r = (
            supabase_client.table("convention_classifications")
            .select("classifications")
            .eq("idcc", variant)
            .maybe_single()
            .execute()
        )
        if r.data and r.data.get("classifications") is not None:
            return r.data["classifications"]
    return []
