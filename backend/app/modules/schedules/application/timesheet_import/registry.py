"""Registre de parseurs import pointages."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.modules.schedules.application.exceptions import ScheduleAppError
from app.modules.schedules.application.parsers.cegid_weekly import try_parse_cegid_weekly
from app.modules.schedules.application.parsers.cegid_horizontal import (
    try_parse_cegid_horizontal,
)
from app.modules.schedules.application.parsers.banque_heures import try_parse_banque_heures
from app.modules.schedules.application.parsers.kelio_weekly import try_parse_kelio_weekly
from app.modules.schedules.application.timesheet_import.structured_parser import (
    parse_tabular_file,
)
from app.shared.infrastructure.documents import (
    DocumentExtractionError,
    extract_document_text,
)
from app.shared.infrastructure.documents.text_extraction import SUPPORTED_EXTENSIONS


@dataclass
class ParseAttempt:
    parser_key: str
    confidence: float
    text: str = ""
    extraction_method: str = ""
    parse_result: Any = None
    tabular_rows: List[Dict[str, Any]] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


def detect_source_type(filename: str) -> str:
    lower = (filename or "").lower()
    if lower.endswith(".pdf"):
        return "document_pdf"
    if lower.endswith(".csv"):
        return "csv"
    if lower.endswith((".xlsx", ".xls")):
        return "xlsx"
    if lower.endswith((".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff", ".bmp")):
        return "document_image"
    return "document_pdf"


def _try_cegid(text: str, *, year: int, month: int) -> ParseAttempt:
    result = try_parse_cegid_weekly(text, target_year=year, target_month=month)
    return ParseAttempt(
        parser_key="cegid_weekly",
        confidence=result.confidence if result.format_detected else 0.0,
        text=text,
        extraction_method="ocr",
        parse_result=result,
        warnings=list(result.parse_warnings),
    )


def _try_cegid_horizontal(text: str, *, year: int, month: int) -> ParseAttempt:
    result = try_parse_cegid_horizontal(text, target_year=year, target_month=month)
    return ParseAttempt(
        parser_key="cegid_horizontal",
        confidence=result.confidence if result.format_detected else 0.0,
        text=text,
        extraction_method="ocr",
        parse_result=result,
        warnings=list(result.parse_warnings),
    )


def _try_banque_heures(text: str, *, year: int, month: int) -> ParseAttempt:
    result = try_parse_banque_heures(text, target_year=year, target_month=month)
    return ParseAttempt(
        parser_key="banque_heures",
        confidence=result.confidence if result.format_detected else 0.0,
        text=text,
        extraction_method="pdf_native",
        parse_result=result,
        warnings=list(result.parse_warnings),
    )


def _try_kelio(text: str, *, year: int, month: int) -> ParseAttempt:
    result = try_parse_kelio_weekly(text, target_year=year, target_month=month)
    return ParseAttempt(
        parser_key="kelio_weekly",
        confidence=result.confidence if result.format_detected else 0.0,
        text=text,
        extraction_method="ocr",
        parse_result=result,
        warnings=list(result.parse_warnings),
    )


def _best_deterministic(text: str, *, year: int, month: int) -> ParseAttempt:
    attempts = [
        _try_cegid(text, year=year, month=month),
        _try_cegid_horizontal(text, year=year, month=month),
        _try_banque_heures(text, year=year, month=month),
        _try_kelio(text, year=year, month=month),
    ]
    return max(attempts, key=lambda attempt: attempt.confidence)


def _try_tabular(
    content: bytes,
    filename: str,
    *,
    year: int,
    month: int,
    column_mapping: Optional[Dict[str, str]] = None,
    options: Optional[Dict[str, Any]] = None,
) -> ParseAttempt:
    parsed = parse_tabular_file(
        content,
        filename,
        target_year=year,
        target_month=month,
        column_mapping=column_mapping,
        options=options or {},
    )
    parser_key = "tabular_punch_pairs" if any(
        r.entry_raw is not None or r.exit_raw is not None for r in parsed.rows
    ) else "tabular_generic"
    return ParseAttempt(
        parser_key=parser_key,
        confidence=parsed.confidence,
        parse_result=parsed,
        tabular_rows=parsed.rows,
        warnings=list(parsed.warnings),
    )


def parse_document(
    content: bytes,
    filename: str,
    *,
    company_id: str | None,
    year: int,
    month: int,
    parser_key: str | None = None,
    column_mapping: Dict[str, str] | None = None,
    options: Dict[str, Any] | None = None,
    skip_llm: bool = False,
) -> ParseAttempt:
    """Tente les parseurs déterministes ; retourne llm_required si IA nécessaire."""
    _ = company_id
    source = detect_source_type(filename)

    if parser_key == "tabular_generic" or parser_key == "tabular_punch_pairs" or source in ("csv", "xlsx"):
        return _try_tabular(
            content,
            filename,
            year=year,
            month=month,
            column_mapping=column_mapping,
            options=options,
        )

    if parser_key == "cegid_weekly":
        text, method, _meta = extract_document_text(content, filename)
        attempt = _try_cegid(text, year=year, month=month)
        attempt.extraction_method = method
        return attempt

    if parser_key == "cegid_horizontal":
        text, method, _meta = extract_document_text(content, filename)
        attempt = _try_cegid_horizontal(text, year=year, month=month)
        attempt.extraction_method = method
        return attempt

    if parser_key == "banque_heures":
        text, method, _meta = extract_document_text(content, filename)
        attempt = _try_banque_heures(text, year=year, month=month)
        attempt.extraction_method = method
        return attempt

    if parser_key == "kelio_weekly":
        text, method, _meta = extract_document_text(content, filename)
        attempt = _try_kelio(text, year=year, month=month)
        attempt.extraction_method = method
        return attempt

    ext = (filename or "").lower()
    if ext.endswith((".csv", ".xlsx", ".xls")):
        return _try_tabular(
            content,
            filename,
            year=year,
            month=month,
            column_mapping=column_mapping,
            options=options,
        )

    if not any(ext.endswith(e) for e in SUPPORTED_EXTENSIONS):
        raise ScheduleAppError(
            "validation",
            "Format de fichier non supporté.",
            status_code=400,
        )

    try:
        text, method, meta = extract_document_text(content, filename)
    except DocumentExtractionError as e:
        raise ScheduleAppError("validation", str(e), status_code=400) from e

    best = _best_deterministic(text, year=year, month=month)
    best.extraction_method = method
    if best.confidence >= 0.75 and best.parse_result and best.parse_result.employees:
        return best

    if skip_llm:
        if best.confidence >= 0.5:
            return best
        raise ScheduleAppError(
            "validation",
            "Format non reconnu sans assistant IA.",
            status_code=422,
        )

    return ParseAttempt(
        parser_key="llm_required",
        confidence=best.confidence,
        text=text,
        extraction_method=method,
        parse_result=best.parse_result if best.confidence >= 0.5 else None,
        warnings=list(meta.warnings) + best.warnings,
    )


def best_deterministic_parse(text: str, *, year: int, month: int) -> ParseAttempt:
    """Choisit le parseur déterministe le plus confiant pour un texte extrait."""
    return _best_deterministic(text, year=year, month=month)


__all__ = ["ParseAttempt", "best_deterministic_parse", "detect_source_type", "parse_document"]
