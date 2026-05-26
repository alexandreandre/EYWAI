"""
Cas d'usage en écriture du module employees.

Délègue au repository, auth, storage, company reader, mappers et domain rules.
Comportement identique au router legacy. Aucun accès DB direct.
"""

from __future__ import annotations
from app.core.logging import get_logger, log_app_debug

logger = get_logger("modules.employees.application.commands")

import secrets
import string
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import HTTPException

from app.core.config import API_DIR
from app.modules.employees.application.dto import EmployeeCreateValidationError
from app.modules.employees.domain.rules import (
    build_employee_folder_name,
    default_company_data_fallback,
)
from app.modules.employees.infrastructure.mappers import prepare_employee_insert_data
from app.modules.employees.infrastructure.providers import (
    generate_contract_pdf,
    generate_credentials_pdf,
    get_auth_provider,
    get_company_reader,
    get_storage_provider,
    on_rib_submitted,
    on_rib_updated,
    remove_accents,
)
from app.modules.employees.infrastructure.repository import (
    EmployeeRepository,
    ProfileRepository,
)

_employee_repository = EmployeeRepository()
_profile_repository = ProfileRepository()


def _grant_collaborator_company_access(
    user_id: str,
    company_id: str,
    granted_by_user_id: Optional[str],
) -> None:
    """
    Lie le nouvel utilisateur à l'entreprise dans user_company_accesses (requis pour get_current_user).
    Aligné sur super_admin create_company_user et create_user_with_permissions (template collaborateur).
    """
    from app.modules.users.application.service import (
        copy_template_permissions_to_user,
        get_default_system_template_id,
        get_user_company_access_repository,
    )

    access_repo = get_user_company_access_repository()
    template_id = get_default_system_template_id("collaborateur")
    access_data: Dict[str, Any] = {
        "user_id": user_id,
        "company_id": company_id,
        "role": "collaborateur",
        "is_primary": True,
    }
    if template_id:
        access_data["role_template_id"] = str(template_id)

    existing = access_repo.get_by_user_and_company(user_id, company_id)
    if existing:
        update_payload: Dict[str, Any] = {
            "role": "collaborateur",
            "is_primary": True,
        }
        if template_id:
            update_payload["role_template_id"] = str(template_id)
        access_repo.update(user_id, company_id, update_payload)
    else:
        access_repo.create(access_data)

    if template_id and granted_by_user_id:
        copy_template_permissions_to_user(
            str(template_id),
            user_id,
            company_id,
            granted_by_user_id,
        )


def _default_logo_path() -> Path:
    return API_DIR / "frontend" / "public" / "Colorplast.png"


