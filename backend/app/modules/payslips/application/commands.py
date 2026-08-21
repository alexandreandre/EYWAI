"""
Commandes (use cases en écriture) du module payslips.

Logique applicative : décision forfait jour vs heures, délégation aux providers
(services legacy). Les routers n'appellent que ces commandes.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from app.core.database import supabase
from app.modules.employees.infrastructure.repository import EmployeeRepository
from app.modules.onboarding.domain.profile import payroll_block_reason
from app.modules.payslips.application.dto import (
    EditPayslipInput,
    GeneratePayslipInput,
    GeneratePayslipResult,
    PayslipBadRequestError,
    PayslipCalendarIncompleteError,
    PayslipValidatedError,
    PayslipNotFoundError,
    RestorePayslipInput,
)
from app.modules.payslips.domain.rules import is_forfait_jour
from app.modules.payslips.infrastructure.providers import (
    payslip_editor_provider,
    payslip_generator_provider,
)
from app.modules.payslips.infrastructure.readers import employee_statut_reader
from app.modules.notifications.application.employee_document_alerts import (
    NOTIFICATION_TYPE_PAYSLIP,
    notify_employee_new_document,
)
from app.modules.employees.application.service import enrich_employee_with_exit_context
from app.shared.domain.employment_rules import payslip_employment_period_block_reason

_employee_repository = EmployeeRepository()
logger = logging.getLogger(__name__)

_PAYSLIP_MONTH_LABELS = (
    "janvier",
    "février",
    "mars",
    "avril",
    "mai",
    "juin",
    "juillet",
    "août",
    "septembre",
    "octobre",
    "novembre",
    "décembre",
)


def _payslip_notification_label(year: int, month: int) -> str:
    if 1 <= month <= 12:
        return f"Bulletin de paie — {_PAYSLIP_MONTH_LABELS[month - 1]} {year}"
    return f"Bulletin de paie — {month:02d}/{year}"


def _notify_payslip_available(
    employee_id: str,
    company_id: str,
    year: int,
    month: int,
) -> bool:
    """Notifie le salarié ; renvoie False en cas d'échec (l'appelant décide
    s'il pose le marqueur d'idempotence — jamais sur un échec, sinon le
    salarié n'est jamais notifié et jamais re-tenté)."""
    try:
        notify_employee_new_document(
            employee_id,
            company_id,
            _payslip_notification_label(year, month),
            page_path="payslips",
            notification_type=NOTIFICATION_TYPE_PAYSLIP,
        )
        return True
    except Exception as exc:
        logger.warning(
            "[doc_notif] Bulletin non notifié pour %s (%02d/%d): %s",
            employee_id,
            month,
            year,
            exc,
        )
        return False


def _fetch_month_schedule(
    company_id: str, employee_id: str, year: int, month: int
) -> dict[str, Any] | None:
    """Ligne employee_schedules (planned_calendar, actual_hours) du mois, ou None."""
    from app.core.database import supabase

    r = (
        supabase.table("employee_schedules")
        .select("planned_calendar, actual_hours")
        .eq("company_id", company_id)
        .eq("employee_id", employee_id)
        .eq("year", year)
        .eq("month", month)
        .maybe_single()
        .execute()
    )
    return r.data if r else None


def _calendar_row_status(employee: dict[str, Any], year: int, month: int) -> str:
    """Complétude du calendrier du mois — même règle que la revue pré-paie
    (`compute_row_status`) : `a_saisir` | `saisi` | `saisi_avec_ecart`."""
    from app.modules.schedules.domain.ecart_rules import compute_row_status
    from app.shared.domain.employment_rules import (
        is_forfait_jour as _is_forfait_jour_flag,
    )

    company_id = str(employee.get("company_id") or "").strip()
    sched = (
        _fetch_month_schedule(company_id, str(employee.get("id") or ""), year, month)
        or {}
    )
    planned_raw = sched.get("planned_calendar") or {}
    actual_raw = sched.get("actual_hours") or {}
    planned_days = (
        planned_raw.get("calendrier_prevu", []) if isinstance(planned_raw, dict) else []
    )
    actual_days = (
        actual_raw.get("calendrier_reel", []) if isinstance(actual_raw, dict) else []
    )
    forfait = _is_forfait_jour_flag(
        employee.get("statut"), employee.get("is_forfait_jour")
    )
    return compute_row_status(planned_days, actual_days, year, month, forfait)


