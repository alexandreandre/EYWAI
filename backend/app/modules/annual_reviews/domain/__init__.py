"""Domaine annual_reviews : entités, règles, interfaces."""
from .entities import AnnualReview
from .enums import AnnualReviewStatusEnum
from .interfaces import IAnnualReviewPdfGenerator, IAnnualReviewRepository
from .rules import (
    DEFAULT_STATUS_ON_CREATE,
    STATUS_REQUIRED_FOR_MARK_COMPLETED,
    STATUS_REQUIRED_FOR_PDF,
    build_employee_update_data,
    build_rh_update_data,
    employee_can_update_acceptance,
    employee_can_update_preparation_notes,
    rh_can_edit_full_fiche,
    validate_can_mark_completed,
    validate_pdf_allowed,
)

__all__ = [
    "AnnualReview",
    "AnnualReviewStatusEnum",
    "DEFAULT_STATUS_ON_CREATE",
    "IAnnualReviewPdfGenerator",
    "IAnnualReviewRepository",
    "STATUS_REQUIRED_FOR_MARK_COMPLETED",
    "STATUS_REQUIRED_FOR_PDF",
    "build_employee_update_data",
    "build_rh_update_data",
    "employee_can_update_acceptance",
    "employee_can_update_preparation_notes",
    "rh_can_edit_full_fiche",
    "validate_can_mark_completed",
    "validate_pdf_allowed",
]