async def create_employee(
    employee_data: Dict[str, Any],
    company_id: str,
    contract_file_content: Optional[bytes] = None,
    contract_content_type: Optional[str] = None,
    identity_file_content: Optional[bytes] = None,
    identity_filename: Optional[str] = None,
    identity_content_type: Optional[str] = None,
    generate_pdf_contract: bool = False,
    granted_by_user_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Crée un employé (Auth + profil + employees + storage + PDF + RIB).
    Comportement identique à create_employee (router legacy).
    Utilise IAuthProvider, IProfileRepository, IEmployeeRepository, IStorageProvider, ICompanyReader.
    """
    new_user_id = None
    auth = get_auth_provider()
    storage = get_storage_provider()
    company_reader = get_company_reader()

    try:
        first_name = employee_data["first_name"]
        last_name = employee_data["last_name"]
        email = employee_data["email"]
        job_title = employee_data.get("job_title") or ""

        simple_punctuation = "!@#$%*?"
        alphabet = string.ascii_letters + string.digits + simple_punctuation
        password = "".join(secrets.choice(alphabet) for _ in range(12))

        first_name_for_username = remove_accents(first_name).lower().replace(" ", "_")
        last_name_for_username = remove_accents(last_name).lower().replace(" ", "_")
        username = f"{first_name_for_username}.{last_name_for_username}"

        try:
            new_user_id = auth.create_user(email=email, password=password)
        except RuntimeError as auth_err:
            raise HTTPException(
                status_code=400,
                detail=f"Impossible de créer l'utilisateur. L'email '{email}' existe peut-être déjà ou une autre erreur est survenue.",
            ) from auth_err

        profile_data = {
            "id": str(new_user_id),
            "first_name": first_name,
            "last_name": last_name,
            "role": "collaborateur",
            "company_id": company_id,
            "job_title": job_title,
        }
        try:
            _profile_repository.upsert(profile_data)
        except RuntimeError:
            try:
                auth.delete_user(new_user_id)
            except Exception:
                pass
            raise HTTPException(
                status_code=500, detail="Échec de la création du profil utilisateur."
            )

        normalized_last_name = remove_accents(last_name).upper()
        normalized_first_name = remove_accents(first_name).capitalize()
        folder_name = build_employee_folder_name(
            normalized_last_name, normalized_first_name
        )

        db_insert_data = prepare_employee_insert_data(
            employee_data,
            new_user_id=str(new_user_id),
            company_id=company_id,
            username=username,
            folder_name=folder_name,
        )

        try:
            new_employee_db = _employee_repository.create(db_insert_data)
        except RuntimeError:
            try:
                auth.delete_user(new_user_id)
            except Exception:
                pass
            raise HTTPException(
                status_code=500,
                detail="Échec de l'enregistrement de l'employé dans la base de données. Vérifiez les politiques RLS de la table 'employees' et les logs de la base de données Supabase.",
            )

        try:
            _grant_collaborator_company_access(
                str(new_user_id),
                company_id,
                granted_by_user_id,
            )
        except Exception as grant_err:
            logger.exception("Exception")
            try:
                _employee_repository.delete(new_employee_db["id"])
            except Exception:
                logger.exception("Exception")
            try:
                auth.delete_user(new_user_id)
            except Exception:
                logger.exception("Exception")
            raise HTTPException(
                status_code=500,
                detail="Échec de l'enregistrement de l'accès à l'entreprise pour le collaborateur.",
            ) from grant_err

        storage_prefix = f"{company_id}/{new_user_id}"
        logo_path = _default_logo_path()

        if generate_pdf_contract:
            try:
                company_data = company_reader.get_company_data(company_id)
                if not company_data:
                    company_data = default_company_data_fallback()
                contract_pdf_content = generate_contract_pdf(
                    employee_data=db_insert_data,
                    company_data=company_data,
                    logo_path=str(logo_path),
                )
                storage.upload(
                    "contracts",
                    f"{storage_prefix}/contrat.pdf",
                    contract_pdf_content,
                    "application/pdf",
                )
            except Exception as pdf_gen_error:
                logger.warning(f'ERROR: Échec de la génération du contrat PDF: {pdf_gen_error}')
                logger.exception("Exception")

        elif contract_file_content is not None:
            try:
                storage.upload(
                    "contracts",
                    f"{storage_prefix}/contrat.pdf",
                    contract_file_content,
                    contract_content_type or "application/pdf",
                )
            except Exception as storage_error:
                logger.warning(f"ERROR: Échec de l'upload du contrat PDF: {storage_error}")
                logger.exception("Exception")

        if identity_file_content is not None:
            file_extension = ".pdf"
            if identity_filename:
                lower = identity_filename.lower()
                if lower.endswith(".pdf"):
                    file_extension = ".pdf"
                elif lower.endswith((".jpg", ".jpeg")):
                    file_extension = ".jpg"
                elif lower.endswith(".png"):
                    file_extension = ".png"
                else:
                    file_extension = Path(identity_filename).suffix or ".pdf"
            else:
                ct = identity_content_type or ""
                if "pdf" in ct:
                    file_extension = ".pdf"
                elif "jpeg" in ct or "jpg" in ct:
                    file_extension = ".jpg"
                elif "png" in ct:
                    file_extension = ".png"
            content_type = identity_content_type
            if not content_type:
                content_type = (
                    "application/pdf"
                    if file_extension == ".pdf"
                    else "image/jpeg"
                    if file_extension in (".jpg", ".jpeg")
                    else "image/png"
                    if file_extension == ".png"
                    else "application/octet-stream"
                )
            try:
                storage.upload(
                    "piece_identite",
                    f"{storage_prefix}/piece_identite{file_extension}",
                    identity_file_content,
                    content_type,
                )
            except Exception as storage_error:
                logger.warning(f"ERROR: Échec de l'upload de la pièce d'identité: {storage_error}")
                logger.exception("Exception")

        try:
            pdf_content = generate_credentials_pdf(
                first_name=first_name,
                last_name=last_name,
                username=username,
                password=password,
                logo_path=str(logo_path),
            )
            storage.upload(
                "creation_compte",
                f"{storage_prefix}/creation_compte.pdf",
                pdf_content,
                "application/pdf",
            )
        except Exception as pdf_error:
            logger.warning(f'ERROR: Échec de la génération/upload du PDF de création de compte: {pdf_error}')
            logger.exception("Exception")

        response_data = dict(new_employee_db)
        response_data["generated_password"] = password

        try:
            coord = employee_data.get("coordonnees_bancaires") or {}
            new_iban = (coord.get("iban") or "").strip()
            if new_iban:
                duplicates = on_rib_submitted(
                    company_id,
                    str(new_employee_db.get("id")),
                    new_iban,
                    f"{first_name} {last_name}".strip(),
                )
                if duplicates:
                    names = [
                        f"{d.get('first_name', '')} {d.get('last_name', '')}".strip()
                        for d in duplicates
                    ]
                    response_data["warnings"] = [
                        f"RIB en doublon avec : {', '.join(names)}"
                    ]
        except Exception as rib_err:
            logger.warning(f'WARN: Vérification RIB doublon ignorée: {rib_err}')
            logger.exception("Exception")

        return response_data

    except HTTPException:
        if new_user_id:
            try:
                auth.delete_user(new_user_id)
            except Exception as delete_error:
                logger.warning(f"FATAL: Impossible de supprimer l'utilisateur orphelin {new_user_id}: {delete_error}")
        raise
    except EmployeeCreateValidationError:
        if new_user_id:
            try:
                auth.delete_user(new_user_id)
            except Exception as delete_error:
                logger.warning(f"FATAL: Impossible de supprimer l'utilisateur orphelin {new_user_id}: {delete_error}")
        raise
    except Exception as e:
        if new_user_id:
            try:
                auth.delete_user(new_user_id)
            except Exception as delete_error:
                logger.warning(f"FATAL: Impossible de supprimer l'utilisateur orphelin {new_user_id}: {delete_error}")
        error_message = str(e)
        field_errors = {}
        if "duplicate key" in error_message.lower():
            if "email" in error_message.lower():
                field_errors["email"] = "Cette adresse email est déjà utilisée"
            if "nir" in error_message.lower():
                field_errors["nir"] = (
                    "Ce numéro de sécurité sociale est déjà enregistré"
                )
        if field_errors:
            raise EmployeeCreateValidationError(
                field_errors=field_errors,
                message="Erreur lors de la création de l'employé",
            ) from e
        logger.exception("Exception")
        raise HTTPException(status_code=500, detail=f"Erreur interne : {str(e)}") from e


def update_employee(employee_id: str, update_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Met à jour un employé (dont alertes RIB si coordonnées bancaires modifiées).
    Comportement identique à update_employee (router legacy).
    """
    if "coordonnees_bancaires" in update_data:
        try:
            curr = _employee_repository.get_by_id_only(employee_id)
            if curr:
                company_id = curr.get("company_id")
                emp_name = (
                    f"{curr.get('first_name', '')} {curr.get('last_name', '')}".strip()
                )
                old_coord = curr.get("coordonnees_bancaires") or {}
                old_iban = (
                    (old_coord.get("iban") or "").strip()
                    if isinstance(old_coord, dict)
                    else ""
                )
                new_coord = update_data.get("coordonnees_bancaires") or {}
                new_iban = (
                    (new_coord.get("iban") or "").strip()
                    if isinstance(new_coord, dict)
                    else ""
                )
                if new_iban and company_id:
                    on_rib_updated(
                        company_id, employee_id, old_iban, new_iban, emp_name
                    )
                    on_rib_submitted(company_id, employee_id, new_iban, emp_name)
        except Exception as rib_err:
            logger.warning(f'WARN: Alertes RIB ignorées lors de la mise à jour: {rib_err}')
            logger.exception("Exception")

    updated = _employee_repository.update(employee_id, update_data)
    if updated is None:
        raise HTTPException(
            status_code=404, detail="Employé non trouvé ou aucune donnée modifiée."
        )
    return updated


def apply_salary_update(
    employee_id: str,
    company_id: str,
    ancien_salaire: Dict[str, Any],
    nouveau_salaire: Dict[str, Any],
    motif: str | None,
    effective_date: str,
    created_by: str,
) -> Dict[str, Any]:
    """
    Met à jour salaire_de_base et insère une ligne salary_history.
    Retourne la ligne d'historique insérée.
    """
    return _employee_repository.update_salary(
        employee_id=employee_id,
        company_id=company_id,
        ancien_salaire=ancien_salaire,
        nouveau_salaire=nouveau_salaire,
        motif=motif,
        effective_date=effective_date,
        created_by=created_by,
    )


def delete_employee(employee_id: str) -> None:
    """
    Supprime un employé : permissions, accès entreprises, profil, ligne employees,
    puis compte Supabase Auth. Sans ce pré-nettoyage, auth.admin.delete_user échoue
    souvent (FK / « Database error deleting user »).
    """
    from app.modules.users.application.service import (
        get_user_company_access_repository,
        get_user_permission_repository,
        get_user_repository,
    )

    auth = get_auth_provider()
    emp = _employee_repository.get_by_id_only(employee_id)
    if emp is None:
        raise HTTPException(status_code=404, detail="Employé non trouvé.")

    auth_uid = str(emp.get("user_id") or employee_id)

    try:
        access_repo = get_user_company_access_repository()
        perm_repo = get_user_permission_repository()
        user_repo = get_user_repository()

        for acc in access_repo.get_accesses_for_user(auth_uid):
            cid = acc["company_id"]
            perm_repo.delete_for_user_company(auth_uid, cid)
            access_repo.delete(auth_uid, cid)

        user_repo.delete(auth_uid)
        _employee_repository.delete(employee_id)

        try:
            auth.delete_user(auth_uid)
        except Exception as auth_exc:
            msg = str(auth_exc).lower()
            if "not found" in msg:
                return
            raise
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Exception")
        raise HTTPException(
            status_code=500,
            detail=f"Erreur interne du serveur lors de la suppression: {str(e)}",
        ) from e
