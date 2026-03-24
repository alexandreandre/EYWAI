# Mappers DB → structures utilisées par l'application (comportement identique au router).
# Pas de dépendance aux schémas Pydantic ; retour de dict pour construction des réponses.
from typing import Any, Dict, Optional


def build_history_entry_dict(
    row: Dict[str, Any],
    generated_by_name: str,
) -> Dict[str, Any]:
    """
    Construit le dict pour une ExportHistoryEntry à partir d'une ligne exports_history.
    Comportement identique à la construction dans GET /history.
    """
    report = row.get("report", {})
    totals_dict = report.get("totals", {}) if isinstance(report, dict) else {}
    return {
        "id": row["id"],
        "export_type": row["export_type"],
        "period": row["period"],
        "status": row["status"],
        "generated_at": row["generated_at"],
        "generated_by": row["generated_by"],
        "generated_by_name": generated_by_name,
        "files_count": len(row.get("file_paths", [])),
        "totals": totals_dict if totals_dict else None,
    }


def build_display_name_from_profile(profile: Optional[Dict[str, Any]]) -> str:
    """Construit le nom affiché à partir d'un profil (first_name, last_name). Retourne 'Utilisateur' si absent."""
    if not profile:
        return "Utilisateur"
    name = f"{profile.get('first_name', '')} {profile.get('last_name', '')}".strip()
    return name or "Utilisateur"
