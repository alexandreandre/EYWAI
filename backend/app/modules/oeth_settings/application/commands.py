"""Commandes d'écriture OETH."""

from __future__ import annotations

from typing import Any, Dict

from app.modules.oeth_settings.application import queries
from app.modules.oeth_settings.domain.constants import BOETH_CODES, DEDUCTION_TYPES, EXTERNAL_TYPES
from app.modules.oeth_settings.infrastructure.boeth_repository import oeth_annual_repository
from app.modules.oeth_settings.infrastructure.boeth_repository import boeth_profiles_repository
from app.modules.oeth_settings.infrastructure.repository import oeth_settings_repository
from app.modules.oeth_settings.schemas.requests import (
    AnnualReviewStatusUpdate,
    BoethExternesUpdate,
    DeductionsUpdate,
    EcapPositionsUpdate,
    EmployeeBoethUpdate,
    OethSettingsUpdate,
    UrssafOverrideUpdate,
)
from app.modules.oeth_settings.schemas.responses import (
    EmployeeBoethProfile,
    OethAnnualReview,
    OethSettings,
)

_DB_WRITABLE_KEYS = frozenset(
    {
        "oeth_assujetti_override",
        "date_franchissement_seuil_20",
        "accord_agree_code",
        "accord_agree_valid_from",
        "accord_agree_valid_to",
        "declaring_establishment_siret",
        "departement",
        "taux_obligation",
    }
)


def save_oeth_settings(company_id: str, data: OethSettingsUpdate) -> OethSettings:
    current = queries.get_oeth_settings(company_id)
    merged: Dict[str, Any] = current.model_dump(mode="json")
    patch = data.model_dump(exclude_unset=True)
    merged.update(patch)
    payload = {k: merged[k] for k in _DB_WRITABLE_KEYS if k in merged}
    row = oeth_settings_repository.upsert(company_id, payload)
    return queries.get_oeth_settings(company_id)


def save_employee_boeth(
    company_id: str, employee_id: str, data: EmployeeBoethUpdate
) -> EmployeeBoethProfile:
    if data.boeth_code not in BOETH_CODES:
        raise ValueError(f"Code BOETH invalide : {data.boeth_code}")
    payload = data.model_dump(mode="json")
    row = boeth_profiles_repository.upsert_profile(company_id, employee_id, payload)
    prof = queries.get_employee_boeth(employee_id, company_id)
    if not prof:
        raise RuntimeError("Profil BOETH introuvable après enregistrement")
    return prof


def remove_employee_boeth(company_id: str, employee_id: str) -> None:
    boeth_profiles_repository.deactivate(employee_id, company_id)


def save_boeth_externes(
    company_id: str, year: int, data: BoethExternesUpdate
) -> OethAnnualReview:
    rows = []
    for item in data.items:
        if item.external_type not in EXTERNAL_TYPES:
            raise ValueError(f"Type BOETH externe invalide : {item.external_type}")
        rows.append(item.model_dump(mode="json"))
    oeth_annual_repository.replace_externes(company_id, year, rows)
    return queries.compute_annual_review(company_id, year)


def save_deductions(
    company_id: str, year: int, data: DeductionsUpdate
) -> OethAnnualReview:
    rows = []
    for item in data.items:
        if item.deduction_type not in DEDUCTION_TYPES:
            raise ValueError(f"Type déduction invalide : {item.deduction_type}")
        rows.append(item.model_dump(mode="json"))
    oeth_annual_repository.replace_deductions(company_id, year, rows)
    return queries.compute_annual_review(company_id, year)


def save_ecap_positions(
    company_id: str, year: int, data: EcapPositionsUpdate
) -> OethAnnualReview:
    rows = [item.model_dump(mode="json") for item in data.items]
    oeth_annual_repository.replace_ecap(company_id, year, rows)
    return queries.compute_annual_review(company_id, year)


def save_urssaf_override(
    company_id: str, year: int, data: UrssafOverrideUpdate
) -> OethAnnualReview:
    patch = data.model_dump(exclude_unset=True, mode="json")
    existing = oeth_annual_repository.get_review(company_id, year) or {}
    merged = {**existing, **patch}
    oeth_annual_repository.upsert_review(company_id, year, merged)
    return queries.compute_annual_review(company_id, year)


def update_annual_review_status(
    company_id: str, year: int, data: AnnualReviewStatusUpdate
) -> OethAnnualReview:
    existing = oeth_annual_repository.get_review(company_id, year) or {}
    existing["status"] = data.status
    if data.status == "declared":
        existing["declared_in_dsn_period"] = f"{year + 1}-04"
    oeth_annual_repository.upsert_review(company_id, year, existing)
    return queries.compute_annual_review(company_id, year)
