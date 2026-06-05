"""Façade application pour le router training."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.modules.training.infrastructure.repository import training_repository


def list_pending_rh_approval(company_id: str) -> List[Dict[str, Any]]:
    return training_repository.list_pending_rh_approval(company_id)


def create_enrollment_request(
    employee_id: str,
    company_id: str,
    training_id: str,
    requested_by: str,
    preferred_date: Optional[str],
    motivation: Optional[str],
) -> Dict[str, Any]:
    return training_repository.create_enrollment_request(
        employee_id,
        company_id,
        training_id,
        requested_by,
        preferred_date,
        motivation,
    )


def get_enrollment_by_id(enrollment_id: str, company_id: str) -> Optional[Dict[str, Any]]:
    return training_repository.get_enrollment_by_id(enrollment_id, company_id)


def approve_enrollment_by_rh(
    enrollment_id: str, company_id: str, **kwargs: Any
) -> Dict[str, Any]:
    return training_repository.approve_by_rh(enrollment_id, company_id, **kwargs)


def submit_enrollment_evaluation(
    enrollment_id: str, company_id: str, **kwargs: Any
) -> Dict[str, Any]:
    return training_repository.submit_evaluation(enrollment_id, company_id, **kwargs)


def upload_enrollment_certificate(
    enrollment_id: str, company_id: str, **kwargs: Any
) -> str:
    return training_repository.upload_enrollment_certificate(
        enrollment_id, company_id, **kwargs
    )
