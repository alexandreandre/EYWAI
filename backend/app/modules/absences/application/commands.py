"""
Commandes (cas d'usage écriture) du module absences.

Utilise domain (règles) et infrastructure (repository, providers, queries).
- ValueError / LookupError : à traduire en HTTPException 400 / 404 par l'appelant.
"""

from __future__ import annotations
from app.core.logging import get_logger

logger = get_logger("modules.absences.application.commands")

from datetime import date
from typing import Any

from app.core.database import supabase
from app.modules.absences.domain.enums import IJSS_ELIGIBLE_TYPES
from app.modules.absences.domain.rules import (
    calculate_acquired_cp,
    requires_salary_certificate,
)
from app.services.document_service import document_service
from app.modules.absences.infrastructure.providers import (
    calendar_update_provider,
    evenement_familial_provider,
    salary_certificate_provider,
)
from app.modules.absences.infrastructure.queries import (
    get_employee_company_id,
    get_employee_hire_date,
    list_absence_requests_validated_for_cp,
)
from app.modules.absences.infrastructure.repository import absence_repository
from app.modules.maintenance_settings.application.queries import get_maintenance_settings
from app.modules.absences.application.queries import (
    build_historique_arrets_annee,
    compute_subrogation_for_absence,
    resolve_nombre_enfants_employee,
)


def _trace_attestation_salaire_ijss_after_generation(
    absence_id: str,
    certificate_id: str | None,
    absence_type: str,
    employee_id: str,
    company_id: str,
    generated_by: str | None,
) -> None:
    """Trace l'attestation dans generated_documents (ne lève pas)."""
    if not certificate_id or not company_id or not employee_id:
        return
    try:
        cert_r = (
            supabase.table("salary_certificates")
            .select("storage_path, filename")
            .eq("id", certificate_id)
            .maybe_single()
            .execute()
        )
        row = cert_r.data if cert_r and cert_r.data else None
        if not row:
            logger.warning(f'⚠️ trace IJSS: certificat {certificate_id} introuvable après génération')
            return
        storage_path = row.get("storage_path") or ""
        document_service.trace_existing_document(
            company_id=company_id,
            employee_id=employee_id,
            document_type="attestation_salaire_ijss",
            category="attestation_situation",
            file_url=storage_path,
            file_name="attestation_salaire_ijss.pdf",
            is_eywai_template=True,
            generation_context={
                "absence_id": str(absence_id),
                "absence_type": absence_type,
                "certificate_id": str(certificate_id),
                "source": "absence_ijss_auto",
            },
            generated_by=generated_by,
        )
    except Exception as e:
        logger.warning(f'⚠️ trace generated_documents attestation IJSS: {e}')
        logger.exception("Exception")


def _hours_for_modulation_absence(employee_id: str, selected_days: list) -> float:
    resp = (
        supabase.table("employees")
        .select("duree_hebdomadaire")
        .eq("id", employee_id)
        .limit(1)
        .execute()
    )
    rows = resp.data or []
    duree = float(rows[0].get("duree_hebdomadaire") or 35) if rows else 35.0
    daily = duree / 5.0
    return round(len(selected_days) * daily, 2)


def _apply_modulation_recovery_on_validation(
    data: dict[str, Any], request_id: str
) -> None:
    """Débite le compte modulation lors de la validation d'une récup."""
    from app.modules.modulation.application.hour_account_commands import (
        create_debit_recovery_movement,
    )
    from app.modules.modulation.application.hour_account_queries import (
        get_employee_account_balance,
    )
    from app.modules.modulation.domain.hour_account_rules import can_debit_recovery
    from app.modules.modulation.infrastructure import repository as modulation_repo

    company_id = str(data.get("company_id") or "")
    employee_id = str(data["employee_id"])
    settings = modulation_repo.get_modulation_settings(company_id)
    if not settings.hour_account_enabled or not settings.recovery_absence_enabled:
        raise ValueError(
            "La récupération sur compte modulation n'est pas activée pour cette entreprise."
        )
    days = data.get("selected_days") or []
    hours = _hours_for_modulation_absence(employee_id, days)
    if hours <= 0:
        raise ValueError("Aucun jour sélectionné pour la récupération modulation.")

    balance = get_employee_account_balance(company_id, employee_id)
    if not can_debit_recovery(balance.account_balance_hours, hours):
        raise ValueError(
            f"Solde modulation insuffisant ({balance.account_balance_hours:.2f} h "
            f"disponibles pour {hours:.2f} h demandées)."
        )

    if settings.recovery_debit_timing != "on_validation":
        return

    first_day = days[0]
    if isinstance(first_day, str):
        ref = date.fromisoformat(first_day[:10])
    else:
        ref = first_day
    create_debit_recovery_movement(
        company_id,
        employee_id,
        ref.year,
        ref.month,
        hours,
        reference_id=request_id,
        note="Récupération modulation (absence validée)",
    )


