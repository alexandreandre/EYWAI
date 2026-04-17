"""Lecture certifications / habilitations."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List, Optional, cast as typing_cast

from app.modules.certifications.infrastructure.repository import (
    certification_repository,
    compute_computed_status,
)
from app.modules.certifications.schemas.responses import (
    CertificationRef,
    ComputedStatus,
    DashboardCounts,
    EmployeeCertification,
)


def _parse_date(val: Any) -> Optional[date]:
    if val is None:
        return None
    if isinstance(val, date) and not isinstance(val, datetime):
        return val
    if isinstance(val, datetime):
        return val.date()
    return date.fromisoformat(str(val)[:10])


def certification_ref_from_row(row: Optional[Dict[str, Any]]) -> Optional[CertificationRef]:
    if not row:
        return None
    return CertificationRef(
        id=str(row["id"]),
        company_id=str(row["company_id"]),
        name=row.get("name") or "",
        code=row.get("code"),
        category=str(row.get("category") or ""),
        validity_months=row.get("validity_months"),
        alert_days=int(row.get("alert_days") or 60),
        certifying_body=row.get("certifying_body"),
        description=row.get("description"),
        legal_link=row.get("legal_link"),
        status=str(row.get("status") or "active"),
        created_at=row.get("created_at"),
    )


def employee_certification_from_row(row: Dict[str, Any]) -> EmployeeCertification:
    r = dict(row)
    ref_row = r.pop("_certification_ref_row", None)
    employee_name = r.pop("_employee_name", None)

    ref_model = certification_ref_from_row(ref_row)
    exp = _parse_date(r.get("expiry_date"))
    alert = int((ref_row or {}).get("alert_days") or 60)
    status = typing_cast(
        ComputedStatus,
        compute_computed_status(exp, alert),
    )
    return EmployeeCertification(
        id=str(r["id"]),
        company_id=str(r["company_id"]),
        employee_id=str(r["employee_id"]),
        certification_id=str(r["certification_id"]),
        obtained_date=_parse_date(r.get("obtained_date")) or date.today(),
        expiry_date=exp,
        certifying_body=r.get("certifying_body"),
        certificate_number=r.get("certificate_number"),
        certificate_url=r.get("certificate_url"),
        notes=r.get("notes"),
        is_archived=bool(r.get("is_archived", False)),
        created_at=r.get("created_at"),
        computed_status=status,  # type: ignore[arg-type]
        certification_ref=ref_model,
        employee_name=employee_name,
    )


def get_certification_refs(company_id: str) -> List[CertificationRef]:
    rows = certification_repository.get_all_refs(company_id)
    out: List[CertificationRef] = []
    for x in rows:
        m = certification_ref_from_row(dict(x))
        if m is not None:
            out.append(m)
    return out


def get_certification_ref(ref_id: str, company_id: str) -> Optional[CertificationRef]:
    row = certification_repository.get_ref_by_id(ref_id, company_id)
    return certification_ref_from_row(row)


def get_employee_certifications(
    company_id: str,
    employee_id: Optional[str] = None,
    include_archived: bool = False,
) -> List[EmployeeCertification]:
    rows = certification_repository.get_all_employee_certs(
        company_id, employee_id=employee_id, include_archived=include_archived
    )
    out: List[EmployeeCertification] = []
    for raw in rows:
        out.append(employee_certification_from_row(dict(raw)))
    return out


def get_employee_certification(
    cert_id: str, company_id: str
) -> Optional[EmployeeCertification]:
    row = certification_repository.get_employee_cert_by_id(cert_id, company_id)
    if not row:
        return None
    return employee_certification_from_row(dict(row))


def get_dashboard_counts(company_id: str) -> DashboardCounts:
    expiring = certification_repository.get_expiring_count(company_id)
    expired = certification_repository.get_expired_count(company_id)
    return DashboardCounts(expiring=expiring, expired=expired)
