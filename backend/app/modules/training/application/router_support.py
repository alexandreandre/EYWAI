"""Façade application pour le router training."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.modules.training.infrastructure.repository import training_repository


def list_pending_manager_approval(
    company_id: str, manager_employee_id: Optional[str]
) -> List[Dict[str, Any]]:
    return training_repository.list_pending_manager_approval(
        company_id, manager_employee_id
    )


def list_pending_rh_approval(company_id: str) -> List[Dict[str, Any]]:
    return training_repository.list_pending_rh_approval(company_id)


def create_enrollment_request(
    company_id: str, data: Dict[str, Any], created_by_user_id: str
) -> Dict[str, Any]:
    return training_repository.create_enrollment_request(
        company_id, data, created_by_user_id
    )


def get_enrollment_by_id(enrollment_id: str, company_id: str) -> Optional[Dict[str, Any]]:
    return training_repository.get_enrollment_by_id(enrollment_id, company_id)


def approve_enrollment_by_manager(
    enrollment_id: str, company_id: str, manager_employee_id: str, **kwargs: Any
) -> Dict[str, Any]:
    return training_repository.approve_by_manager(
        enrollment_id, company_id, manager_employee_id, **kwargs
    )


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