def create_absence_request(
    request_data: Any, *, enforce_conge_paye_balance: bool = False
) -> dict:
    """
    Crée une demande d'absence.
    Raises: ValueError (validation métier), LookupError (employé non trouvé).
    """
    selected_days = getattr(request_data, "selected_days", None) or []
    if not selected_days:
        raise ValueError("Veuillez sélectionner au moins un jour.")

    absence_type = getattr(request_data, "type", None)
    employee_id = getattr(request_data, "employee_id", None)
    event_subtype = getattr(request_data, "event_subtype", None)

    if enforce_conge_paye_balance and absence_type == "conge_paye":
        from app.modules.absences.application.queries import (
            assert_employee_conge_paye_request_allowed,
        )

        assert_employee_conge_paye_request_allowed(employee_id, selected_days)

    if absence_type == "evenement_familial":
        if not event_subtype:
            raise ValueError(
                "Pour un événement familial, veuillez sélectionner le type d'événement."
            )
        hire_date_raw = get_employee_hire_date(employee_id)
        hire_date = None
        if hire_date_raw:
            hire_date = (
                date.fromisoformat(hire_date_raw)
                if isinstance(hire_date_raw, str)
                else hire_date_raw
            )
        solde_data = evenement_familial_provider.get_solde_evenement(
            employee_id, event_subtype, hire_date
        )
        if solde_data["solde_restant"] <= 0:
            raise ValueError("Aucun jour restant pour cet événement familial.")
        jours_demandes = len(selected_days)
        if jours_demandes > solde_data["solde_restant"]:
            raise ValueError(
                f"Vous avez droit à {solde_data['solde_restant']} jour(s) pour cet événement. "
                f"Vous en avez demandé {jours_demandes}."
            )

    company_id = get_employee_company_id(employee_id)
    if not company_id:
        raise LookupError("Employé non trouvé.")

    db_data = {
        "employee_id": employee_id,
        "company_id": company_id,
        "type": absence_type,
        "comment": getattr(request_data, "comment", None),
        "status": "pending",
        "selected_days": [
            d.isoformat() if hasattr(d, "isoformat") else d for d in selected_days
        ],
        "attachment_url": getattr(request_data, "attachment_url", None),
        "filename": getattr(request_data, "filename", None),
    }
    if absence_type == "evenement_familial" and event_subtype:
        db_data["event_subtype"] = event_subtype

    arret_type = getattr(request_data, "arret_type", None)
    if isinstance(arret_type, str) and arret_type:
        db_data["arret_type"] = arret_type

    return absence_repository.create(db_data)


