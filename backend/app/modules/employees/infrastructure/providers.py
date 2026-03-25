"""
Providers (services externes) du module employees.

- Implémentations des ports du domain (storage, auth, company, résidence).
- PDF, RIB, promotions, résidence, texte : app.shared.infrastructure et app.shared.utils.
Comportement strictement identique au router legacy.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.core.database import supabase
from app.modules.employees.domain.interfaces import (
    IAuthProvider,
    ICompanyReader,
    IResidencePermitStatusCalculator,
    IStorageProvider,
)
from app.modules.employees.schemas.responses import EmployeeRhAccess, PromotionListItem


# ----- Implémentations des ports (Supabase) -----


class SupabaseStorageProvider(IStorageProvider):
    """Implémentation Supabase de IStorageProvider."""

    def list_files(self, bucket: str, path: str) -> List[Dict[str, Any]]:
        result = supabase.storage.from_(bucket).list(path)
        return list(result) if isinstance(result, list) else []

    def create_signed_url(
        self,
        bucket: str,
        path: str,
        expiry_seconds: int = 3600,
        download: bool = True,
    ) -> Optional[str]:
        response = supabase.storage.from_(bucket).create_signed_url(
            path, expiry_seconds, options={"download": download}
        )
        data = getattr(response, "data", response)
        if isinstance(data, dict):
            return data.get("signedURL")
        return None

    def upload(
        self,
        bucket: str,
        path: str,
        content: bytes,
        content_type: str,
    ) -> None:
        supabase.storage.from_(bucket).upload(
            path=path,
            file=content,
            file_options={"x-upsert": "true", "content-type": content_type},
        )


class SupabaseAuthProvider(IAuthProvider):
    """Implémentation Supabase Auth de IAuthProvider."""

    def create_user(self, email: str, password: str) -> str:
        response = supabase.auth.admin.create_user(
            {
                "email": email,
                "password": password,
                "email_confirm": True,
            }
        )
        if response.user is None:
            raise RuntimeError("Auth create_user returned no user")
        return str(response.user.id)

    def delete_user(self, user_id: str) -> None:
        supabase.auth.admin.delete_user(user_id)


class SupabaseCompanyReader(ICompanyReader):
    """Implémentation Supabase de ICompanyReader."""

    def get_company_data(self, company_id: str) -> Optional[Dict[str, Any]]:
        response = (
            supabase.table("companies")
            .select("company_name, siret, email")
            .eq("id", company_id)
            .single()
            .execute()
        )
        if not response.data:
            return None
        return dict(response.data)


class SupabaseResidencePermitStatusCalculator(IResidencePermitStatusCalculator):
    """Implémentation via app.shared.infrastructure.residence_permit."""

    def calculate(
        self,
        is_subject_to_residence_permit: bool,
        residence_permit_expiry_date: Optional[Any],
        employment_status: str,
        reference_date: Optional[Any] = None,
    ) -> Dict[str, Any]:
        from app.shared.infrastructure.residence_permit import (
            calculate_residence_permit_status,
        )

        return calculate_residence_permit_status(
            is_subject_to_residence_permit=is_subject_to_residence_permit,
            residence_permit_expiry_date=residence_permit_expiry_date,
            employment_status=employment_status,
            reference_date=reference_date,
        )


# Instances par défaut (utilisées par l'application et les queries)
_storage = SupabaseStorageProvider()
_auth = SupabaseAuthProvider()
_company_reader = SupabaseCompanyReader()
_residence_calculator = SupabaseResidencePermitStatusCalculator()


def get_storage_provider() -> IStorageProvider:
    return _storage


def get_auth_provider() -> IAuthProvider:
    return _auth


def get_company_reader() -> ICompanyReader:
    return _company_reader


def get_residence_permit_calculator() -> IResidencePermitStatusCalculator:
    return _residence_calculator


# ----- PDF, texte, résidence, RIB, promotions (app.shared) -----


def generate_credentials_pdf(
    first_name: str,
    last_name: str,
    username: str,
    password: str,
    logo_path: str,
) -> bytes:
    """Via app.shared.infrastructure.pdf."""
    from app.shared.infrastructure.pdf import generate_credentials_pdf as _impl

    return _impl(first_name, last_name, username, password, logo_path)


def generate_contract_pdf(
    employee_data: Dict[str, Any],
    company_data: Dict[str, Any],
    logo_path: str,
) -> bytes:
    """Via app.shared.infrastructure.pdf."""
    from app.shared.infrastructure.pdf import generate_contract_pdf as _impl

    return _impl(employee_data, company_data, logo_path)


def remove_accents(text: str) -> str:
    """Via app.shared.utils."""
    from app.shared.utils import remove_accents as _impl

    return _impl(text)


def calculate_residence_permit_status(
    is_subject_to_residence_permit: bool,
    residence_permit_expiry_date: Optional[Any],
    employment_status: str,
    reference_date: Optional[Any] = None,
) -> Dict[str, Any]:
    """Délègue au calculator (app.shared.infrastructure.residence_permit)."""
    return _residence_calculator.calculate(
        is_subject_to_residence_permit=is_subject_to_residence_permit,
        residence_permit_expiry_date=residence_permit_expiry_date,
        employment_status=employment_status,
        reference_date=reference_date,
    )


def normalize_iban(iban: str) -> str:
    """Via app.shared.infrastructure.rib_alert."""
    from app.shared.infrastructure.rib_alert import normalize_iban as _impl

    return _impl(iban)


def on_rib_updated(
    company_id: str,
    employee_id: str,
    old_iban: str,
    new_iban: str,
    employee_name: str,
) -> None:
    """Via app.shared.infrastructure.rib_alert."""
    from app.shared.infrastructure.rib_alert import on_rib_updated as _impl

    return _impl(company_id, employee_id, old_iban, new_iban, employee_name)


def on_rib_submitted(
    company_id: str,
    employee_id: str,
    new_iban: str,
    employee_name: str,
) -> List[Dict[str, Any]]:
    """Via app.shared.infrastructure.rib_alert."""
    from app.shared.infrastructure.rib_alert import on_rib_submitted as _impl

    return _impl(company_id, employee_id, new_iban, employee_name)


def get_promotions(
    company_id: str,
    employee_id: Optional[str] = None,
    **kwargs: Any,
) -> List[PromotionListItem]:
    """Via app.shared.infrastructure.promotion ; conversion en schémas du module."""
    from app.shared.infrastructure.promotion import get_promotions as _get_raw

    raw = _get_raw(company_id=company_id, employee_id=employee_id, **kwargs)
    return [PromotionListItem(**item) for item in raw]


def get_employee_rh_access(employee_id: str, company_id: str) -> EmployeeRhAccess:
    """Via app.shared.infrastructure.promotion ; conversion en schéma du module."""
    from app.shared.infrastructure.promotion import get_employee_rh_access as _get_raw

    raw = _get_raw(employee_id=employee_id, company_id=company_id)
    return EmployeeRhAccess(**raw)
