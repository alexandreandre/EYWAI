"""
PDF identifiants de connexion : recherche storage, génération et URL signée.
"""

from __future__ import annotations

import secrets
import string
from typing import Any, Dict, Optional

from app.core.logging import get_logger
from app.modules.employees.domain.rules import default_company_data_fallback
from app.modules.employees.infrastructure.providers import (
    generate_credentials_pdf,
    get_auth_provider,
    get_company_reader,
    get_storage_provider,
)
from app.modules.employees.infrastructure.queries import get_employee_company_id
from app.modules.employees.infrastructure.repository import EmployeeRepository

logger = get_logger("modules.employees.application.credentials_pdf")

CREDENTIALS_BUCKET = "creation_compte"
CREDENTIALS_FILENAME = "creation_compte.pdf"

_employee_repository = EmployeeRepository()


def _generate_temp_password() -> str:
    alphabet = string.ascii_letters + string.digits + "!@#$%*?"
    return "".join(secrets.choice(alphabet) for _ in range(12))


def _credentials_search_prefixes(
    company_id: str,
    employee_id: str,
    user_id: Optional[str],
    folder_name: Optional[str],
) -> list[str]:
    """Préfixes storage à parcourir (id employé, user auth, dossier legacy)."""
    prefixes: list[str] = []

    def add(prefix: str) -> None:
        normalized = prefix.strip("/")
        if normalized and normalized not in prefixes:
            prefixes.append(normalized)

    if company_id and employee_id:
        add(f"{company_id}/{employee_id}")
    if company_id and user_id:
        add(f"{company_id}/{user_id}")
    if company_id and folder_name:
        add(f"{company_id}/{folder_name}")
    if folder_name:
        add(folder_name)
    return prefixes


def find_credentials_pdf_path(
    storage: Any,
    company_id: str,
    employee_id: str,
    user_id: Optional[str],
    folder_name: Optional[str] = None,
) -> Optional[str]:
    """Retourne le chemin storage du PDF s'il existe."""
    for prefix in _credentials_search_prefixes(
        company_id, employee_id, user_id, folder_name
    ):
        inner = storage.list_files(CREDENTIALS_BUCKET, prefix)
        if any(f.get("name") == CREDENTIALS_FILENAME for f in inner):
            return f"{prefix}/{CREDENTIALS_FILENAME}"
    return None


_PASSWORD_UNAVAILABLE = (
    "— contactez les RH ou utilisez « Mot de passe oublié » sur la page de connexion"
)


def _resolve_temp_password(auth: Any, user_id: str) -> str:
    password = _generate_temp_password()
    try:
        auth.update_user_password(user_id, password)
        return password
    except Exception as auth_err:
        logger.warning(
            "Mot de passe temporaire non défini pour %s (%s) — PDF sans mot de passe",
            user_id,
            auth_err,
        )
        return _PASSWORD_UNAVAILABLE


def ensure_credentials_pdf(employee_id: str) -> Optional[str]:
    """
    Garantit la présence du PDF identifiants en storage.
    Retourne le chemin storage ou None si le collaborateur n'a pas de compte auth.
    """
    company_id = get_employee_company_id(employee_id)
    if not company_id:
        return None

    employee = _employee_repository.get_by_id_only(employee_id)
    if not employee:
        return None

    user_id = str(employee.get("user_id") or "").strip() or None
    folder_name = str(employee.get("employee_folder_name") or "").strip() or None

    if not user_id and employee.get("email"):
        try:
            from app.modules.employees.application.account_provisioning import (
                provision_collaborator_account,
            )

            provision_collaborator_account(employee_id, company_id)
            employee = _employee_repository.get_by_id_only(employee_id) or employee
            user_id = str(employee.get("user_id") or "").strip() or None
        except Exception as prov_err:
            logger.warning(
                "Provisionnement compte ignoré pour %s: %s",
                employee_id,
                prov_err,
            )

    storage = get_storage_provider()
    existing = find_credentials_pdf_path(
        storage,
        company_id,
        employee_id,
        user_id,
        folder_name,
    )
    if existing:
        return existing

    first_name = str(employee.get("first_name") or "").strip()
    last_name = str(employee.get("last_name") or "").strip()
    username = str(employee.get("username") or "").strip()
    if not username and first_name and last_name:
        from app.shared.utils import remove_accents

        username = (
            f"{remove_accents(first_name).lower().replace(' ', '_')}."
            f"{remove_accents(last_name).lower().replace(' ', '_')}"
        )
    if not username:
        logger.warning("PDF identifiants impossible : username manquant pour %s", employee_id)
        return None

    password = _resolve_temp_password(get_auth_provider(), user_id) if user_id else _PASSWORD_UNAVAILABLE

    company_reader = get_company_reader()
    try:
        company_data = company_reader.get_company_data(company_id)
    except Exception as company_err:
        logger.warning(
            "Lecture entreprise ignorée pour PDF identifiants (%s): %s",
            company_id,
            company_err,
        )
        company_data = None
    company_data = company_data or default_company_data_fallback()

    try:
        pdf_content = generate_credentials_pdf(
            first_name=first_name,
            last_name=last_name,
            username=username,
            password=password,
            logo_path="",
            company_data=company_data,
        )
        canonical = f"{company_id}/{employee_id}/{CREDENTIALS_FILENAME}"
        storage.upload(CREDENTIALS_BUCKET, canonical, pdf_content, "application/pdf")
        logger.info("PDF identifiants généré pour l'employé %s", employee_id)
        return canonical
    except Exception as pdf_err:
        logger.warning(
            "Échec génération PDF identifiants pour %s: %s",
            employee_id,
            pdf_err,
        )
        return None


def get_credentials_pdf_url(employee_id: str) -> Optional[str]:
    """URL signée du PDF identifiants (génère le fichier s'il est absent)."""
    path = ensure_credentials_pdf(employee_id)
    if not path:
        return None
    storage = get_storage_provider()
    return storage.create_signed_url(
        CREDENTIALS_BUCKET,
        path,
        expiry_seconds=3600,
        download=True,
    )
