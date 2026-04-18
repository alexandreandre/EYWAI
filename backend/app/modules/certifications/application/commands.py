"""Commandes certifications / habilitations."""

from __future__ import annotations

from typing import Any, Dict

from dateutil.relativedelta import relativedelta

from app.core.database import supabase

from app.modules.certifications.application import queries
from app.modules.certifications.infrastructure import storage as cert_storage
from app.modules.certifications.infrastructure.repository import certification_repository
from app.modules.certifications.schemas.requests import (
    CertificationRefCreate,
    CertificationRefUpdate,
    EmployeeCertificationCreate,
    EmployeeCertificationUpdate,
)
from app.modules.certifications.schemas.responses import CertificationRef, EmployeeCertification


def _assert_employee_in_company(employee_id: str, company_id: str) -> None:
    r = (
        supabase.table("employees")
        .select("id")
        .eq("id", employee_id)
        .eq("company_id", company_id)
        .maybe_single()
        .execute()
    )
    if not r.data:
        raise ValueError("Employé introuvable dans cette entreprise.")


def create_certification_ref(company_id: str, data: CertificationRefCreate) -> CertificationRef:
    payload = data.model_dump(mode="json", exclude_unset=True)
    row = certification_repository.create_ref(company_id, payload)
    return queries.certification_ref_from_row(row) or CertificationRef.model_validate(row)


def update_certification_ref(
    ref_id: str, company_id: str, data: CertificationRefUpdate
) -> CertificationRef:
    patch = data.model_dump(mode="json", exclude_unset=True)
    row = certification_repository.update_ref(ref_id, company_id, patch)
    return queries.certification_ref_from_row(row) or CertificationRef.model_validate(row)


def archive_certification_ref(ref_id: str, company_id: str) -> None:
    certification_repository.archive_ref(ref_id, company_id)


def create_employee_certification(
    company_id: str, data: EmployeeCertificationCreate
) -> EmployeeCertification:
    _assert_employee_in_company(data.employee_id, company_id)
    ref = certification_repository.get_ref_by_id(data.certification_id, company_id)
    if not ref:
        raise LookupError("Référentiel d’habilitation introuvable.")
    if str(ref.get("status") or "") == "archived":
        raise ValueError("Ce référentiel est archivé.")

    obtained = data.obtained_date
    expiry = data.expiry_date
    vm = ref.get("validity_months")
    if expiry is None and vm is not None and int(vm) > 0:
        expiry = obtained + relativedelta(months=int(vm))

    payload: Dict[str, Any] = {
        "employee_id": data.employee_id,
        "certification_id": data.certification_id,
        "obtained_date": obtained.isoformat(),
        "expiry_date": expiry.isoformat() if expiry else None,
        "certifying_body": data.certifying_body,
        "certificate_number": data.certificate_number,
        "notes": data.notes,
        "is_archived": False,
    }
    row = certification_repository.create_employee_cert(company_id, payload)
    return queries.employee_certification_from_row(row)


def update_employee_certification(
    cert_id: str, company_id: str, data: EmployeeCertificationUpdate
) -> EmployeeCertification:
    patch = data.model_dump(mode="json", exclude_unset=True)
    if "certification_id" in patch and patch["certification_id"]:
        ref = certification_repository.get_ref_by_id(str(patch["certification_id"]), company_id)
        if not ref:
            raise LookupError("Référentiel d’habilitation introuvable.")
    row = certification_repository.update_employee_cert(cert_id, company_id, patch)
    return queries.employee_certification_from_row(row)


def archive_employee_certification(cert_id: str, company_id: str) -> None:
    certification_repository.archive_employee_cert(cert_id, company_id)


def upload_certificate_file(
    company_id: str, cert_id: str, file_bytes: bytes, filename: str
) -> EmployeeCertification:
    existing = certification_repository.get_employee_cert_by_id(cert_id, company_id)
    if not existing:
        raise LookupError("Habilitation non trouvée.")
    url = cert_storage.upload_certificate(company_id, cert_id, file_bytes, filename)
    row = certification_repository.update_employee_cert(
        cert_id, company_id, {"certificate_url": url}
    )
    return queries.employee_certification_from_row(row)