def _check_calendar_guard(
    employee: dict[str, Any], cmd: GeneratePayslipInput
) -> dict[str, Any] | None:
    """Garde « calendrier manquant/incomplet ».

    Refuse (422) si le mois est `a_saisir`, sauf override explicite
    `force_calendrier_incomplet` — alors trace l'auteur et retourne le
    warning à joindre à la réponse. Retourne None si le mois est complet.
    """
    row_status = _calendar_row_status(employee, cmd.year, cmd.month)
    if row_status != "a_saisir":
        return None
    message = (
        f"Calendrier {cmd.month:02d}/{cmd.year} incomplet pour cet employé : "
        "des heures planifiées ou réelles manquent. Complétez le calendrier "
        "avant de générer, ou forcez explicitement la génération."
    )
    if not cmd.force_calendrier_incomplet:
        raise PayslipCalendarIncompleteError(message)
    logger.warning(
        "[generation] Calendrier %02d/%d incomplet pour l'employé %s : "
        "génération FORCÉE par %s (%s).",
        cmd.month,
        cmd.year,
        cmd.employee_id,
        cmd.requested_by or "inconnu",
        cmd.requested_by_name or "nom inconnu",
    )
    return {
        "code": "calendrier_incomplet_force",
        "message": (
            f"Généré malgré un calendrier {cmd.month:02d}/{cmd.year} incomplet "
            "(forçage explicite)."
        ),
    }


def _fetch_existing_payslip(
    employee_id: str, year: int, month: int
) -> dict[str, Any] | None:
    """Bulletin existant de la période (statut + contenu), None sinon."""
    r = (
        supabase.table("payslips")
        .select("id, status, payslip_data, url, edit_history")
        .match({"employee_id": employee_id, "year": year, "month": month})
        .maybe_single()
        .execute()
    )
    return r.data if r and r.data else None


def _archive_before_regeneration(
    existing: dict[str, Any], cmd: GeneratePayslipInput
) -> None:
    """Archive le bulletin validé AVANT que le générateur ne l'écrase.

    Même format que l'historique d'édition manuelle (payslip_editor) : la
    version précédente reste consultable et restaurable.
    """
    history = existing.get("edit_history") or []
    if not isinstance(history, list):
        history = []
    history.append(
        {
            "version": len(history) + 1,
            "edited_at": datetime.now().isoformat(),
            "edited_by": cmd.requested_by,
            "edited_by_name": cmd.requested_by_name,
            "changes_summary": "Régénération d'un bulletin validé (forçage explicite)",
            "action": "regeneration",
            "previous_payslip_data": existing.get("payslip_data", {}),
            "previous_pdf_url": existing.get("url"),
        }
    )
    supabase.table("payslips").update({"edit_history": history}).eq(
        "id", existing["id"]
    ).execute()


def _reset_payslip_flags_after_regeneration(payslip_id: str) -> None:
    """Après régénération forcée : le bulletin redevient un brouillon.

    Le statut « valide » portait sur l'ANCIEN contenu ; les acquittements
    d'alertes vivent dans payslip_data et sont déjà balayés par l'upsert du
    générateur. manually_edited est remis à False : les retouches manuelles
    ont été archivées, pas conservées.
    """
    supabase.table("payslips").update(
        {"status": "brouillon", "manually_edited": False}
    ).eq("id", payslip_id).execute()


def _check_validated_guard(
    cmd: GeneratePayslipInput,
) -> dict[str, Any] | None:
    """Garde « bulletin validé » : refuse (409) sauf forçage explicite.

    Retourne le bulletin existant si une régénération forcée est en cours
    (l'appelant doit archiver avant, réinitialiser après), None sinon.
    """
    existing = _fetch_existing_payslip(cmd.employee_id, cmd.year, cmd.month)
    if not existing or existing.get("status") != "valide":
        return None
    if not cmd.regenerer_bulletin_valide:
        raise PayslipValidatedError(
            f"Un bulletin validé existe déjà pour {cmd.month:02d}/{cmd.year}. "
            "Le régénérer archivera la version validée et exigera une "
            "nouvelle validation."
        )
    logger.warning(
        "[generation] Bulletin validé %s (%02d/%d) régénéré par %s (%s) : "
        "version archivée, statut remis à brouillon.",
        existing.get("id"),
        cmd.month,
        cmd.year,
        cmd.requested_by or "inconnu",
        cmd.requested_by_name or "nom inconnu",
    )
    return existing


