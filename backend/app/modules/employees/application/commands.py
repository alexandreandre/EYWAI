"""
Cas d'usage en écriture du module employees.

Délègue au repository, auth, storage, company reader, mappers et domain rules.
Comportement identique au router legacy. Aucun accès DB direct.
"""

from __future__ import annotations
from app.core.logging import get_logger

logger = get_logger("modules.employees.application.commands")

import secrets
import string
import uuid
from datetime import date as _date
from pathlib import Path
from typing import Any, Dict, Iterator, Optional

from fastapi import HTTPException

from app.modules.employees.application.dto import EmployeeCreateValidationError
from app.modules.employees.domain.rules import (
    build_dsn_import_auth_email,
    build_employee_folder_name,
    default_company_data_fallback,
    normalize_temps_travail_fields,
)
from app.modules.employees.infrastructure.queries import allocate_collaborator_username
from app.modules.employees.domain.salary_timeline import est_augmentation_planifiee
from app.modules.employees.domain.trial_period import TRIAL_JSON_STATUT_CONFIRMED
from app.modules.onboarding.domain.profile import (
    enrich_employee_profile_completeness,
    is_profile_complete,
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

        username = allocate_collaborator_username(first_name, last_name)

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

        employee_id = str(new_employee_db["id"])
        storage_prefix = f"{company_id}/{employee_id}"
        company_data = company_reader.get_company_data(company_id)
        if not company_data:
            company_data = default_company_data_fallback()

        if generate_pdf_contract:
            try:
                contract_pdf_content = generate_contract_pdf(
                    employee_data=db_insert_data,
                    company_data=company_data,
                    logo_path="",
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
                logo_path="",
                company_data=company_data,
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


def create_employee_imported(
    employee_data: Dict[str, Any],
    company_id: str,
) -> Dict[str, Any]:
    """
    Crée un salarié importé (DSN) avec compte Auth collaborateur.
    Génère le PDF identifiants avec un mot de passe temporaire réel.
    """
    first_name = employee_data["first_name"]
    last_name = employee_data["last_name"]
    technical_email_seed = uuid.uuid4().hex
    email = employee_data.get("email") or build_dsn_import_auth_email(
        technical_email_seed
    )

    normalized_last_name = remove_accents(last_name).upper()
    normalized_first_name = remove_accents(first_name).capitalize()
    folder_name = build_employee_folder_name(normalized_last_name, normalized_first_name)
    username = allocate_collaborator_username(first_name, last_name)
    alphabet = string.ascii_letters + string.digits + "!@#$%*?"
    password = "".join(secrets.choice(alphabet) for _ in range(12))

    auth = get_auth_provider()
    new_user_id: Optional[str] = None
    try:
        new_user_id, email = _create_user_with_technical_fallback(
            auth,
            email=email,
            password=password,
            fallback_seed=technical_email_seed,
        )
    except RuntimeError as auth_err:
        raise HTTPException(
            status_code=400,
            detail=f"Impossible de créer le compte collaborateur importé : {auth_err}",
        ) from auth_err

    try:
        _profile_repository.upsert(
            {
                "id": str(new_user_id),
                "first_name": first_name,
                "last_name": last_name,
                "role": "collaborateur",
                "company_id": company_id,
                "job_title": employee_data.get("job_title") or "",
            }
        )
        _grant_collaborator_company_access(str(new_user_id), company_id, None)
    except Exception as access_err:
        try:
            auth.delete_user(str(new_user_id))
        except Exception:
            pass
        raise HTTPException(
            status_code=500,
            detail="Compte importé créé mais échec du profil ou de l'accès entreprise.",
        ) from access_err

    db_insert_data = prepare_employee_insert_data(
        employee_data,
        new_user_id=str(new_user_id),
        company_id=company_id,
        username=username,
        folder_name=folder_name,
    )
    db_insert_data["employment_status"] = employee_data.get("employment_status") or "actif"
    db_insert_data["email"] = email

    try:
        new_employee_db = _employee_repository.create(db_insert_data)
    except Exception:
        try:
            auth.delete_user(str(new_user_id))
        except Exception:
            pass
        raise

    employee_id = str(new_employee_db.get("id") or new_user_id)

    try:
        from app.modules.employees.application.credentials_pdf import (
            store_credentials_pdf_for_employee,
        )

        store_credentials_pdf_for_employee(
            employee_id,
            company_id,
            password=password,
            username=username,
        )
    except Exception as pdf_err:
        logger.warning(
            "Échec génération PDF identifiants pour salarié importé %s: %s",
            employee_id,
            pdf_err,
        )
    response = dict(new_employee_db)
    response["generated_password"] = password
    return response


def activate_imported_employee_account(
    employee_id: str,
    company_id: str,
    email: str,
    granted_by_user_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Crée le compte Auth pour un salarié importé et active son accès entreprise.
    """
    emp = _employee_repository.get_by_id(employee_id, company_id)
    if emp is None:
        raise HTTPException(status_code=404, detail="Employé non trouvé.")
    if emp.get("user_id"):
        raise HTTPException(
            status_code=400,
            detail="Ce salarié possède déjà un compte utilisateur.",
        )

    auth = get_auth_provider()
    alphabet = string.ascii_letters + string.digits + "!@#$%*?"
    password = "".join(secrets.choice(alphabet) for _ in range(12))

    try:
        new_user_id = auth.create_user(email=email, password=password)
    except RuntimeError as auth_err:
        raise HTTPException(
            status_code=400,
            detail=f"Impossible de créer le compte : {auth_err}",
        ) from auth_err

    profile_data = {
        "id": str(new_user_id),
        "first_name": emp.get("first_name", ""),
        "last_name": emp.get("last_name", ""),
        "role": "collaborateur",
        "company_id": company_id,
        "job_title": emp.get("job_title") or "",
    }
    try:
        _profile_repository.upsert(profile_data)
    except RuntimeError:
        try:
            auth.delete_user(new_user_id)
        except Exception:
            pass
        raise HTTPException(status_code=500, detail="Échec de la création du profil.")

    username = allocate_collaborator_username(
        str(emp.get("first_name") or ""),
        str(emp.get("last_name") or ""),
        exclude_employee_id=employee_id,
        existing=str(emp.get("username") or "") or None,
    )
    update_employee(
        employee_id,
        {
            "email": email,
            "username": username,
        },
    )
    _employee_repository.update(
        employee_id,
        {"user_id": str(new_user_id), "employment_status": "actif"},
    )

    try:
        _grant_collaborator_company_access(
            str(new_user_id),
            company_id,
            granted_by_user_id,
        )
    except Exception as grant_err:
        raise HTTPException(
            status_code=500,
            detail="Compte créé mais échec de l'accès entreprise.",
        ) from grant_err

    credentials_pdf_path: Optional[str] = None
    try:
        from app.modules.employees.application.credentials_pdf import (
            store_credentials_pdf_for_employee,
        )

        credentials_pdf_path = store_credentials_pdf_for_employee(
            employee_id,
            company_id,
            password=password,
            username=username,
        )
    except Exception as pdf_err:
        logger.warning(
            "Échec génération PDF identifiants après activation %s: %s",
            employee_id,
            pdf_err,
        )

    return {
        "employee_id": employee_id,
        "user_id": str(new_user_id),
        "email": email,
        "username": username,
        "generated_password": password,
        "credentials_pdf_path": credentials_pdf_path,
    }


def _maybe_activate_after_onboarding(employee_id: str) -> None:
    """Passe en actif un salarié en onboarding dont la fiche paie est complète."""
    emp = _employee_repository.get_by_id_only(employee_id)
    if not emp:
        return
    if str(emp.get("employment_status") or "").lower() != "en_onboarding":
        return
    if is_profile_complete(emp):
        _employee_repository.update(employee_id, {"employment_status": "actif"})


def _merge_json_dicts(
    current: Dict[str, Any] | None, update: Dict[str, Any]
) -> Dict[str, Any]:
    merged = dict(current or {})
    for key, value in update.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = {**merged[key], **value}
        else:
            merged[key] = value
    return merged


def update_employee(employee_id: str, update_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Met à jour un employé (dont alertes RIB si coordonnées bancaires modifiées).
    Comportement identique à update_employee (router legacy).
    """
    for _key, _val in list(update_data.items()):
        if isinstance(_val, _date):
            update_data[_key] = _val.isoformat()

    if "is_temps_partiel" in update_data or "duree_hebdomadaire" in update_data:
        curr = _employee_repository.get_by_id_only(employee_id) or {}
        is_tp, duree = normalize_temps_travail_fields(
            update_data.get("is_temps_partiel", curr.get("is_temps_partiel")),
            update_data.get("duree_hebdomadaire", curr.get("duree_hebdomadaire")),
        )
        update_data["is_temps_partiel"] = is_tp
        update_data["duree_hebdomadaire"] = duree

    if "specificites_paie" in update_data:
        curr = _employee_repository.get_by_id_only(employee_id)
        current_spec = (curr or {}).get("specificites_paie") or {}
        if not isinstance(current_spec, dict):
            current_spec = {}
        incoming_spec = update_data.get("specificites_paie") or {}
        if not isinstance(incoming_spec, dict):
            incoming_spec = {}
        update_data["specificites_paie"] = _merge_json_dicts(
            current_spec, incoming_spec
        )

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

    try:
        updated = _employee_repository.update(employee_id, update_data)
    except Exception as e:
        error_message = str(e)
        if "duplicate key" in error_message.lower() and "nir" in error_message.lower():
            raise HTTPException(
                status_code=400,
                detail="Ce numéro de sécurité sociale est déjà enregistré.",
            ) from e
        raise
    if updated is None:
        raise HTTPException(
            status_code=404, detail="Employé non trouvé ou aucune donnée modifiée."
        )
    _maybe_activate_after_onboarding(employee_id)
    refreshed = _employee_repository.get_by_id_only(employee_id)
    result = refreshed if refreshed is not None else updated
    return enrich_employee_profile_completeness(result)


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
    Insère salary_history. Met à jour salaire_de_base seulement si effective_date <= aujourd'hui.
    Retourne la ligne d'historique insérée.
    """
    eff = _date.fromisoformat(str(effective_date)[:10])
    row = _employee_repository.insert_salary_history(
        employee_id=employee_id,
        company_id=company_id,
        ancien_salaire=ancien_salaire,
        nouveau_salaire=nouveau_salaire,
        motif=motif,
        effective_date=effective_date,
        created_by=created_by,
    )
    if not est_augmentation_planifiee(eff, _date.today()):
        synced = _employee_repository.sync_salaire_actif(
            employee_id, company_id, _date.today()
        )
        if synced is None:
            raise HTTPException(
                status_code=404,
                detail="Employé introuvable lors de la synchronisation du salaire.",
            )
    _maybe_activate_after_onboarding(employee_id)
    return row


def sync_employee_salaire_actif(
    employee_id: str,
    company_id: str,
    as_of: _date | None = None,
) -> Optional[Dict[str, Any]]:
    """Synchronise employees.salaire_de_base depuis salary_history."""
    return _employee_repository.sync_salaire_actif(
        employee_id, company_id, as_of or _date.today()
    )


def upload_employee_contract(
    employee_id: str,
    company_id: str,
    file_content: bytes,
    content_type: Optional[str] = None,
) -> None:
    """Dépose ou remplace le contrat PDF signé d'un collaborateur existant."""
    if not file_content:
        raise HTTPException(status_code=400, detail="Fichier vide.")

    employee = _employee_repository.get_by_id(employee_id, company_id)
    if employee is None:
        raise HTTPException(status_code=404, detail="Employé non trouvé.")

    storage = get_storage_provider()
    storage_prefix = f"{company_id}/{employee_id}"
    try:
        storage.upload(
            "contracts",
            f"{storage_prefix}/contrat.pdf",
            file_content,
            content_type or "application/pdf",
        )
    except Exception as storage_error:
        logger.warning("ERROR: Échec de l'upload du contrat PDF: %s", storage_error)
        logger.exception("Exception")
        raise HTTPException(
            status_code=500,
            detail="Impossible d'enregistrer le contrat PDF.",
        ) from storage_error

    # Le dépôt du contrat peut être la dernière étape d'onboarding : si la fiche
    # paie est déjà complète, activer le salarié sans attendre une autre action.
    _maybe_activate_after_onboarding(employee_id)


_EMPLOYEE_DELETE_STEP_LABELS: Dict[str, str] = {
    "preparation": "Lecture de la fiche…",
    "storage": "Suppression des fichiers (contrats, bulletins…)…",
    "data": "Suppression des données (absences, paie, plannings…)…",
    "account": "Retrait des accès et du compte…",
    "finalize": "Finalisation…",
}


def _employee_display_name(emp: Dict[str, Any], employee_id: str) -> str:
    first = (emp.get("first_name") or "").strip()
    last = (emp.get("last_name") or "").strip()
    return f"{first} {last}".strip() or employee_id


def _iter_employee_deletion(
    employee_id: str, company_id: str
) -> Iterator[Dict[str, Any]]:
    """Émet une étape NDJSON par phase réelle de suppression d'un salarié."""
    from app.modules.employees.application.deletion_cleanup import (
        cleanup_employee_orphan_rows,
        cleanup_employee_storage,
        cleanup_user_account_for_company,
    )
    from app.shared.db_errors import raise_http_for_db_error

    auth = get_auth_provider()

    yield {
        "event": "step",
        "step": "preparation",
        "label": _EMPLOYEE_DELETE_STEP_LABELS["preparation"],
    }
    emp = _employee_repository.get_by_id(employee_id, company_id)
    if emp is None:
        raise HTTPException(status_code=404, detail="Employé non trouvé.")

    auth_uid = str(emp.get("user_id") or employee_id)

    try:
        yield {
            "event": "step",
            "step": "storage",
            "label": _EMPLOYEE_DELETE_STEP_LABELS["storage"],
        }
        cleanup_employee_storage(company_id, employee_id)

        yield {
            "event": "step",
            "step": "data",
            "label": _EMPLOYEE_DELETE_STEP_LABELS["data"],
        }
        cleanup_employee_orphan_rows(employee_id)

        yield {
            "event": "step",
            "step": "account",
            "label": _EMPLOYEE_DELETE_STEP_LABELS["account"],
        }
        delete_auth_account = cleanup_user_account_for_company(
            auth_uid, company_id, employee_id
        )
        _employee_repository.delete(employee_id)

        if delete_auth_account:
            try:
                auth.delete_user(auth_uid)
            except Exception as auth_exc:
                msg = str(auth_exc).lower()
                if "not found" not in msg:
                    raise

        yield {
            "event": "step",
            "step": "finalize",
            "label": _EMPLOYEE_DELETE_STEP_LABELS["finalize"],
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("delete_employee failed for %s", employee_id)
        raise_http_for_db_error(exc)


def iter_delete_all_company_employees(
    company_id: str,
) -> Iterator[Dict[str, Any]]:
    """Supprime tous les employés et émet la progression (NDJSON)."""
    from app.core.database import supabase

    company_resp = (
        supabase.table("companies")
        .select("id, company_name")
        .eq("id", company_id)
        .maybe_single()
        .execute()
    )
    if not company_resp.data:
        raise LookupError("Entreprise non trouvée")

    company_name = company_resp.data.get("company_name") or company_id
    employees = _employee_repository.get_by_company(company_id)
    total = len(employees)
    removed: list[Dict[str, str]] = []
    failed: list[Dict[str, str]] = []

    yield {
        "event": "started",
        "company_id": company_id,
        "company_name": company_name,
        "total": total,
    }

    for index, emp in enumerate(employees, start=1):
        employee_id = str(emp.get("id") or "")
        if not employee_id:
            continue
        display_name = _employee_display_name(emp, employee_id)
        context = {
            "index": index,
            "total": total,
            "employee_id": employee_id,
            "employee_name": display_name,
        }

        yield {"event": "employee_started", **context}

        try:
            for step_event in _iter_employee_deletion(employee_id, company_id):
                yield {**step_event, **context}
            removed.append(
                {"employee_id": employee_id, "employee_name": display_name}
            )
            yield {"event": "employee_done", **context}
        except HTTPException as exc:
            error = str(exc.detail)
            failed.append(
                {
                    "employee_id": employee_id,
                    "employee_name": display_name,
                    "error": error,
                }
            )
            yield {"event": "employee_failed", "error": error, **context}
        except Exception as exc:
            logger.warning(
                "Suppression employé %s échouée pour entreprise %s : %s",
                employee_id,
                company_id,
                exc,
            )
            error = str(exc)
            failed.append(
                {
                    "employee_id": employee_id,
                    "employee_name": display_name,
                    "error": error,
                }
            )
            yield {"event": "employee_failed", "error": error, **context}

    result = {
        "success": len(failed) == 0,
        "company_id": company_id,
        "company_name": company_name,
        "requested_count": total,
        "removed_count": len(removed),
        "removed": removed,
        "failed": failed,
    }

    if len(failed) == 0:
        from app.modules.employees.application.company_onboarding_reset import (
            reset_company_onboarding_after_employee_purge,
        )

        try:
            result["onboarding_reset"] = reset_company_onboarding_after_employee_purge(
                company_id
            )
        except Exception as exc:
            logger.warning(
                "Réinitialisation onboarding échouée pour entreprise %s : %s",
                company_id,
                exc,
            )
            result["onboarding_reset_error"] = str(exc)

    yield {"event": "completed", "result": result}


def delete_all_company_employees(company_id: str) -> Dict[str, Any]:
    """Supprime tous les employés d'une entreprise et leurs données liées."""
    result: Dict[str, Any] | None = None
    for event in iter_delete_all_company_employees(company_id):
        if event.get("event") == "completed":
            result = event.get("result")
    if result is None:
        raise RuntimeError("Suppression interrompue sans résultat final")
    return result


def delete_employee(employee_id: str, company_id: str) -> None:
    """
    Supprime un employé et toutes ses données liées (cascade DB + storage + compte).
    """
    for _ in _iter_employee_deletion(employee_id, company_id):
        pass


def confirm_trial_period(employee_id: str, company_id: str) -> Dict[str, Any]:
    """Confirme l'embauche en clôturant le suivi de période d'essai."""
    emp = _employee_repository.get_by_id(employee_id, company_id)
    if emp is None:
        raise HTTPException(status_code=404, detail="Employé non trouvé.")

    current_pe = emp.get("periode_essai")
    if not isinstance(current_pe, dict) or not current_pe:
        raise HTTPException(
            status_code=400,
            detail="Aucune période d'essai renseignée pour ce collaborateur.",
        )

    merged_pe = dict(current_pe)
    merged_pe["statut"] = TRIAL_JSON_STATUT_CONFIRMED

    updated = _employee_repository.update(employee_id, {"periode_essai": merged_pe})
    if updated is None:
        raise HTTPException(
            status_code=404, detail="Employé non trouvé ou aucune donnée modifiée."
        )
    return updated
