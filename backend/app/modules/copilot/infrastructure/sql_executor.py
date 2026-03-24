"""
Exécuteur SQL en lecture (RPC Supabase).

Implémente ISqlExecutor. Comportement strictement identique au legacy.
"""
from __future__ import annotations

from typing import Any

from app.core.database import get_supabase_client


class SupabaseSqlExecutor:
    """Exécute des requêtes SQL en lecture via la RPC execute_sql de Supabase."""

    def execute_read_only(self, query: str) -> Any:
        """Exécute une requête SQL (SELECT). Retourne les données brutes (rpc_response.data)."""
        supabase = get_supabase_client()
        rpc_response = supabase.rpc("execute_sql", {"query": query}).execute()
        return rpc_response.data


_sql_executor: SupabaseSqlExecutor | None = None


def get_sql_executor() -> SupabaseSqlExecutor:
    """Retourne l'instance partagée de l'exécuteur SQL."""
    global _sql_executor
    if _sql_executor is None:
        _sql_executor = SupabaseSqlExecutor()
    return _sql_executor
