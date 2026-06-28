"""
Provisionnement compte collaborateur (auth + profil + accès + PDF identifiants).

Utilisé lorsque le salarié est créé hors ``create_employee`` (ex. recrutement).
"""

from __future__ import annotations

import secrets
import string
from typing import Any, Dict, Optional

from app.core.logging import get_logger
from app.modules.employees.application.credentials_pdf import (
    CREDENTIALS_BUCKET,
    CREDENTIALS_FILENAME,
    find_credentials_pdf_path,
)
from app.modules.employees.domain.rules import (
    build_dsn_import_auth_email,
    default_company_data_fallback,
)
from app.modules.employees.infrastructure.queries import allocate_collaborator_username
from app.modules.employees.infrastructure.providers import (
    generate_credentials_pdf,
    get_auth_provider,
    get_company_reader,
    get_storage_provider,
)
from app.modules.employees.infrastructure.repository import (
    EmployeeRepository,
    ProfileRepository,
)

logger = get_logger("modules.employees.application.account_provisioning")

_employee_repository = EmployeeRepository()
_profile_repository = ProfileRepository()


def _generate_temp_password() -> str:
    alphabet = string.ascii_letters + string.digits + "!@#$%*?"
    return "".join(secrets.choice(alphabet) for _ in range(12))


def _derive_username(
    first_name: str,
    last_name: str,
    existing: Optional[str],
    *,
    employee_id: str,
) -> str:
    return allocate_collaborator_username(
        first_name,
        last_name,
        exclude_employee_id=employee_id,
        existing=existing,
    )


def _create_user_with_technical_fallback(
    auth: Any,
    *,
    email: str,
    password: str,
    fallback_seed: str,
) -> tuple[str, str]:
    try:
        return auth.create_user(email=email, password=password), email
    except Exception:
        fallback_email = build_dsn_import_auth_email(fallback_seed)
        if fallback_email == email:
            raise
        return auth.create_user(email=fallback_email, password=password), fallback_email


def provision_collaborator_account(
    employee_id: str,
    company_id: str,
    granted_by_user_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Crée le compte auth, le profil, l'accès entreprise et le PDF identifiants
    pour un salarié existant sans compte utilisateur.
    """
    from app.modules.employees.application.commands import _grant_collaborator_company_access

    employee = _employee_repository.get_by_id(employee_id, company_id)
    if not employee:
        raise ValueError("Employé introuvable")

    email = str(employee.get("email") or "").strip()
    if not email:
        email = build_dsn_import_auth_email(employee_id)

    first_name = str(employee.get("first_name") or "").strip()
    last_name = str(employee.get("last_name") or "").strip()
    job_title = str(employee.get("job_title") or "").strip()
    username = _derive_username(
        first_name,
        last_name,
        employee.get("username"),
        employee_id=employee_id,
    )

    storage = get_storage_provider()
    user_id = str(employee.get("user_id") or "").strip() or None
    folder_name = str(employee.get("employee_folder_name") or "").strip() or None

    existing_pdf = find_credentials_pdf_path(
        storage,
        company_id,
        employee_id,
        user_id,
        folder_name,
    )
    if user_id and existing_pdf:
        return {
            "user_id": user_id,
            "username": username,
            "credentials_pdf_path": existing_pdf,
            "generated_password": None,
            "already_provisioned": True,
        }

    password = _generate_temp_password()
    auth = get_auth_provider()

    if not user_id:
        try:
            user_id, email = _create_user_with_technical_fallback(
                auth,
                email=email,
                password=password,
                fallback_seed=employee_id,
            )
        except RuntimeError as exc:
            raise ValueError(
                f"Impossible de créer le compte utilisateur pour {email}: {exc}"
            ) from exc

        _profile_repository.upsert(
            {
                "id": str(user_id),
                "first_name": first_name,
                "last_name": last_name,
                "role": "collaborateur",
                "company_id": company_id,
                "job_title": job_title,
            }
        )

        _employee_repository.update(
            employee_id,
            {
                "email": email,
                "user_id": str(user_id),
                "username": username,
            },
        )

        try:
            _grant_collaborator_company_access(
                str(user_id),
                company_id,
                granted_by_user_id,
            )
        except Exception as grant_err:
            logger.exception("Échec accès entreprise pour %s", employee_id)
            try:
                auth.delete_user(str(user_id))
            except Exception:
                pass
            raise ValueError(
                "Compte auth créé mais échec de l'accès entreprise."
            ) from grant_err
    else:
        try:
            auth.update_user_password(user_id, password)
        except Exception as pwd_err:
            logger.warning(
                "Mot de passe temporaire non défini pour %s: %s",
                employee_id,
                pwd_err,
            )
            password = (
                "— contactez les RH ou utilisez « Mot de passe oublié » "
                "sur la page de connexion"
            )

    company_reader = get_company_reader()
    try:
        company_data = company_reader.get_company_data(company_id)
    except Exception:
        company_data = None
    company_data = company_data or default_company_data_fallback()

    pdf_content = generate_credentials_pdf(
        first_name=first_name,
        last_name=last_name,
        username=username,
        password=password,
        logo_path="",
        company_data=company_data,
    )
    pdf_path = f"{company_id}/{employee_id}/{CREDENTIALS_FILENAME}"
    storage.upload(CREDENTIALS_BUCKET, pdf_path, pdf_content, "application/pdf")
    logger.info(
        "Compte collaborateur provisionné pour l'employé %s (user_id=%s)",
        employee_id,
        user_id,
    )

    return {
        "user_id": str(user_id),
        "username": username,
        "credentials_pdf_path": pdf_path,
        "generated_password": password if not str(password).startswith("—") else None,
        "already_provisioned": False,
    }


def reset_collaborator_credentials(
    employee_id: str,
    company_id: str,
) -> Dict[str, Any]:
    """
    Regénère le mot de passe temporaire et le PDF identifiants pour un compte existant.
    Recalcule l'identifiant prenom.nom si nécessaire (collision / placeholder import).
    """
    employee = _employee_repository.get_by_id(employee_id, company_id)
    if not employee:
        raise ValueError("Employé introuvable")

    user_id = str(employee.get("user_id") or "").strip()
    if not user_id:
        return provision_collaborator_account(employee_id, company_id)

    email = str(employee.get("email") or "").strip()
    first_name = str(employee.get("first_name") or "").strip()
    last_name = str(employee.get("last_name") or "").strip()
    username = allocate_collaborator_username(
        first_name,
        last_name,
        exclude_employee_id=employee_id,
        existing=str(employee.get("username") or "") or None,
    )

    password = _generate_temp_password()
    auth = get_auth_provider()
    auth.update_user_password(user_id, password)

    _employee_repository.update(
        employee_id,
        {"username": username},
    )

    company_reader = get_company_reader()
    try:
        company_data = company_reader.get_company_data(company_id)
    except Exception:
        company_data = None
    company_data = company_data or default_company_data_fallback()

    pdf_content = generate_credentials_pdf(
        first_name=first_name,
        last_name=last_name,
        username=username,
        password=password,
        logo_path="",
        company_data=company_data,
    )
    pdf_path = f"{company_id}/{employee_id}/{CREDENTIALS_FILENAME}"
    get_storage_provider().upload(
        CREDENTIALS_BUCKET, pdf_path, pdf_content, "application/pdf"
    )
    logger.info("Identifiants régénérés pour l'employé %s", employee_id)

    return {
        "user_id": user_id,
        "username": username,
        "email": email,
        "credentials_pdf_path": pdf_path,
        "generated_password": password,
    }
