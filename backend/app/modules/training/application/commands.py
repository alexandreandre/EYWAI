"""Commandes catalogue formations."""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from app.modules.certifications.infrastructure.repository import certification_repository
from app.modules.training.application import queries
from app.modules.training.infrastructure.repository import training_repository
from app.modules.training.schemas.requests import (
    TrainingCatalogCreate,
    TrainingCatalogUpdate,
    TrainingEnrollmentCreate,
    TrainingEnrollmentUpdate,
)
from app.modules.training.schemas.responses import TrainingCatalog, TrainingEnrollment


def _validate_certification(company_id: str, certification_id: Optional[str]) -> None:
    if not certification_id:
        return
    ref = certification_repository.get_ref_by_id(certification_id, company_id)
    if not ref:
        raise ValueError("Référentiel d’habilitation introuvable.")


def _suggest_for_completed(
    company_id: str, training_id: str, new_status: str
) -> Tuple[bool, Optional[str]]:
    if new_status != "completed":
        return False, None
    tr = training_repository.get_training_by_id(training_id, company_id)
    if not tr:
        return False, None
    cid = tr.get("certification_id")
    if cid:
        return True, str(cid)
    return False, None


def create_training(company_id: str, data: TrainingCatalogCreate) -> TrainingCatalog:
    _validate_certification(company_id, data.certification_id)
    payload = data.model_dump(mode="json", exclude_unset=True)
    row = training_repository.create_training(company_id, payload)
    return queries.training_catalog_from_row(row)


def update_training(
    training_id: str, company_id: str, data: TrainingCatalogUpdate
) -> TrainingCatalog:
    patch = data.model_dump(exclude_unset=True, mode="json")
    if "certification_id" in patch:
        _validate_certification(company_id, patch.get("certification_id"))
    row = training_repository.update_training(training_id, company_id, patch)
    return queries.training_catalog_from_row(row)


def archive_training(training_id: str, company_id: str) -> None:
    training_repository.archive_training(training_id, company_id)


def create_enrollment(
    company_id: str, data: TrainingEnrollmentCreate
) -> TrainingEnrollment:
    if training_repository.has_active_enrollment_duplicate(
        company_id, data.training_id, data.employee_id
    ):
        raise ValueError(
            "Une inscription active existe déjà pour ce collaborateur sur cette formation."
        )
    tr = training_repository.get_training_by_id(data.training_id, company_id)
    if not tr:
        raise LookupError("Formation non trouvée.")
    if str(tr.get("status") or "") == "archived":
        raise ValueError("Impossible d’inscrire sur une formation archivée.")

    payload = data.model_dump(mode="json", exclude_unset=True)
    row = training_repository.create_enrollment(company_id, payload)
    suggest, cert_id = _suggest_for_completed(
        company_id, data.training_id, str(data.status)
    )
    return queries.training_enrollment_from_row(
        dict(row), suggest=suggest, suggested_certification_id=cert_id
    )


def update_enrollment(
    enrollment_id: str, company_id: str, data: TrainingEnrollmentUpdate
) -> TrainingEnrollment:
    existing = training_repository.get_enrollment_by_id(enrollment_id, company_id)
    if not existing:
        raise LookupError("Inscription non trouvée.")
    old_status = str(existing.get("status") or "")
    patch: Dict[str, Any] = data.model_dump(exclude_unset=True, mode="json")
    new_status = str(patch.get("status", old_status))
    row = training_repository.update_enrollment(enrollment_id, company_id, patch)
    suggest = False
    cert_id: Optional[str] = None
    if new_status == "completed" and old_status != "completed":
        suggest, cert_id = _suggest_for_completed(
            company_id, str(row["training_id"]), new_status
        )
    return queries.training_enrollment_from_row(
        dict(row), suggest=suggest, suggested_certification_id=cert_id
    )


def cancel_enrollment(enrollment_id: str, company_id: str) -> None:
    training_repository.cancel_enrollment(enrollment_id, company_id)


def create_training_from_cc_recommendation(
    company_id: str, recommendation_id: str
) -> TrainingCatalog:
    from app.modules.collective_agreements.training_reco.service import (
        get_cc_training_recommendations_service,
    )
    from app.modules.training.infrastructure.cc_resolution import company_has_idcc

    svc = get_cc_training_recommendations_service()
    reco = svc.get_recommendation(recommendation_id)
    if not reco.get("is_active"):
        raise ValueError("Cette proposition n'est pas active.")
    reco_idcc = str(reco.get("idcc") or "")
    if not company_has_idcc(company_id, reco_idcc):
        raise PermissionError(
            "Cette proposition ne correspond pas à la convention collective de votre entreprise."
        )

    existing = training_repository.get_training_by_source_cc_recommendation(
        company_id, recommendation_id
    )
    if existing:
        return queries.training_catalog_from_row(existing)

    categories = ["Convention collective"]
    payload = {
        "title": str(reco.get("title") or "").strip(),
        "training_type": "presentiel",
        "pedagogical_objective": reco.get("pedagogical_objective"),
        "categories": categories,
        "source_cc_recommendation_id": recommendation_id,
    }
    if not payload["title"]:
        raise ValueError("Titre de formation invalide.")
    row = training_repository.create_training(company_id, payload)
    return queries.training_catalog_from_row(row)
