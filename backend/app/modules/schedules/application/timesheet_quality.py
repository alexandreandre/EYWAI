"""
Contrôles qualité automatiques pour les propositions d'import de pointages.
"""

from __future__ import annotations

from typing import List, Literal, Set

from app.modules.schedules.schemas.ai import (
    AiEmployeeProposal,
    RosterEmployee,
    TimesheetQualityCheck,
)

QualityLevel = Literal["ok", "warning", "error", "info"]

WEEKLY_TOTAL_TOLERANCE_OK = 0.25
WEEKLY_TOTAL_TOLERANCE_WARN = 1.0
COVERAGE_INCOMPLETE_THRESHOLD = 0.6


def _sum_hours(days: List) -> float:
    total = 0.0
    for d in days:
        if d.heures is not None and d.heures > 0:
            total += d.heures
    return round(total, 2)


def compute_employee_weekly_totals(proposal: AiEmployeeProposal) -> AiEmployeeProposal:
    imported = _sum_hours(proposal.days)
    proposal.weekly_total_imported = imported
    if proposal.weekly_total_pdf is not None:
        proposal.weekly_total_gap = round(
            abs(proposal.weekly_total_pdf - imported), 2
        )
    return proposal


def _is_extraction_incomplete(proposal: AiEmployeeProposal) -> bool:
    expected = proposal.days_expected_count or 0
    imported = proposal.days_imported_count
    if imported is None:
        imported = len(
            [d for d in proposal.days if d.heures is not None and d.heures > 0]
        )

    if expected > 0 and imported < expected:
        return True

    coverage = proposal.coverage_ratio
    gap = proposal.weekly_total_gap or 0.0
    if coverage is not None and coverage < 1.0 and gap > WEEKLY_TOTAL_TOLERANCE_WARN:
        return True

    return False


def _is_match_doubtful(proposal: AiEmployeeProposal) -> bool:
    return (
        proposal.match_confidence == "medium"
        and proposal.employee_id is not None
    )


def _apply_review_status_rules(proposal: AiEmployeeProposal) -> AiEmployeeProposal:
    """Statuts distincts : extraction incomplète vs écart heures vs match douteux."""
    if proposal.review_status in ("error", "empty"):
        proposal.quality_issue = None
        return proposal

    if not proposal.employee_id:
        proposal.review_status = "error"
        proposal.quality_issue = None
        return proposal

    if _is_match_doubtful(proposal):
        proposal.review_status = "warning"
        proposal.quality_issue = "match_doubtful"
        return proposal

    if _is_extraction_incomplete(proposal):
        proposal.review_status = "warning"
        proposal.quality_issue = "extraction_incomplete"
        return proposal

    gap = proposal.weekly_total_gap
    if gap is not None and gap > WEEKLY_TOTAL_TOLERANCE_OK:
        proposal.review_status = "warning"
        proposal.quality_issue = "weekly_total_gap"
        return proposal

    proposal.review_status = "ok"
    proposal.quality_issue = None
    return proposal


def quality_checks_for_employee(proposal: AiEmployeeProposal) -> List[TimesheetQualityCheck]:
    checks: List[TimesheetQualityCheck] = []
    name = proposal.raw_name
    mat = proposal.time_tracking_id

    if proposal.review_status == "empty":
        checks.append(
            TimesheetQualityCheck(
                level="info",
                code="empty_week",
                message=f"{name} : semaine sans pointage (0 h).",
                employee_raw_name=name,
                matricule=mat,
            )
        )
        return checks

    if proposal.review_status == "error" or proposal.match_confidence == "none":
        if proposal.match_method == "matricule" and mat:
            checks.append(
                TimesheetQualityCheck(
                    level="error",
                    code="matricule_unmatched",
                    message=f"Matricule {mat} ({name}) : aucun salarié EYWAI correspondant.",
                    employee_raw_name=name,
                    matricule=mat,
                )
            )
        else:
            checks.append(
                TimesheetQualityCheck(
                    level="error",
                    code="employee_unmatched",
                    message=f"« {name} » : salarié non identifié — associez manuellement.",
                    employee_raw_name=name,
                    matricule=mat,
                )
            )

    if proposal.quality_issue == "match_doubtful":
        checks.append(
            TimesheetQualityCheck(
                level="warning",
                code="match_doubtful",
                message=f"« {name} » : correspondance à confirmer.",
                employee_raw_name=name,
                matricule=mat,
            )
        )

    if proposal.quality_issue == "extraction_incomplete":
        expected = proposal.days_expected_count or "?"
        imported = proposal.days_imported_count or len(proposal.days)
        checks.append(
            TimesheetQualityCheck(
                level="warning",
                code="extraction_incomplete",
                message=(
                    f"{name} : extraction incomplète ({imported}/{expected} jours lus) — "
                    "complétez au planning si besoin."
                ),
                employee_raw_name=name,
                matricule=mat,
            )
        )

    if proposal.weekly_total_pdf is not None:
        gap = proposal.weekly_total_gap or 0.0
        if gap <= WEEKLY_TOTAL_TOLERANCE_OK:
            checks.append(
                TimesheetQualityCheck(
                    level="ok",
                    code="weekly_total_ok",
                    message=(
                        f"{name} : total hebdo cohérent "
                        f"(PDF {proposal.weekly_total_pdf:.2f} h, "
                        f"import {_sum_hours(proposal.days):.2f} h)."
                    ),
                    employee_raw_name=name,
                    matricule=mat,
                )
            )
        elif proposal.quality_issue == "weekly_total_gap":
            if gap <= WEEKLY_TOTAL_TOLERANCE_WARN:
                checks.append(
                    TimesheetQualityCheck(
                        level="warning",
                        code="weekly_total_gap",
                        message=(
                            f"{name} : écart total hebdo {gap:.2f} h "
                            f"(PDF {proposal.weekly_total_pdf:.2f} h vs "
                            f"import {_sum_hours(proposal.days):.2f} h)."
                        ),
                        employee_raw_name=name,
                        matricule=mat,
                    )
                )
            else:
                checks.append(
                    TimesheetQualityCheck(
                        level="warning",
                        code="weekly_total_gap_high",
                        message=(
                            f"{name} : écart total hebdo important ({gap:.2f} h) — "
                            "vérifiez les heures jour par jour."
                        ),
                        employee_raw_name=name,
                        matricule=mat,
                    )
                )

    if proposal.weekly_total_pdf and proposal.weekly_total_pdf > 0 and not proposal.days:
        checks.append(
            TimesheetQualityCheck(
                level="error",
                code="no_days_with_total",
                message=f"{name} : total PDF > 0 mais aucun jour importé.",
                employee_raw_name=name,
                matricule=mat,
            )
        )

    return checks


