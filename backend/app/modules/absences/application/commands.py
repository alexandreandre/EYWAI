"""
Commandes (cas d'usage écriture) du module absences.

Utilise domain (règles) et infrastructure (repository, providers, queries).
- ValueError / LookupError : à traduire en HTTPException 400 / 404 par l'appelant.
"""

from __future__ import annotations
from app.core.logging import get_logger

logger = get_logger("modules.absences.application.commands")

import math
from datetime import date
from typing import Any

from app.core.database import supabase
from app.modules.absences.domain.enums import (
    IJSS_ELIGIBLE_TYPES,
    type_calendrier_projete,
)
from app.modules.absences.domain.rules import (
    quotite_demi_journees,
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
    get_employee_statut,
)
from app.shared.domain.employment_rules import is_forfait_jour
from app.modules.absences.infrastructure.repository import absence_repository
from app.modules.maintenance_settings.application.queries import get_maintenance_settings
from app.modules.absences.application.queries import (
    build_historique_arrets_annee,
    compute_subrogation_for_absence,
    get_cp_solde_restant,
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


def _verifier_modulation_recovery(data: dict[str, Any]):
    """Vérifie settings + solde d'une récup modulation. Raises ValueError.

    Appelée AVANT d'écrire le statut « validated » : sinon un refus (solde
    insuffisant, modulation désactivée) laissait l'absence validée en base
    sans mouvement de débit.
    Retourne (heures à débiter, settings modulation).
    """
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
    return hours, settings


def _apply_modulation_recovery_on_validation(
    data: dict[str, Any], request_id: str, *, precheck=None
) -> None:
    """Débite le compte modulation lors de la validation d'une récup.

    `precheck` : résultat de _verifier_modulation_recovery déjà obtenu AVANT
    l'écriture du statut — revérifier ici pourrait échouer après coup et
    laisser l'absence validée sans débit.
    """
    from app.modules.modulation.application.hour_account_commands import (
        create_debit_recovery_movement,
    )

    company_id = str(data.get("company_id") or "")
    employee_id = str(data["employee_id"])
    days = data.get("selected_days") or []
    hours, settings = (
        precheck if precheck is not None else _verifier_modulation_recovery(data)
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
    demi_journees_raw = getattr(request_data, "demi_journees", None) or {}
    # Clés normalisées en ISO : c'est la forme stockée (jsonb) et lue partout.
    demi_journees = {
        (k if isinstance(k, str) else k.isoformat()): v
        for k, v in demi_journees_raw.items()
    }
    if demi_journees and is_forfait_jour(get_employee_statut(employee_id)):
        # Le forfait-jours se décompte à la journée (réel 0/1) : une
        # demi-journée débiterait 0,5 au solde sans ligne CP fiable au
        # bulletin (l'analyseur forfait n'a pas la granularité).
        raise ValueError(
            "La demi-journée de congé n'est pas disponible pour un salarié "
            "au forfait-jours (décompte à la journée)."
        )

    if enforce_conge_paye_balance and absence_type == "conge_paye":
        from app.modules.absences.application.queries import (
            assert_employee_conge_paye_request_allowed,
        )

        assert_employee_conge_paye_request_allowed(
            employee_id, selected_days, demi_journees=demi_journees
        )

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
    if demi_journees:
        db_data["demi_journees"] = demi_journees
    heures_par_jour_raw = getattr(request_data, "heures_par_jour", None) or {}
    if heures_par_jour_raw:
        db_data["heures_par_jour"] = {
            (k if isinstance(k, str) else k.isoformat()): float(v)
            for k, v in heures_par_jour_raw.items()
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

    if status == "validated" and req_before.get("status") == "validated":
        # Garde de transition : re-valider recalculerait jours_payes (à 0,
        # ses propres jours comptant désormais comme « pris ») et
        # re-débiterait le compte modulation.
        raise ValueError("Demande déjà validée.")

    update_dict: dict[str, Any] = {"status": status}

    precheck_modulation = None
    if status == "validated" and req_before.get("type") == "recuperation_modulation":
        # Contrôle AVANT l'écriture du statut ; le résultat (heures, settings)
        # est réutilisé au débit pour ne pas revérifier après l'écriture — une
        # seconde vérification qui échouerait recréerait l'incohérence
        # « validée sans débit ».
        precheck_modulation = _verifier_modulation_recovery(req_before)

    if status == "validated" and req_before.get("type") == "conge_paye":
        # Solde = celui AFFICHÉ à la RH (report N-1, ajustements, ancienneté,
        # CET compris) : l'ancien calcul maison (acquis période courante − pris)
        # marquait « sans solde » des jours couverts par le report (retour
        # Gaëlle 03/09). La colonne jours_payes est numérique depuis la
        # migration demi-journées ; on paie par pas de 0,5 jour — un solde à
        # 10,33 paie au plus 10,5… non : 10,0 ou 10,5 ≤ solde, donc 10,0.
        available = get_cp_solde_restant(req_before["employee_id"])
        requested = quotite_demi_journees(
            req_before.get("selected_days") or [],
            req_before.get("demi_journees"),
        )
        payable = math.floor(float(available) * 2) / 2
        update_dict["jours_payes"] = min(requested, payable)

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

    if status == "cancelled" and req_before.get("status") == "validated":
        if req_before.get("type") == "recuperation_modulation":
            # Le re-crédit du compte modulation n'existe pas encore : annuler
            # laisserait le salarié débité pour une absence disparue.
            raise ValueError(
                "Annulation impossible pour une récupération modulation : le "
                "re-crédit des heures n'est pas encore géré."
            )
        # Restauration AVANT l'écriture du statut : si elle échoue, la demande
        # reste validée et l'annulation peut être rejouée — l'inverse laisse
        # des jours gelés sans recours (retour Gaëlle 03/09, RC de Bugny).
        employee_id = str(req_before["employee_id"])
        type_projete = type_calendrier_projete(str(req_before.get("type") or ""))
        couverts: set[str] = set()
        if type_projete:
            # Requête directe (PAS list_validated_for_employees : elle fusionne
            # les jours du planning en fausses absences, qui couvriraient tous
            # les jours à restaurer). Seule une AUTRE absence projetant le MÊME
            # type de jour possède encore ces cases ; les autres types sont
            # déjà protégés par le contrôle type/origine de la restauration.
            resp = (
                supabase.table("absence_requests")
                .select("id, type, selected_days")
                .eq("employee_id", employee_id)
                .eq("status", "validated")
                .neq("id", request_id)
                .execute()
            )
            for r in resp.data or []:
                if (
                    type_calendrier_projete(str(r.get("type") or ""))
                    != type_projete
                ):
                    continue
                couverts.update(str(d)[:10] for d in r.get("selected_days") or [])
        a_restaurer = [
            date.fromisoformat(str(d)[:10])
            for d in req_before.get("selected_days") or []
            if str(d)[:10] not in couverts
        ]
        if a_restaurer:
            calendar_update_provider.restore_calendar_from_days(
                employee_id, a_restaurer, str(req_before.get("type") or "")
            )

    data = absence_repository.update(request_id, update_dict)
    if not data:
        raise LookupError("Demande introuvable après mise à jour.")

    if status == "validated":
        absence_type = data.get("type", "")
        if absence_type == "recuperation_modulation":
            _apply_modulation_recovery_on_validation(
                data, request_id, precheck=precheck_modulation
            )
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
        if data.get("heures_par_jour"):
            # Repos compensateur pris en heures : la journée reste TRAVAILLÉE
            # au calendrier (le salarié est présent), seul le compteur est
            # débité — aucune projection.
            pass
        else:
            calendar_update_provider.update_calendar_from_days(
                data["employee_id"],
                days_to_update,
                absence_type,
                arret_type=str(arret_type) if arret_type else None,
                subrogation_active=sub_active if isinstance(sub_active, bool) else None,
                nombre_enfants=nombre_enfants,
                historique_arrets_annee=historique or None,
                demi_journees=data.get("demi_journees") or None,
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


# --- Saisie RH directe au calendrier (« une saisie RH enregistre un fait ») ---

#: Marqueur des demandes auto-créées depuis le planning. Il permet de les
#: reconnaître (filtrage, annulation au retypage) — ne jamais l'utiliser pour
#: une demande saisie par un salarié ou par la RH dans le module Absences.
PLANNING_SOURCE_COMMENT = "Saisie RH au calendrier"

#: Seuls types de jour calendrier matérialisables en demande (lot 1 :
#: CP/RTT jour plein). Les arrêts restent au module Absences (arret_type
#: obligatoire, période calendaire réelle, attestation CPAM générée).
_CALENDAR_TO_REQUEST_TYPE = {"conges_payes": "conge_paye", "rtt": "rtt"}


def create_absences_from_planning(
    employee_id: str,
    company_id: str,
    *,
    year: int,
    month: int,
    jours_par_type: dict[str, list[int]],
    photos_avant: dict[str, dict] | None = None,
    aujourd_hui: date | None = None,
) -> list[dict]:
    """Matérialise en demandes VALIDÉES les jours CP/RTT saisis directement
    au calendrier par la RH.

    Une demande PAR JOUR (aucune API ne sait retrancher un jour d'une demande
    existante) ; no-op si une demande validée projette déjà ce type de jour —
    une récup modulation projette aussi ``conges_payes``, créer un CP
    par-dessus double-débiterait ; un jour CP antérieur à la date de reprise
    bulletin (``cp_opening_reference_date``) est laissé au calendrier seul :
    il est déjà dans le solde d'ouverture, une demande le compterait deux
    fois. Retourne des warnings à remonter au planning.
    """
    from app.modules.absences.infrastructure.planning_cp_repository import (
        get_cp_opening_reference_dates,
    )

    warnings: list[dict] = []
    ref_aujourd_hui = aujourd_hui or date.today()
    cutoff = get_cp_opening_reference_dates([employee_id]).get(employee_id)

    validated = (
        supabase.table("absence_requests")
        .select("id, type, selected_days")
        .eq("employee_id", employee_id)
        .eq("status", "validated")
        .execute()
    ).data or []
    couverts_par_type: dict[str, set[str]] = {}
    couverts_tous_types: set[str] = set()
    for r in validated:
        proj = type_calendrier_projete(str(r.get("type") or ""))
        if proj:
            couverts_par_type.setdefault(proj, set()).update(
                str(d)[:10] for d in r.get("selected_days") or []
            )
            couverts_tous_types.update(
                str(d)[:10] for d in r.get("selected_days") or []
            )

    for calendar_type, jours in jours_par_type.items():
        request_type = _CALENDAR_TO_REQUEST_TYPE.get(calendar_type)
        if not request_type:
            continue
        eligibles: list[date] = []
        for jour in sorted(jours):
            day = date(year, month, int(jour))
            iso = day.isoformat()
            if iso in couverts_par_type.get(calendar_type, set()):
                continue  # une demande validée projette déjà ce jour
            if iso in couverts_tous_types:
                # Une demande validée d'un AUTRE type (arrêt, événement
                # familial…) couvre ce jour : matérialiser un CP/RTT
                # par-dessus créerait une double trace (arrêt toujours
                # validé + CP débité). La RH doit d'abord traiter la
                # demande existante dans Gestion des congés.
                warnings.append(
                    {
                        "jour": int(jour),
                        "code": "jour_couvert_par_autre_demande",
                        "detail": (
                            f"Le {day:%d/%m} est couvert par une demande "
                            "validée d'un autre type : annulez-la d'abord "
                            "dans Gestion des congés — aucune demande créée."
                        ),
                    }
                )
                continue
            if request_type == "conge_paye" and cutoff and day <= cutoff:
                warnings.append(
                    {
                        "jour": int(jour),
                        "code": "cp_avant_reprise",
                        "detail": (
                            f"CP du {day:%d/%m} antérieur à la reprise des "
                            f"compteurs ({cutoff:%d/%m/%Y}) : déjà compté dans "
                            "le solde repris, aucune demande créée."
                        ),
                    }
                )
                continue
            eligibles.append(day)

        disponible = 0.0
        if request_type == "conge_paye" and eligibles:
            # Le solde AFFICHÉ décompte DÉJÀ les jours PASSÉS de cette rafale :
            # le mois vient d'être enregistré, ils y figurent en pseudo-CP du
            # planning (count_absence_days_taken s'arrête à AUJOURD'HUI —
            # un jour futur n'est jamais compté comme pris). On ne réintègre
            # donc que les éligibles ≤ aujourd'hui, puis on décrémente
            # localement : sans quoi la dernière journée passée d'un solde
            # juste serait payée 0, et un CP posé pour demain à solde nul
            # serait payé 1.
            deja_decomptes = sum(1 for d in eligibles if d <= ref_aujourd_hui)
            disponible = float(get_cp_solde_restant(employee_id)) + deja_decomptes

        for day in eligibles:
            iso = day.isoformat()
            jour = day.day
            db_data: dict[str, Any] = {
                "employee_id": employee_id,
                "company_id": company_id,
                "type": request_type,
                "status": "validated",
                "workflow_step": "approved_rh",
                "selected_days": [iso],
                "comment": f"{PLANNING_SOURCE_COMMENT} ({day:%d/%m/%Y})",
            }
            if request_type == "conge_paye":
                # Même règle qu'à la validation RH : payé par pas de 0,5 dans
                # la limite du solde, le dépassement devient du sans-solde.
                payable = max(0.0, math.floor(disponible * 2) / 2)
                db_data["jours_payes"] = min(1.0, payable)
                disponible -= 1.0
                if db_data["jours_payes"] < 1.0:
                    warnings.append(
                        {
                            "jour": int(jour),
                            "code": "cp_au_dela_du_solde",
                            "detail": (
                                f"CP du {day:%d/%m} posé au-delà du solde : "
                                f"{db_data['jours_payes']:.1f} j payé(s) sur 1."
                            ),
                        }
                    )
            created = absence_repository.create(db_data)
            couverts_par_type.setdefault(calendar_type, set()).add(iso)
            try:
                calendar_update_provider.update_calendar_from_days(
                    employee_id,
                    [day],
                    request_type,
                    adopter_jours_deja_types=True,
                    photos_avant=photos_avant or None,
                )
            except Exception:
                logger.exception(
                    "Projection calendrier de la demande planning %s échouée",
                    created.get("id"),
                )
            warnings.append(
                {
                    "jour": int(jour),
                    "code": "demande_creee_depuis_planning",
                    "type": request_type,
                }
            )
    return warnings


def cancel_planning_absences_for_requalified_days(
    employee_id: str,
    *,
    year: int,
    month: int,
    requalifications: list[dict],
) -> list[dict]:
    """Annule les demandes AUTO-CRÉÉES depuis le planning quand la RH retype
    leur jour (congé → travail…).

    Ne touche jamais une demande saisie par le salarié ou par la RH dans le
    module Absences (marqueur absent), ni une demande multi-jours : dans ces
    cas le warning de requalification alerte, la demande se traite dans
    Absences. La restauration de l'annulation est neutre : la RH vient de
    retyper le jour et la fusion a purgé ``origine`` — le garde-fou de
    ``restore_calendar_from_days`` la saute.
    """
    warnings: list[dict] = []
    jours_par_type_avant: dict[str, list[int]] = {}
    for w in requalifications:
        if w.get("code") != "absence_validee_requalifiee":
            continue
        t_avant = w.get("type_avant")
        if t_avant in _CALENDAR_TO_REQUEST_TYPE:
            jours_par_type_avant.setdefault(t_avant, []).append(int(w["jour"]))
    if not jours_par_type_avant:
        return warnings

    validated = (
        supabase.table("absence_requests")
        .select("id, type, selected_days, comment")
        .eq("employee_id", employee_id)
        .eq("status", "validated")
        .execute()
    ).data or []

    for calendar_type, jours in jours_par_type_avant.items():
        request_type = _CALENDAR_TO_REQUEST_TYPE[calendar_type]
        for jour in jours:
            iso = date(year, month, int(jour)).isoformat()
            for r in validated:
                if r.get("type") != request_type:
                    continue
                days = [str(d)[:10] for d in r.get("selected_days") or []]
                if days != [iso]:
                    continue  # jamais rétrécir une demande multi-jours
                if not str(r.get("comment") or "").startswith(
                    PLANNING_SOURCE_COMMENT
                ):
                    continue
                try:
                    update_absence_request_status(str(r["id"]), "cancelled")
                    warnings.append(
                        {
                            "jour": int(jour),
                            "code": "demande_planning_annulee",
                            "type": request_type,
                        }
                    )
                except Exception:
                    logger.exception(
                        "Annulation de la demande planning %s échouée",
                        r.get("id"),
                    )
                break
    return warnings
