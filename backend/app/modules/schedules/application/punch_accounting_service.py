"""Service application — comptabilisation pointages sur propositions et badgeuse."""

from __future__ import annotations

import hashlib
from datetime import date
from typing import Any, List

from app.modules.schedules.domain.punch_accounting_entities import (
    PlannedShiftBreak,
    PunchDayInput,
)
from app.modules.schedules.domain.punch_accounting_rules import (
    compute_from_raw_times,
    compute_punch_day,
    minutes_to_time_string,
    parse_hhmm_value,
)
from app.modules.schedules.infrastructure import punch_accounting_repository as repo
from app.modules.schedules.schemas.ai import (
    AiCalendarProposalResponse,
    AiDayEntry,
    AiEmployeeProposal,
    TimesheetQualityCheck,
)


# Version des règles de calcul des heures pointées. À incrémenter dès qu'un
# même relevé peut donner des heures différentes — les aperçus mis en cache
# sous une version antérieure sont alors ignorés.
#   2 : pause des feuilles importées alignée sur le paramétrage société.
PUNCH_CALC_RULES_VERSION = 3  # lot 4 : pauses brutes sur imports (prompt + repli supprimé)


def punch_calc_fingerprint(company_id: str | None) -> str:
    """Empreinte des règles qui ont produit des heures, cache d'aperçu compris."""
    parts: List[str] = [f"v{PUNCH_CALC_RULES_VERSION}"]
    if not company_id:
        return ":".join(parts + ["no-company"])

    settings = repo.get_settings(company_id)
    parts.append(
        "|".join(
            str(v)
            for v in (
                settings.enabled,
                settings.tolerance_minutes,
                settings.default_break_deduct_minutes,
                settings.break_threshold_minutes,
                settings.slot_detection,
                settings.within_tolerance_pay_theoretical,
                settings.require_manager_validation_for_overtime,
            )
        )
    )
    if settings.enabled:
        slots = "|".join(
            f"{s.code}-{s.entry_minutes}-{s.exit_minutes}-{s.break_deduct_minutes}"
            f"-{s.paid_break_minutes}-{s.paid_lunch_break}"
            for s in sorted(repo.list_slots(company_id), key=lambda s: s.sort_order)
        )
        parts.append(hashlib.sha1(slots.encode()).hexdigest()[:12])
    return ":".join(parts)


def _resolve_exit_raw(row: dict[str, Any], use_last: bool) -> object:
    exit_last = row.get("exit_last") or row.get("sortie_3") or row.get("exit_3")
    if parse_hhmm_value(exit_last):
        return exit_last
    if not use_last:
        return exit_last
    for key in ("sortie_2", "exit_2", "sortie_1", "exit_1"):
        val = row.get(key)
        if parse_hhmm_value(val):
            return val
    return exit_last


def apply_punch_accounting_to_proposal(
    proposal: AiCalendarProposalResponse,
    company_id: str,
) -> AiCalendarProposalResponse:
    settings = repo.get_settings(company_id)
    if not settings.enabled:
        return proposal

    # Absence de créneau volontaire chez les sociétés à horaires variables :
    # la pause s'y résout par le seuil de présence, pas par une grille, et le
    # théorique de la journée vaut le pointé.
    slots = repo.list_slots(company_id)

    quality_checks: List[TimesheetQualityCheck] = list(proposal.quality_checks)
    employees_out: List[AiEmployeeProposal] = []

    for emp in proposal.employees:
        new_days: List[AiDayEntry] = []
        warnings = list(emp.warnings)
        for day in emp.days:
            entry_raw = day.punch_entry_raw
            exit_raw = day.punch_exit_raw
            shift_code = day.shift_code

            if entry_raw is None and exit_raw is None and (
                day.heures is not None or not slots
            ):
                # Rien à recomptabiliser : soit les heures sont déjà là, soit,
                # sans grille horaire, la journée ne porte aucun élément à
                # confronter — l'inventer en absence effacerait une saisie.
                new_days.append(day)
                continue

            result = compute_from_raw_times(
                entry_raw=entry_raw,
                exit_raw=exit_raw,
                shift_code=shift_code,
                settings=settings,
                slots=slots,
                planned_shift=(
                    PlannedShiftBreak(paid_break_minutes=day.planned_paid_break_minutes)
                    if day.planned_paid_break_minutes
                    else None
                ),
                punched_break_minutes=day.punch_break_minutes,
            )

            if result.is_absent or result.is_incomplete:
                # Sans badge, ou avec un seul : le jour reste VIDE, à compléter
                # par la RH (heures, ou case « absent » puis son type). Une
                # « absence » à 0 h faisait retenir une absence injustifiée
                # dès qu'on forçait la paie.
                for alert in result.alerts:
                    warnings.append(f"Jour {day.jour} : {alert}")
                    quality_checks.append(
                        TimesheetQualityCheck(
                            level="warning",
                            code="punch_incomplete",
                            message=f"Jour {day.jour} : {alert}",
                            employee_raw_name=emp.raw_name,
                            matricule=emp.time_tracking_id,
                        )
                    )
                new_days.append(day.model_copy(update={"heures": None}))
                continue

            for alert in result.alerts:
                warnings.append(f"Jour {day.jour} : {alert}")
                quality_checks.append(
                    TimesheetQualityCheck(
                        level="warning",
                        code="punch_overtime_review",
                        message=f"Jour {day.jour} : {alert}",
                        employee_raw_name=emp.raw_name,
                        matricule=emp.time_tracking_id,
                    )
                )

            heures_jour = result.accounted_hours
            notes: dict[str, Any] = {}
            if result.needs_review and emp.employee_id:
                motif = result.overtime_reason or "daily_excess"
                notes = {
                    "heures_en_plus_a_valider": round(result.overtime_hours, 2),
                    "motif_heures_en_plus": motif,
                    "creneau_applique_id": result.applied_slot_id,
                }
                # Aperçu en lecture seule : la revue « en attente » ne naît qu'à
                # l'enregistrement (enregistrer_heures_en_plus_a_valider). Une
                # décision déjà APPROUVÉE pour le même excédent reste effective
                # au ré-import, comme le garde upsert_overtime_review.
                work_date = date(
                    day.year or proposal.year, day.month or proposal.month, day.jour
                )
                existante = repo.get_overtime_review(emp.employee_id, work_date)
                if _decision_approuvee_au_meme_contenu(
                    existante, result.overtime_hours, motif
                ):
                    heures_jour = round(heures_jour + result.overtime_hours, 2)

            new_days.append(day.model_copy(update={"heures": heures_jour, **notes}))

        employees_out.append(emp.model_copy(update={"days": new_days, "warnings": warnings}))

    return proposal.model_copy(
        update={"employees": employees_out, "quality_checks": quality_checks}
    )


