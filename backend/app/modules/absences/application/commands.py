"""
Commandes (cas d'usage écriture) du module absences.

Utilise domain (règles) et infrastructure (repository, providers, queries).
- ValueError / LookupError : à traduire en HTTPException 400 / 404 par l'appelant.
"""
from __future__ import annotations

import sys
import traceback
from datetime import date
from typing import Any

from app.modules.absences.domain.rules import (
    calculate_acquired_cp,
    requires_salary_certificate,
)
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


def create_absence_request(request_data: Any) -> dict:
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

    return absence_repository.create(db_data)


def update_absence_request_status(
    request_id: str,
    status: str,
    current_user_id: str | None = None,
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
        cp_acquis = (
            calculate_acquired_cp(hire_date, date.today()) if hire_date else 0
        )
        other_validated = list_absence_requests_validated_for_cp(
            req_before["employee_id"], exclude_request_id=request_id
        )
        cp_pris_autres = sum(
            r.get("jours_payes") if r.get("jours_payes") is not None else len(r.get("selected_days", []))
            for r in other_validated
        )
        available = max(0, cp_acquis - cp_pris_autres)
        requested = len(req_before.get("selected_days") or [])
        update_dict["jours_payes"] = min(requested, available)

    data = absence_repository.update(request_id, update_dict)
    if not data:
        raise LookupError("Demande introuvable après mise à jour.")

    if status == "validated":
        days_to_update = [
            date.fromisoformat(d) if isinstance(d, str) else d
            for d in data["selected_days"]
        ]
        calendar_update_provider.update_calendar_from_days(
            data["employee_id"], days_to_update, data["type"]
        )
        absence_type = data.get("type", "")
        if requires_salary_certificate(absence_type):
            try:
                generated_by = str(current_user_id) if current_user_id else None
                salary_certificate_provider.generate_for_absence(
                    request_id, generated_by=generated_by
                )
            except Exception as cert_error:
                print(
                    f"⚠️ Erreur lors de la génération automatique de l'attestation: {cert_error}",
                    file=sys.stderr,
                )
                traceback.print_exc()

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
        raise ValueError(
            "L'arrêt doit être validé pour générer une attestation."
        )
    if not requires_salary_certificate(absence.get("type", "")):
        raise ValueError(
            "Ce type d'arrêt ne nécessite pas d'attestation de salaire."
        )
    cert_id = salary_certificate_provider.generate_for_absence(
        absence_id, generated_by=generated_by
    )
    if not cert_id:
        raise RuntimeError("Erreur lors de la génération de l'attestation")
    return cert_id
