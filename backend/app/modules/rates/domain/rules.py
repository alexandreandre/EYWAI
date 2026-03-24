"""
Règles métier pures pour le module rates.

Sélection de la ligne retenue par config_key (version puis created_at) et
forme de sortie (clés exposées). Aucune I/O, aucun FastAPI.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

# Clés exposées pour une catégorie de taux (contrat de sortie API, identique au legacy).
RATE_CATEGORY_OUTPUT_KEYS = (
    "config_data",
    "version",
    "last_checked_at",
    "comment",
    "source_links",
)


def _is_row_better(candidate: dict[str, Any], current: dict[str, Any]) -> bool:
    """
    True si candidate doit remplacer current pour la même config_key.
    Priorité : version la plus haute ; à égalité, created_at la plus récente.
    """
    v_c = candidate.get("version") or 0
    v_cur = current.get("version") or 0
    if v_c > v_cur:
        return True
    if v_c < v_cur:
        return False
    t_c = candidate.get("created_at") or "1970-01-01T00:00:00Z"
    t_cur = current.get("created_at") or "1970-01-01T00:00:00Z"
    return datetime.fromisoformat(t_c.replace("Z", "+00:00")) > datetime.fromisoformat(
        t_cur.replace("Z", "+00:00")
    )


def group_and_select_best(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """
    Regroupe les lignes par config_key et garde une seule ligne par clé.

    Règle : pour chaque config_key, on garde la ligne avec la version la plus haute ;
    à égalité, la ligne avec created_at la plus récente.
    Retour : dict[config_key, row] (row = ligne complète).
    """
    grouped: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = row.get("config_key")
        if not key:
            continue
        current = grouped.get(key)
        if not current or _is_row_better(row, current):
            grouped[key] = dict(row)
    return grouped


def build_rate_category_output(row: dict[str, Any]) -> dict[str, Any]:
    """
    Construit le dict de sortie pour une catégorie (contrat API legacy).

    Retourne uniquement les clés RATE_CATEGORY_OUTPUT_KEYS.
    """
    return {k: row.get(k) for k in RATE_CATEGORY_OUTPUT_KEYS}
