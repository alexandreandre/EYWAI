# Repository exports_history — écriture uniquement (insert).
# Les lectures sont dans infrastructure/queries.py.
from typing import Any, Dict, Optional

from app.core.database import supabase


def insert_export_record(record: Dict[str, Any]) -> Optional[str]:
    """Insère un enregistrement dans exports_history. Retourne l'id créé ou None."""
    response = supabase.table("exports_history").insert(record).execute()
    if response.data and len(response.data) > 0:
        return response.data[0].get("id")
    return None
