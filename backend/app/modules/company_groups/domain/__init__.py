# Domain layer for company_groups. Aucune dépendance FastAPI ni DB.
from app.modules.company_groups.domain.entities import CompanyGroup, CompanyInGroupRef
from app.modules.company_groups.domain.interfaces import (
    ICompanyGroupRepository,
    IGroupStatsProvider,
    IUserLookupProvider,
)
from app.modules.company_groups.domain import rules

__all__ = [
    "CompanyGroup",
    "CompanyInGroupRef",
    "ICompanyGroupRepository",
    "IGroupStatsProvider",
    "IUserLookupProvider",
    "rules",
]
