# Schemas for uploads (contrat API identique à api/routers/uploads.py).
from app.modules.uploads.schemas.requests import (
    EntityTypeLiteral,
    LogoScaleUpdate,
    UploadLogoForm,
)
from app.modules.uploads.schemas.responses import (
    BdesUploadResponse,
    DeleteLogoResponse,
    LogoScaleResponse,
    UploadLogoResponse,
)

__all__ = [
    "EntityTypeLiteral",
    "UploadLogoForm",
    "LogoScaleUpdate",
    "UploadLogoResponse",
    "BdesUploadResponse",
    "DeleteLogoResponse",
    "LogoScaleResponse",
]