def build_global_quality_checks(
    employees: List[AiEmployeeProposal],
    roster: List[RosterEmployee],
    *,
    parse_confidence: float | None = None,
    detected_format: str | None = None,
) -> tuple[List[TimesheetQualityCheck], int]:
    """Contrôles globaux + compte salariés roster absents du PDF."""
    checks: List[TimesheetQualityCheck] = []
    pdf_employee_ids: Set[str] = {
        e.employee_id for e in employees if e.employee_id
    }
    pdf_matricules = {
        (e.time_tracking_id or "").strip()
        for e in employees
        if (e.time_tracking_id or "").strip()
    }

    roster_not_in_doc = 0
    for emp in roster:
        tid = (emp.time_tracking_id or "").strip()
        if emp.id in pdf_employee_ids:
            continue
        if tid and tid in pdf_matricules:
            continue
        roster_not_in_doc += 1

    if roster_not_in_doc > 0:
        checks.append(
            TimesheetQualityCheck(
                level="info",
                code="roster_not_in_document",
                message=(
                    f"{roster_not_in_doc} salarié(s) actif(s) hors relevé "
                    "(normal pour un import hebdomadaire partiel)."
                ),
            )
        )

    unknown_matricules = [
        e for e in employees
        if (e.time_tracking_id or "").strip()
        and e.review_status == "error"
        and e.match_method in ("matricule", "none")
    ]
    for emp in unknown_matricules:
        if emp.time_tracking_id and not any(
            c.code == "matricule_unmatched" and c.matricule == emp.time_tracking_id
            for c in checks
        ):
            checks.append(
                TimesheetQualityCheck(
                    level="warning",
                    code="pdf_unknown_matricule",
                    message=(
                        f"Matricule {emp.time_tracking_id} ({emp.raw_name}) "
                        "absent du roster EYWAI."
                    ),
                    employee_raw_name=emp.raw_name,
                    matricule=emp.time_tracking_id,
                )
            )

    if detected_format == "cegid_weekly" and parse_confidence is not None:
        if parse_confidence < 0.5:
            checks.append(
                TimesheetQualityCheck(
                    level="warning",
                    code="parse_confidence_low",
                    message=(
                        "Qualité OCR faible — vérifiez attentivement ou "
                        "réessayez avec un scan plus net."
                    ),
                )
            )

    return checks, roster_not_in_doc


def run_quality_checks(
    employees: List[AiEmployeeProposal],
    roster: List[RosterEmployee],
    *,
    parse_confidence: float | None = None,
    detected_format: str | None = None,
) -> tuple[List[AiEmployeeProposal], List[TimesheetQualityCheck], int]:
    updated: List[AiEmployeeProposal] = []
    all_checks: List[TimesheetQualityCheck] = []

    for emp in employees:
        emp = compute_employee_weekly_totals(emp)
        emp = _apply_review_status_rules(emp)
        all_checks.extend(quality_checks_for_employee(emp))
        updated.append(emp)

    global_checks, roster_not_in_doc = build_global_quality_checks(
        updated,
        roster,
        parse_confidence=parse_confidence,
        detected_format=detected_format,
    )
    all_checks = global_checks + all_checks
    return updated, all_checks, roster_not_in_doc


def average_coverage(employees: List[AiEmployeeProposal]) -> float | None:
    ratios = [
        e.coverage_ratio
        for e in employees
        if e.coverage_ratio is not None and e.review_status != "empty"
    ]
    if not ratios:
        return None
    return round(sum(ratios) / len(ratios), 3)


__all__ = [
    "average_coverage",
    "run_quality_checks",
    "quality_checks_for_employee",
    "COVERAGE_INCOMPLETE_THRESHOLD",
]
