"""
DTOs applicatifs du module company_groups.

Structure cible pour les retours des queries/commands (à brancher lors de la migration).
Alignés sur les réponses API actuelles (api/routers/company_groups.py).
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

__all__ = [
    "GroupWithCompaniesDto",
    "CompanyGroupDto",
    "GroupListSummaryDto",
    "ManageUserAccessResultDto",
    "BulkAddCompaniesResultDto",
    "AddRemoveCompanyResultDto",
    "RemoveUserFromGroupResultDto",
]


@dataclass
class GroupWithCompaniesDto:
    """Résultat get_my_groups / get_group_details."""

    id: str
    group_name: str
    siren: Optional[str]
    description: Optional[str]
    logo_url: Optional[str]
    is_active: bool
    created_at: Any
    updated_at: Any
    companies: List[Dict[str, Any]]


@dataclass
class CompanyGroupDto:
    """Résultat create_group / update_group."""

    id: str
    group_name: str
    siren: Optional[str]
    description: Optional[str]
    logo_url: Optional[str]
    is_active: bool
    created_at: Any
    updated_at: Any


@dataclass
class GroupListSummaryDto:
    """Un groupe dans la liste GET / (super admin) : id, group_name, description, created_at, company_count, total_employees."""

    id: str
    group_name: str
    description: Optional[str]
    created_at: Any
    company_count: int
    total_employees: int


@dataclass
class ManageUserAccessResultDto:
    """Résultat manage_user_access_in_group."""

    message: str
    user_id: str
    user_email: str
    added_count: int
    updated_count: int
    removed_count: int


@dataclass
class BulkAddCompaniesResultDto:
    """Résultat bulk_add_companies_to_group."""

    message: str
    success_count: int
    failed_count: int
    failed_companies: List[str]


@dataclass
class AddRemoveCompanyResultDto:
    """Résultat add_company_to_group / remove_company_from_group."""

    message: str
    group_id: Optional[str] = None
    company_id: Optional[str] = None


@dataclass
class RemoveUserFromGroupResultDto:
    """Résultat remove_user_from_group."""

    message: str
    removed_count: int
