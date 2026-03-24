# Schemas for super_admin. Migrés depuis api/routers/super_admin.py.
from app.modules.super_admin.schemas.requests import (
    CompanyCreate,
    CompanyCreateWithAdmin,
    CompanyUpdate,
    ReductionFillonRequest,
    UserCreate,
)
from app.modules.super_admin.schemas.responses import (
    CompaniesListResponse,
    CreateCompanyUserResponse,
    DashboardStatsResponse,
    DeleteCompanyPermanentResponse,
    DeleteCompanyUserResponse,
    SuperAdminsListResponse,
    SystemHealthResponse,
    UpdateCompanyUserResponse,
    UsersListResponse,
)

__all__ = [
    "CompanyCreate",
    "CompanyCreateWithAdmin",
    "CompanyUpdate",
    "UserCreate",
    "ReductionFillonRequest",
    "DashboardStatsResponse",
    "CompaniesListResponse",
    "UsersListResponse",
    "SuperAdminsListResponse",
    "SystemHealthResponse",
    "CreateCompanyUserResponse",
    "UpdateCompanyUserResponse",
    "DeleteCompanyUserResponse",
    "DeleteCompanyPermanentResponse",
]