def generate_payslip(cmd: GeneratePayslipInput) -> GeneratePayslipResult:
    """
    Génère un bulletin pour un employé / période.
    Logique applicative : récupère le statut employé (via port), choisit forfait jour ou heures,
    délègue au provider (services legacy).

    Gardes (lot 3 — génération sûre), côté serveur, jamais dans les générateurs :
    - calendrier du mois `a_saisir` → PayslipCalendarIncompleteError (422),
      sauf `force_calendrier_incomplet` explicite (tracé, warning en réponse).
    """
    employee = _employee_repository.get_by_id_only(cmd.employee_id)
    if not employee:
        raise PayslipNotFoundError("Employé non trouvé.")
    block_reason = payroll_block_reason(employee)
    if block_reason:
        raise PayslipBadRequestError(block_reason)
    employee = enrich_employee_with_exit_context(employee)
    period_block_reason = payslip_employment_period_block_reason(
        employee, cmd.year, cmd.month
    )
    if period_block_reason:
        raise PayslipBadRequestError(period_block_reason)

    calendar_warning = _check_calendar_guard(employee, cmd)
    validated_existing = _check_validated_guard(cmd)
    if validated_existing:
        _archive_before_regeneration(validated_existing, cmd)

    statut = employee_statut_reader.get_employee_statut(cmd.employee_id)
    if is_forfait_jour(statut):
        result = payslip_generator_provider.generate_forfait(
            employee_id=cmd.employee_id,
            year=cmd.year,
            month=cmd.month,
        )
    else:
        result = payslip_generator_provider.generate_heures(
            employee_id=cmd.employee_id,
            year=cmd.year,
            month=cmd.month,
        )

    # Lot 3 : plus AUCUNE notification à la génération — le salarié n'est
    # prévenu qu'à la VALIDATION du bulletin (comparison_service), une fois.

    warnings: list[Any] = list(result.get("warnings") or [])
    if calendar_warning:
        warnings.append(calendar_warning)
    if validated_existing and str(result.get("status") or "") == "success":
        _reset_payslip_flags_after_regeneration(str(validated_existing["id"]))
        warnings.append(
            {
                "code": "bulletin_valide_regenere",
                "message": (
                    f"Le bulletin validé de {cmd.month:02d}/{cmd.year} a été "
                    "régénéré : ancienne version archivée, nouvelle version en "
                    "brouillon à revalider."
                ),
            }
        )

    return GeneratePayslipResult(
        status=result["status"],
        message=result["message"],
        download_url=result["download_url"],
        payslip_id=result.get("payslip_id"),
        warnings=warnings or None,
    )


def delete_payslip(payslip_id: str) -> None:
    """
    Supprime un bulletin (BDD + storage) et déclenche recalc COR.
    Délègue au repository (wrapper legacy ou implémentation future).
    """
    from app.modules.payslips.infrastructure.repository import payslip_repository

    payslip_repository.delete(payslip_id)


def edit_payslip(cmd: EditPayslipInput) -> dict[str, Any]:
    """Sauvegarde les modifications d'un bulletin. Délègue au provider legacy."""
    return payslip_editor_provider.save_edited(
        payslip_id=cmd.payslip_id,
        new_payslip_data=cmd.payslip_data,
        changes_summary=cmd.changes_summary,
        current_user_id=cmd.current_user_id,
        current_user_name=cmd.current_user_name,
        pdf_notes=cmd.pdf_notes,
        internal_note=cmd.internal_note,
    )


def restore_payslip_version(cmd: RestorePayslipInput) -> dict[str, Any]:
    """Restaure une version d'un bulletin. Délègue au provider legacy."""
    return payslip_editor_provider.restore_version(
        payslip_id=cmd.payslip_id,
        version=cmd.version,
        current_user_id=cmd.current_user_id,
        current_user_name=cmd.current_user_name,
    )
