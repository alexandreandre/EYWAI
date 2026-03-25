"""
Commandes applicatives : calcul des indemnités de sortie.
Les routers et modules (ex. employee_exits) appellent ce module, pas engine directement.
"""

from __future__ import annotations

from typing import Any


def calculer_indemnites_sortie(
    employee_data: dict[str, Any],
    exit_data: dict[str, Any],
    supabase_client: Any = None,
) -> dict[str, Any]:
    """Calcule les indemnités de sortie. Délègue à engine.calcul_indemnites_sortie."""
    from app.modules.payroll.engine import calculer_indemnites_sortie as _impl

    return _impl(
        employee_data=employee_data,
        exit_data=exit_data,
        supabase_client=supabase_client,
    )