def update_absence_request_status(
    request_id: str,
    status: str,
    current_user_id: str | None = None,
    subrogation_active: bool | None = None,
) -> dict:
    """
    Met à jour le statut d'une demande (validated / rejected / cancelled).
    Raises: LookupError si demande non trouvée.
    """
    req_before = absence_repository.get_by_id(request_id)
    if not req_before:
        raise LookupError(f"Demande {request_id} non trouvée.")

    update_dict: dict[str, Any] = {"status": status}

    if status == "validated" and req_before.get("type") == "conge_paye":
        hire_date_raw = get_employee_hire_date(req_before["employee_id"])
        hire_date = None
        if hire_date_raw:
            hire_date = (
                date.fromisoformat(hire_date_raw)
                if isinstance(hire_date_raw, str)
                else hire_date_raw
            )
        cp_acquis = calculate_acquired_cp(hire_date, date.today()) if hire_date else 0
        other_validated = list_absence_requests_validated_for_cp(
            req_before["employee_id"], exclude_request_id=request_id
        )
        cp_pris_autres = sum(
            r.get("jours_payes")
            if r.get("jours_payes") is not None
            else len(r.get("selected_days", []))
            for r in other_validated
        )
        available = max(0, cp_acquis - cp_pris_autres)
        requested = len(req_before.get("selected_days") or [])
        update_dict["jours_payes"] = min(requested, available)

    if subrogation_active is not None:
        update_dict["subrogation_active"] = bool(subrogation_active)
    elif status == "validated" and req_before.get("arret_type"):
        emp_res = (
            supabase.table("employees")
            .select("*")
            .eq("id", req_before["employee_id"])
            .maybe_single()
            .execute()
        )
        employee_row = emp_res.data if emp_res else None
        if employee_row and req_before.get("subrogation_active") is None:
            settings_dict = get_maintenance_settings(
                str(employee_row.get("company_id") or "")
            ).model_dump(mode="json")
            resolved_sub = compute_subrogation_for_absence(
                req_before,
                employee_row,
                settings_dict,
                override=None,
            )
            update_dict["subrogation_active"] = resolved_sub

    data = absence_repository.update(request_id, update_dict)
    if not data:
        raise LookupError("Demande introuvable après mise à jour.")

    if status == "validated":
        absence_type = data.get("type", "")
        if absence_type == "recuperation_modulation":
            _apply_modulation_recovery_on_validation(data, request_id)
        days_to_update = [
            date.fromisoformat(d) if isinstance(d, str) else d
            for d in data["selected_days"]
        ]
        arret_type = data.get("arret_type")
        settings_dict = get_maintenance_settings(
            str(data.get("company_id") or "")
        ).model_dump(mode="json")
        sub_active = data.get("subrogation_active")
        if sub_active is None and arret_type:
            emp_res = (
                supabase.table("employees")
                .select("*")
                .eq("id", data["employee_id"])
                .maybe_single()
                .execute()
            )
            employee_row = emp_res.data if emp_res else None
            if employee_row:
                sub_active = compute_subrogation_for_absence(
                    data, employee_row, settings_dict, override=subrogation_active
                )
                absence_repository.update(
                    request_id, {"subrogation_active": bool(sub_active)}
                )
                data["subrogation_active"] = sub_active
        nombre_enfants = resolve_nombre_enfants_employee(str(data["employee_id"]))
        historique: list[dict[str, Any]] = []
        if absence_type in IJSS_ELIGIBLE_TYPES and days_to_update:
            historique = build_historique_arrets_annee(
                str(data["employee_id"]),
                days_to_update[0].year,
                exclude_request_id=request_id,
            )
        calendar_update_provider.update_calendar_from_days(
            data["employee_id"],
            days_to_update,
            absence_type,
            arret_type=str(arret_type) if arret_type else None,
            subrogation_active=sub_active if isinstance(sub_active, bool) else None,
            nombre_enfants=nombre_enfants,
            historique_arrets_annee=historique or None,
        )
        # Types IJSS / attestation : alignés sur IJSS_ELIGIBLE_TYPES (= arrêts avec attestation).
        if requires_salary_certificate(absence_type) and absence_type in IJSS_ELIGIBLE_TYPES:
            try:
                generated_by = str(current_user_id) if current_user_id else None
                certificate_id = salary_certificate_provider.generate_for_absence(
                    request_id, generated_by=generated_by
                )
                if certificate_id:
                    _trace_attestation_salaire_ijss_after_generation(
                        absence_id=request_id,
                        certificate_id=certificate_id,
                        absence_type=absence_type,
                        employee_id=str(data.get("employee_id") or ""),
                        company_id=str(data.get("company_id") or ""),
                        generated_by=generated_by,
                    )
            except Exception as cert_error:
                logger.warning(f"⚠️ Erreur lors de la génération automatique de l'attestation: {cert_error}")
                logger.exception("Exception")

    return data


def generate_salary_certificate(
    absence_id: str, generated_by: str | None = None
) -> str:
    """
    Génère une attestation de salaire pour un arrêt validé.
    Raises: LookupError (arrêt non trouvé), ValueError (non validé ou type non éligible), RuntimeError (échec génération).
    """
    absence = absence_repository.get_by_id(absence_id)
    if not absence:
        raise LookupError("Arrêt non trouvé.")
    if absence.get("status") != "validated":
        raise ValueError("L'arrêt doit être validé pour générer une attestation.")
    if not requires_salary_certificate(absence.get("type", "")):
        raise ValueError("Ce type d'arrêt ne nécessite pas d'attestation de salaire.")
    cert_id = salary_certificate_provider.generate_for_absence(
        absence_id, generated_by=generated_by, replace_existing=True
    )
    if not cert_id:
        raise RuntimeError("Erreur lors de la génération de l'attestation")
    try:
        _trace_attestation_salaire_ijss_after_generation(
            absence_id=absence_id,
            certificate_id=cert_id,
            absence_type=absence.get("type", ""),
            employee_id=str(absence.get("employee_id") or ""),
            company_id=str(absence.get("company_id") or ""),
            generated_by=generated_by,
        )
    except Exception as e:
        logger.warning(f'⚠️ trace attestation IJSS (manuelle): {e}')
        logger.exception("Exception")
    return cert_id


