"""Les fiches du groupe, pour comparer un salarié à ses collègues."""

from __future__ import annotations

from typing import Any, Dict, List

from app.core.database import supabase
from app.modules.pcs_ese.domain.proposition import FicheCollegue


def _code(classification: Any) -> str:
    if isinstance(classification, dict):
        return str(classification.get("pcs") or "").strip()
    return ""


def fiches_du_groupe(company_id: str) -> List[FicheCollegue]:
    """Les fiches de toutes les sociétés du groupe de `company_id` (la société seule sinon)."""
    societe = (
        supabase.table("companies")
        .select("id, company_name, group_id")
        .eq("id", company_id)
        .maybe_single()
        .execute()
    )
    ligne: Dict[str, Any] = (societe.data if societe else None) or {}
    if not ligne:
        return []
    societes = [ligne]
    if ligne.get("group_id"):
        r = (
            supabase.table("companies")
            .select("id, company_name, group_id")
            .eq("group_id", ligne["group_id"])
            .execute()
        )
        societes = r.data or societes
    noms = {str(s["id"]): str(s.get("company_name") or "") for s in societes}
    r = (
        supabase.table("employees")
        .select("id, company_id, job_title, statut, classification_conventionnelle")
        .in_("company_id", list(noms))
        .execute()
    )
    return [
        FicheCollegue(
            employee_id=str(e["id"]),
            company_id=str(e["company_id"]),
            societe=noms.get(str(e["company_id"]), ""),
            poste=str(e.get("job_title") or ""),
            statut=str(e.get("statut") or ""),
            code=_code(e.get("classification_conventionnelle")),
        )
        for e in (r.data or [])
    ]
