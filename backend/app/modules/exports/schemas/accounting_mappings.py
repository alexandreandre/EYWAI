from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class AccountingMappingOut(BaseModel):
    id: str
    company_id: Optional[str] = None
    rubrique_code: str
    rubrique_libelle: str
    compte_comptable: str
    journal: str = "OD"
    sens: Literal["debit", "credit"] = "debit"
    type_rubrique: str = "salaire"
    analytique: Optional[str] = None
    is_active: bool = True
    is_global_default: bool = False


class AccountingMappingUpsert(BaseModel):
    rubrique_code: str = Field(..., min_length=1)
    rubrique_libelle: str = Field(..., min_length=1)
    compte_comptable: str = Field(..., min_length=3)
    journal: str = "OD"
    sens: Literal["debit", "credit"] = "debit"
    type_rubrique: str = "salaire"
    analytique: Optional[str] = None
    is_active: bool = True


class AccountingMappingsListResponse(BaseModel):
    mappings: List[AccountingMappingOut]
    company_overrides_count: int
