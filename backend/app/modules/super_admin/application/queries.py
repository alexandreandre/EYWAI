"""
Queries du module super_admin (couche application).

Délègue à l'infrastructure (DB). Comportement identique.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.modules.super_admin.infrastructure import queries as infra_queries


def get_global_stats(super_admin_row: Dict[str, Any]) -> Dict[str, Any]:
    """Statistiques globales pour GET /dashboard/stats."""
    return infra_queries.get_global_stats(super_admin_row)


def get_support_badges() -> Dict[str, Any]:
    """Compteurs tickets pour badges navigation admin."""
    return infra_queries.get_support_badges()


def list_platform_audit_logs(
    company_id: Optional[str] = None,
    user_id: Optional[str] = None,
    action: Optional[str] = None,
    resource_type: Optional[str] = None,
    created_after: Optional[str] = None,
    created_before: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    """Journal d'audit cross-plateforme."""
    return infra_queries.list_platform_audit_logs(
        company_id=company_id,
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        created_after=created_after,
        created_before=created_before,
        limit=limit,
        offset=offset,
    )


def list_companies(
    skip: int = 0,
    limit: int = 50,
    search: Optional[str] = None,
    is_active: Optional[bool] = None,
) -> Dict[str, Any]:
    """Liste des entreprises avec filtres. Retourne { companies, total }."""
    return infra_queries.list_companies(
        skip=skip, limit=limit, search=search, is_active=is_active
    )


def get_company_details(company_id: str) -> Dict[str, Any]:
    """Détails d'une entreprise + stats (employees_count, users_count, users_by_role)."""
    return infra_queries.get_company_details(company_id)


def list_all_users(
    skip: int = 0,
    limit: int = 50,
    company_id: Optional[str] = None,
    role: Optional[str] = None,
    search: Optional[str] = None,
) -> Dict[str, Any]:
    """Liste tous les utilisateurs (avec emails via admin client). Retourne { users, total }."""
    return infra_queries.list_all_users(
        skip=skip, limit=limit, company_id=company_id, role=role, search=search
    )


def get_company_users(
    company_id: str,
    role: Optional[str] = None,
) -> Dict[str, Any]:
    """Utilisateurs ayant accès à une entreprise (user_company_accesses + profiles + emails)."""
    return infra_queries.get_company_users(company_id, role=role)


def list_super_admins() -> Dict[str, Any]:
    """Liste tous les super admins. Retourne { super_admins, total }."""
    return infra_queries.list_super_admins()


def get_system_health() -> Dict[str, Any]:
    """État de santé (RPC check_company_data_integrity)."""
    return infra_queries.get_system_health()


def get_employees_for_reduction_fillon() -> Dict[str, Any]:
    """Liste des employés pour le test réduction Fillon."""
    return infra_queries.get_employees_for_reduction_fillon()


def calculate_reduction_fillon(
    employee_id: str, month: int, year: int
) -> Dict[str, Any]:
    """Calcule la réduction Fillon pour un employé/mois. Structure détaillée identique au legacy."""
    return infra_queries.calculate_reduction_fillon(employee_id, month, year)