def _decision_approuvee_au_meme_contenu(
    revue: dict[str, Any] | None, heures: float, motif: str
) -> bool:
    if not revue or str(revue.get("status") or "") != "approved":
        return False
    return round(float(revue.get("overtime_hours") or 0), 2) == round(heures, 2) and str(
        revue.get("reason") or ""
    ) == str(motif or "")


def enregistrer_heures_en_plus_a_valider(
    company_id: str,
    year: int,
    month: int,
    employees: List[Any],
) -> int:
    """Crée (ou met à jour) la revue « en attente » de chaque jour enregistré
    qui porte des heures en plus notées à l'aperçu. Un jour retypé à la
    relecture (congé, absence…) ou seulement prévu n'en crée pas."""
    n = 0
    for emp in employees:
        if not getattr(emp, "employee_id", None):
            continue
        for day in emp.days:
            heures = day.heures_en_plus_a_valider or 0
            if day.nature != "reel" or day.type != "travail" or heures <= 0:
                continue
            entree = parse_hhmm_value(day.punch_entry_raw)
            sortie = parse_hhmm_value(day.punch_exit_raw)
            repo.upsert_overtime_review(
                company_id,
                employee_id=emp.employee_id,
                work_date=date(day.year or year, day.month or month, day.jour),
                overtime_hours=heures,
                reason=day.motif_heures_en_plus or "daily_excess",
                raw_entry_time=minutes_to_time_string(entree) if entree else None,
                raw_exit_time=minutes_to_time_string(sortie) if sortie else None,
                applied_slot_id=day.creneau_applique_id,
                status="pending",
            )
            n += 1
    return n


def compute_accounted_hours_for_badgeuse_day(
    company_id: str,
    *,
    entry_minutes: int | None,
    exit_minutes: int | None,
    shift_code: str | None = None,
    planned_paid_break_minutes: int = 0,
    planned_unpaid_break_minutes: int | None = None,
    measured_break_minutes: int | None = None,
) -> tuple[float, bool, float, str | None]:
    """Retourne (heures_comptabilisées, needs_review, overtime_hours, reason)."""
    settings = repo.get_settings(company_id)
    if not settings.enabled:
        if entry_minutes and exit_minutes and exit_minutes > entry_minutes:
            gross = exit_minutes - entry_minutes
            return round(gross / 60.0, 2), False, 0.0, None
        return 0.0, False, 0.0, None

    slots = repo.list_slots(company_id)
    planned_shift: PlannedShiftBreak | None = None
    if (
        planned_unpaid_break_minutes is not None
        or shift_code
        or planned_paid_break_minutes > 0
    ):
        planned_shift = PlannedShiftBreak(
            paid_break_minutes=max(0, int(planned_paid_break_minutes or 0)),
            unpaid_break_minutes=planned_unpaid_break_minutes,
            slot_code=shift_code,
        )
    elif planned_paid_break_minutes > 0:
        planned_shift = PlannedShiftBreak(paid_break_minutes=planned_paid_break_minutes)

    result = compute_punch_day(
        PunchDayInput(
            entry_minutes=entry_minutes,
            exit_minutes=exit_minutes,
            shift_code=shift_code,
            planned_shift=planned_shift,
            measured_break_minutes=measured_break_minutes,
        ),
        settings,
        slots,
    )
    return (
        result.accounted_hours,
        result.needs_review,
        result.overtime_hours,
        result.overtime_reason,
    )


