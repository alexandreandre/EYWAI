"""
Point d'entrée partagé pour résoudre employees.id à partir d'un compte utilisateur.

Délègue à la canonique employees.infrastructure.queries.resolve_employee_id_for_user_account.
Les modules métier importent depuis ce module plutôt que de réimplémenter Supabase.
"""

from __future__ import annotations

from app.modules.employees.infrastructure.queries import (
    resolve_employee_id_for_user_account,
)

__all__ = ["resolve_employee_id_for_user_account"]
