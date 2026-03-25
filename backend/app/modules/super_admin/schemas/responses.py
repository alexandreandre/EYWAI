"""
Schémas réponse API du module super_admin.

Structures alignées sur les réponses exactes du router legacy
(api/routers/super_admin.py). Conservent le comportement exact pour
validation / documentation / future utilisation en response_model.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ----- GET /dashboard/stats -----


class DashboardStatsCompanies(BaseModel):
    total: int
    active: int
    inactive: int


class DashboardStatsUsers(BaseModel):
    total: int
    by_role: Dict[str, int] = Field(default_factory=dict)


class DashboardStatsEmployees(BaseModel):
    total: int


class DashboardStatsSuperAdmins(BaseModel):
    total: int


class DashboardTopCompany(BaseModel):
    id: str
    name: str
    employees_count: int


class DashboardStatsResponse(BaseModel):
    """Réponse exacte GET /dashboard/stats."""

    companies: DashboardStatsCompanies
    users: DashboardStatsUsers
    employees: DashboardStatsEmployees
    super_admins: DashboardStatsSuperAdmins
    top_companies: List[DashboardTopCompany] = Field(default_factory=list)


# ----- GET /companies -----


class CompaniesListResponse(BaseModel):
    """Réponse exacte GET /companies."""

    companies: List[Dict[str, Any]] = Field(default_factory=list)
    total: int = 0


# ----- GET /companies/{company_id}, POST /companies, PATCH /companies/{company_id} -----


class CompanyStats(BaseModel):
    employees_count: int
    users_count: int
    users_by_role: Dict[str, int] = Field(default_factory=dict)


# Réponse GET /companies/{company_id} = company_data (dict) avec clé "stats" (CompanyStats)
# Réponse POST /companies = { success: True, company: dict, admin?: dict }
# Réponse PATCH /companies/{company_id} = { success: True, company: dict }


class CompanyActionResponse(BaseModel):
    """Réponse POST /companies, PATCH /companies/{company_id}, DELETE /companies/{company_id}."""

    success: bool = True
    company: Optional[Dict[str, Any]] = None
    message: Optional[str] = None
    admin: Optional[Dict[str, Any]] = None


# ----- DELETE /companies/{company_id}/permanent -----


class DeletedCompanyInfo(BaseModel):
    id: str
    name: str


class DeleteCompanyPermanentResponse(BaseModel):
    """Réponse exacte DELETE /companies/{company_id}/permanent."""

    success: bool = True
    message: str = ""
    deleted_company: DeletedCompanyInfo
    deletion_statistics: Dict[str, int] = Field(default_factory=dict)
    total_records_deleted: int = 0


# ----- GET /users, GET /companies/{company_id}/users -----


class UsersListResponse(BaseModel):
    """Réponse exacte GET /users et GET /companies/{company_id}/users."""

    users: List[Dict[str, Any]] = Field(default_factory=list)
    total: int = 0


# ----- POST /companies/{company_id}/users, PATCH/DELETE company user -----


class CreateCompanyUserResponse(BaseModel):
    success: bool = True
    user: Dict[str, Any] = Field(default_factory=dict)


class UpdateCompanyUserResponse(BaseModel):
    success: bool = True
    message: str = "Utilisateur mis à jour avec succès"


class DeleteCompanyUserResponse(BaseModel):
    success: bool = True
    message: str = ""


# ----- GET /system/health -----


class SystemHealthResponse(BaseModel):
    """Réponse exacte GET /system/health."""

    status: str = "healthy"
    checks: Dict[str, str] = Field(default_factory=dict)
    integrity_issues: List[Any] = Field(default_factory=list)
    error: Optional[str] = None


# ----- GET /super-admins -----


class SuperAdminsListResponse(BaseModel):
    """Réponse exacte GET /super-admins."""

    super_admins: List[Dict[str, Any]] = Field(default_factory=list)
    total: int = 0


# ----- POST /reduction-fillon/calculate -----
# Structure complexe (result, employee_data, company_data, schedule_data, monthly_inputs_data,
# composition_brut, expenses_data, absences_data, cumuls_precedents, calcul_detail, input_data).
# Conservée en dict pour compatibilité ; pas de modèle Pydantic strict pour l’instant.


# ----- GET /reduction-fillon/employees -----


class ReductionFillonEmployeeItem(BaseModel):
    id: str
    name: str
    company_name: str
    salaire_base: float
    duree_hebdomadaire: int
    statut: str
    job_title: str


class ReductionFillonEmployeesResponse(BaseModel):
    """Réponse exacte GET /reduction-fillon/employees."""

    employees: List[Dict[str, Any]] = Field(default_factory=list)
    total: int = 0
