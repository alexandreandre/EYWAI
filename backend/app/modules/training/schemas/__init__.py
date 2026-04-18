"""Schémas training."""

from app.modules.training.schemas.requests import (
    TrainingCatalogCreate,
    TrainingCatalogUpdate,
    TrainingEnrollmentCreate,
    TrainingEnrollmentUpdate,
)
from app.modules.training.schemas.responses import (
    TotalConsumedResponse,
    TrainingCatalog,
    TrainingEnrollment,
)

__all__ = [
    "TotalConsumedResponse",
    "TrainingCatalog",
    "TrainingCatalogCreate",
    "TrainingCatalogUpdate",
    "TrainingEnrollment",
    "TrainingEnrollmentCreate",
    "TrainingEnrollmentUpdate",
]
