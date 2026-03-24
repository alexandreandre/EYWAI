# Schemas for collective_agreements (migrés depuis schemas/collective_agreement.py).
from .requests import (
    AssignAgreementBody,
    CollectiveAgreementCatalogCreate,
    CollectiveAgreementCatalogUpdate,
    CompanyCollectiveAgreementCreate,
    GetUploadUrlBody,
    QuestionRequest,
)
from .responses import (
    CollectiveAgreementCatalog,
    CollectiveAgreementCatalogBase,
    CompanyCollectiveAgreement,
    CompanyCollectiveAgreementWithDetails,
    QuestionResponse,
    UploadUrlResponse,
)

__all__ = [
    "AssignAgreementBody",
    "CollectiveAgreementCatalog",
    "CollectiveAgreementCatalogBase",
    "CollectiveAgreementCatalogCreate",
    "CollectiveAgreementCatalogUpdate",
    "CompanyCollectiveAgreement",
    "CompanyCollectiveAgreementCreate",
    "CompanyCollectiveAgreementWithDetails",
    "GetUploadUrlBody",
    "QuestionRequest",
    "QuestionResponse",
    "UploadUrlResponse",
]