def mark_salary_certificate_transmitted(
    absence_id: str,
    *,
    transmitted: bool,
    user_id: str | None = None,
) -> dict:
    """Marque ou démarque la transmission CPAM d'une attestation."""
    absence = absence_repository.get_by_id(absence_id)
    if not absence:
        raise LookupError("Arrêt non trouvé.")
    cert_resp = (
        supabase.table("salary_certificates")
        .select("id")
        .eq("absence_request_id", absence_id)
        .maybe_single()
        .execute()
    )
    if not cert_resp or not cert_resp.data:
        raise LookupError("Aucune attestation trouvée pour cet arrêt.")
    from datetime import datetime, timezone

    payload: dict[str, Any] = {
        "transmitted_to_cpam": bool(transmitted),
        "transmission_date": datetime.now(timezone.utc).isoformat()
        if transmitted
        else None,
    }
    supabase.table("salary_certificates").update(payload).eq(
        "absence_request_id", absence_id
    ).execute()
    return {
        "absence_id": absence_id,
        "transmitted_to_cpam": bool(transmitted),
        "message": "Transmission CPAM enregistrée."
        if transmitted
        else "Transmission CPAM annulée.",
    }


def create_reconciliation_absence(
    employee_id: str,
    company_id: str,
    current_user_id: str,
    *,
    absence_type: str,
    selected_days: list,
    arret_type: str | None = None,
    comment: str | None = None,
    source: str = "dsn_import",
    supabase_client: Any = None,
) -> dict:
    """
    Crée une absence historique depuis l'import DSN (bypass workflow / soldes CP).

    Réservé au flux import DSN (``source='dsn_import'``).
    """
    if source != "dsn_import":
        raise ValueError("Source de création non autorisée.")

    if not selected_days:
        raise ValueError("Aucun jour sélectionné pour l'absence DSN.")

    sb = supabase_client or supabase
    emp_res = (
        sb.table("employees")
        .select("id, company_id, employment_status")
        .eq("id", employee_id)
        .maybe_single()
        .execute()
    )
    employee = emp_res.data if emp_res else None
    if not employee or str(employee.get("company_id")) != str(company_id):
        raise LookupError("Employé non trouvé.")

    employment_status = str(employee.get("employment_status") or "actif").lower()
    if employment_status in ("en_sortie", "parti"):
        return {
            "skipped": True,
            "reason": "exit_in_progress",
            "employee_id": employee_id,
        }

    days_iso = [
        d.isoformat() if hasattr(d, "isoformat") else str(d)[:10]
        for d in selected_days
    ]

    existing = (
        sb.table("absence_requests")
        .select("id, selected_days, type")
        .eq("employee_id", employee_id)
        .eq("type", absence_type)
        .eq("status", "validated")
        .execute()
    )
    for row in existing.data or []:
        existing_days = set(row.get("selected_days") or [])
        if existing_days == set(days_iso):
            return row

    db_data: dict[str, Any] = {
        "employee_id": employee_id,
        "company_id": company_id,
        "type": absence_type,
        "status": "validated",
        "workflow_step": "approved_rh",
        "selected_days": days_iso,
        "comment": comment or "Import DSN historique",
    }
    if arret_type:
        db_data["arret_type"] = arret_type

    try:
        created = absence_repository.create(db_data)
    except Exception as exc:
        if "processus de sortie" in str(exc).lower():
            return {
                "skipped": True,
                "reason": "exit_in_progress",
                "employee_id": employee_id,
            }
        raise

    try:
        days_to_update = [date.fromisoformat(d) for d in days_iso]
        calendar_update_provider.update_calendar_from_days(
            employee_id,
            days_to_update,
            absence_type,
            arret_type=arret_type,
        )
    except Exception:
        logger.exception("Sync calendrier absence DSN échouée pour %s", created.get("id"))

    return created
