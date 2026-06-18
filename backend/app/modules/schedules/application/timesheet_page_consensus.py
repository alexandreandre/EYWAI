"""Consensus vision + texte OCR pour une page de relevé de pointages."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.modules.schedules.application.employee_match import (
    _normalize_matricule,
    is_junk_employee_name,
)

HOURS_MATCH_OK = 0.25
HOURS_MISMATCH_WARN = 0.5


@dataclass
class PageEmployee:
    raw_name: str
    matricule: str | None = None
    weekly_total_pdf: float | None = None
    days: list[dict[str, Any]] = field(default_factory=list)
    confidence: float = 0.5
    warnings: list[str] = field(default_factory=list)
    source_channels: list[str] = field(default_factory=list)


@dataclass
class PageExtractionResult:
    page_index: int
    employees: list[PageEmployee] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    conflicts_count: int = 0
    tokens_used: int = 0
    page_period_hint: str | None = None
    vision_data: dict[str, Any] | None = None
    text_data: dict[str, Any] | None = None


def _employee_key(raw_name: str, matricule: str | None) -> str:
    mat = _normalize_matricule(matricule)
    if mat:
        return f"mat:{mat}"
    return f"name:{(raw_name or '').strip().lower()}"


def _parse_channel_data(data: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not data:
        return []
    employees = data.get("employees") or []
    out: list[dict[str, Any]] = []
    for emp in employees:
        raw_name = str(emp.get("raw_name") or "").strip()
        if not raw_name or is_junk_employee_name(raw_name):
            continue
        out.append(emp)
    return out


def _hours_close(a: float | None, b: float | None) -> bool:
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    return abs(a - b) <= HOURS_MATCH_OK


def _merge_days(
    vision_days: list[dict[str, Any]],
    text_days: list[dict[str, Any]],
    *,
    prefer_vision: bool,
) -> tuple[list[dict[str, Any]], int]:
    conflicts = 0
    by_jour: dict[int, dict[str, Any]] = {}

    for source_days, channel in ((vision_days, "vision"), (text_days, "text")):
        for day in source_days:
            try:
                jour = int(day.get("jour"))
            except (TypeError, ValueError):
                continue
            heures = day.get("heures")
            try:
                heures_val = None if heures is None else float(heures)
            except (TypeError, ValueError):
                heures_val = None
            day_type = str(day.get("type") or "travail")
            existing = by_jour.get(jour)
            if existing is None:
                by_jour[jour] = {
                    "jour": jour,
                    "heures": heures_val,
                    "type": day_type,
                }
                continue
            if _hours_close(existing.get("heures"), heures_val):
                if existing.get("heures") is None and heures_val is not None:
                    existing["heures"] = heures_val
                continue
            conflicts += 1
            if prefer_vision and channel == "vision":
                by_jour[jour] = {"jour": jour, "heures": heures_val, "type": day_type}
            elif not prefer_vision and channel == "text":
                by_jour[jour] = {"jour": jour, "heures": heures_val, "type": day_type}

    return sorted(by_jour.values(), key=lambda d: d["jour"]), conflicts


def _vision_confidence(data: dict[str, Any] | None) -> float:
    if not data:
        return 0.0
    try:
        return float(data.get("confidence") or 0.5)
    except (TypeError, ValueError):
        return 0.5


def _text_confidence(data: dict[str, Any] | None) -> float:
    if not data:
        return 0.0
    try:
        return float(data.get("confidence") or 0.5)
    except (TypeError, ValueError):
        return 0.5


def build_page_consensus(
    *,
    page_index: int,
    vision_data: dict[str, Any] | None,
    text_data: dict[str, Any] | None,
    tokens_used: int = 0,
) -> PageExtractionResult:
    """Fusionne les extractions vision et texte d'une même page."""
    vision_emps = _parse_channel_data(vision_data)
    text_emps = _parse_channel_data(text_data)
    prefer_vision = _vision_confidence(vision_data) >= _text_confidence(text_data)

    index: dict[str, tuple[dict[str, Any] | None, dict[str, Any] | None]] = {}
    for emp in vision_emps:
        key = _employee_key(str(emp.get("raw_name") or ""), emp.get("matricule"))
        prev = index.get(key, (None, None))
        index[key] = (emp, prev[1])
    for emp in text_emps:
        key = _employee_key(str(emp.get("raw_name") or ""), emp.get("matricule"))
        prev = index.get(key, (None, None))
        index[key] = (prev[0], emp)

    employees: list[PageEmployee] = []
    warnings: list[str] = []
    conflicts_total = 0

    for key, (v_emp, t_emp) in index.items():
        if v_emp and t_emp:
            raw_name = str(v_emp.get("raw_name") or t_emp.get("raw_name") or "")
            matricule = v_emp.get("matricule") or t_emp.get("matricule")
            v_days = v_emp.get("days") or []
            t_days = t_emp.get("days") or []
            merged_days, day_conflicts = _merge_days(
                v_days, t_days, prefer_vision=prefer_vision
            )
            conflicts_total += day_conflicts
            weekly = v_emp.get("weekly_total_pdf")
            if weekly is None:
                weekly = t_emp.get("weekly_total_pdf")
            try:
                weekly_val = None if weekly is None else float(weekly)
            except (TypeError, ValueError):
                weekly_val = None
            employees.append(
                PageEmployee(
                    raw_name=raw_name,
                    matricule=str(matricule).strip() if matricule else None,
                    weekly_total_pdf=weekly_val,
                    days=merged_days,
                    confidence=min(
                        1.0,
                        (_vision_confidence(vision_data) + _text_confidence(text_data)) / 2,
                    ),
                    warnings=[],
                    source_channels=["vision", "text"],
                )
            )
        elif v_emp:
            raw_name = str(v_emp.get("raw_name") or "")
            matricule = v_emp.get("matricule")
            employees.append(
                PageEmployee(
                    raw_name=raw_name,
                    matricule=str(matricule).strip() if matricule else None,
                    weekly_total_pdf=_coerce_float(v_emp.get("weekly_total_pdf")),
                    days=list(v_emp.get("days") or []),
                    confidence=_vision_confidence(vision_data) * 0.85,
                    warnings=[],
                    source_channels=["vision"],
                )
            )
        elif t_emp:
            raw_name = str(t_emp.get("raw_name") or "")
            matricule = t_emp.get("matricule")
            employees.append(
                PageEmployee(
                    raw_name=raw_name,
                    matricule=str(matricule).strip() if matricule else None,
                    weekly_total_pdf=_coerce_float(t_emp.get("weekly_total_pdf")),
                    days=list(t_emp.get("days") or []),
                    confidence=_text_confidence(text_data) * 0.85,
                    warnings=[],
                    source_channels=["text"],
                )
            )

    period_hint = None
    if vision_data and vision_data.get("page_period_hint"):
        period_hint = str(vision_data["page_period_hint"])
    elif text_data and text_data.get("page_period_hint"):
        period_hint = str(text_data["page_period_hint"])

    from app.modules.schedules.application.timesheet_warning_filter import (
        filter_timesheet_warnings,
    )

    warnings = filter_timesheet_warnings(warnings)

    return PageExtractionResult(
        page_index=page_index,
        employees=employees,
        warnings=warnings,
        conflicts_count=conflicts_total,
        tokens_used=tokens_used,
        page_period_hint=period_hint,
        vision_data=vision_data,
        text_data=text_data,
    )


def _coerce_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


__all__ = ["PageEmployee", "PageExtractionResult", "build_page_consensus"]
