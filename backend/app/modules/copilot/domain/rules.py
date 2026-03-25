"""
Règles métier du module copilot.

À utiliser depuis la couche application uniquement.
"""

from __future__ import annotations


def only_select_allowed(sql_query: str) -> bool:
    """
    Vérifie que la requête SQL est une requête SELECT (lecture seule).

    Utilisée avant exécution pour bloquer toute modification (INSERT/UPDATE/DELETE/etc.).
    À appeler depuis l'application avant de déléguer à ISqlExecutor.
    """
    stripped = (sql_query or "").strip().lower()
    return stripped.startswith("select")
