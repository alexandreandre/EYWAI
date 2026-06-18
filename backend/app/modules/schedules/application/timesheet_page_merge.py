"""Fusion multi-pages des extractions hybrides de relevés de pointages."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.modules.schedules.application.employee_match import (
    _normalize_matricule,
    is_junk_employee_name,
)
from app.modules.schedules.application.timesheet_page_consensus import (
    PageEmployee,
    PageExtractionResult,
)


@dataclass
class MergedEmployee:
    raw_name: str
    matricule: str | None = None
    weekly_total_pdf: float | None = None
    days: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    pages_seen: list[int] = field(default_factory=list)
    confidence: float = 0.5


@dataclass
class MergedExtractionResult:
    employees: list[MergedEmployee] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    conflicts_count: int = 0
    confidence: float = 0.0
    page_period_hints: list[str] = field(default_factory=list)
    pages_processed: int = 0


def _merge_key(emp: PageEmployee) -> str:
    mat = _normalize_matricule(emp.matricule)
    if mat:
        return f"mat:{mat}"
    return f"name:{(emp.raw_name or '').strip().lower()}"


def _merge_day_lists(
    existing: list[dict[str, Any]],
    incoming: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], int]:
    conflicts = 0
    by_jour: dict[int, dict[str, Any]] = {
        int(d["jour"]): dict(d) for d in existing if d.get("jour") is not None
    }
    for day in incoming:
        try:
            jour = int(day.get("jour"))
        except (TypeError, ValueError):
            continue
        new_hours = day.get("heures")
        if jour in by_jour:
            old_hours = by_jour[jour].get("heures")
            if old_hours is not None and new_hours is not None:
                try:
                    if abs(float(old_hours) - float(new_hours)) > 0.5:
                        conflicts += 1
                        if float(new_hours) > float(old_hours):
                            by_jour[jour] = dict(day)
                        continue
                except (TypeError, ValueError):
                    pass
        else:
            by_jour[jour] = dict(day)
    return sorted(by_jour.values(), key=lambda d: int(d["jour"])), conflicts


def merge_page_results(
    page_results: list[PageExtractionResult],
) -> MergedExtractionResult:
    """Agrège les salariés extraits page par page."""
    merged: dict[str, MergedEmployee] = {}
    global_warnings: list[str] = []
    conflicts_total = 0
    hints: list[str] = []
    confidences: list[float] = []

    for page in page_results:
        if page.page_period_hint:
            hints.append(page.page_period_hint)
        global_warnings.extend(page.warnings)
        conflicts_total += page.conflicts_count

        for emp in page.employees:
            if is_junk_employee_name(emp.raw_name):
                continue
            key = _merge_key(emp)
            if key not in merged:
                merged[key] = MergedEmployee(
                    raw_name=emp.raw_name,
                    matricule=emp.matricule,
                    weekly_total_pdf=emp.weekly_total_pdf,
                    days=list(emp.days),
                    warnings=list(emp.warnings),
                    pages_seen=[page.page_index],
                    confidence=emp.confidence,
                )
                confidences.append(emp.confidence)
                continue

            target = merged[key]
            target.pages_seen.append(page.page_index)
            merged_days, day_conflicts = _merge_day_lists(target.days, emp.days)
            target.days = merged_days
            conflicts_total += day_conflicts
            if day_conflicts:
                target.warnings.append(
                    f"Conflit inter-pages sur {day_conflicts} jour(s) — dernière page retenue."
                )
            if emp.weekly_total_pdf is not None:
                target.weekly_total_pdf = emp.weekly_total_pdf
            target.confidence = (target.confidence + emp.confidence) / 2
            confidences.append(emp.confidence)

    employees = list(merged.values())
    avg_conf = sum(confidences) / len(confidences) if confidences else 0.0

    from app.modules.schedules.application.timesheet_warning_filter import (
        filter_timesheet_warnings,
    )

    return MergedExtractionResult(
        employees=employees,
        warnings=filter_timesheet_warnings(global_warnings),
        conflicts_count=conflicts_total,
        confidence=round(avg_conf, 3),
        page_period_hints=hints,
        pages_processed=len(page_results),
    )


__all__ = ["MergedEmployee", "MergedExtractionResult", "merge_page_results"]
