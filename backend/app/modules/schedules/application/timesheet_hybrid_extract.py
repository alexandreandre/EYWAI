"""Orchestrateur extraction hybride par page (vision + OCR texte)."""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Any, Callable

from app.modules.schedules.application.parsers.cegid_weekly import (
    CegidEmployeeBlock,
    CegidParseResult,
    try_parse_cegid_weekly,
)
from app.modules.schedules.application.timesheet_extract_config import (
    timesheet_page_concurrency,
    timesheet_page_text_model,
    timesheet_vision_model,
)
from app.modules.schedules.application.timesheet_page_consensus import (
    PageExtractionResult,
    build_page_consensus,
)
from app.modules.schedules.application.timesheet_page_merge import (
    MergedExtractionResult,
    merge_page_results,
)
from app.modules.schedules.application.timesheet_page_schema import (
    PAGE_EXTRACTION_JSON_SCHEMA,
    build_page_system_prompt,
    build_page_user_prompt_text,
    build_page_user_prompt_vision,
)
from app.shared.infrastructure.ai import is_llm_configured
from app.shared.infrastructure.ai.structured_extractor import extract_structured_json
from app.shared.infrastructure.ai.structured_vision import extract_structured_json_from_image
from app.shared.infrastructure.documents.text_extraction import (
    DocumentExtractionError,
    RenderedDocument,
    RenderedPage,
    render_document_pages,
)

logger = logging.getLogger(__name__)

_CEGID_FALLBACK_THRESHOLD = 0.6
ProgressCallback = Callable[[dict[str, Any]], None]


@dataclass
class HybridExtractResult:
    parse_result: CegidParseResult
    full_ocr_text: str
    extraction_method: str
    pages_total: int
    pages_processed: int
    truncated: bool
    warnings: list[str] = field(default_factory=list)
    page_results: list[PageExtractionResult] = field(default_factory=list)
    merged: MergedExtractionResult | None = None
    tokens_used: int = 0
    consensus_conflicts: int = 0
    used_cegid_fallback: bool = False


def _matricule_hint(known_mats: list[str]) -> str:
    if not known_mats:
        return ""
    return (
        "Matricules GTA connus : "
        + ", ".join(sorted(set(known_mats))[:30])
        + "."
    )


def _extract_single_page_hybrid(
    page: RenderedPage,
    *,
    year: int,
    month: int,
    pages_total: int,
    matricule_hint: str,
) -> PageExtractionResult:
    tokens = 0
    vision_data: dict[str, Any] | None = None
    text_data: dict[str, Any] | None = None

    if is_llm_configured():
        vision_result = extract_structured_json_from_image(
            system_prompt=build_page_system_prompt(
                year=year, month=month, channel="vision"
            ),
            user_prompt=build_page_user_prompt_vision(
                page_index=page.page_index,
                pages_total=pages_total,
                matricule_hint=matricule_hint,
            ),
            image_bytes=page.png_bytes,
            mime_type="image/png",
            json_schema=PAGE_EXTRACTION_JSON_SCHEMA,
            schema_name="timesheet_page_vision",
            model=timesheet_vision_model(),
            max_tokens=4096,
        )
        if vision_result:
            vision_data = vision_result.data
            tokens += vision_result.tokens_used

        if page.ocr_text and page.ocr_text.strip():
            text_result = extract_structured_json(
                system_prompt=build_page_system_prompt(
                    year=year, month=month, channel="text"
                ),
                user_prompt=build_page_user_prompt_text(
                    ocr_text=page.ocr_text,
                    page_index=page.page_index,
                    pages_total=pages_total,
                    matricule_hint=matricule_hint,
                ),
                json_schema=PAGE_EXTRACTION_JSON_SCHEMA,
                schema_name="timesheet_page_text",
                model=timesheet_page_text_model(),
                max_tokens=4096,
            )
            if text_result:
                text_data = text_result.data
                tokens += text_result.tokens_used

    return build_page_consensus(
        page_index=page.page_index,
        vision_data=vision_data,
        text_data=text_data,
        tokens_used=tokens,
    )


def _merged_to_cegid_result(
    merged: MergedExtractionResult,
    *,
    target_year: int,
    target_month: int,
    cegid_fallback: CegidParseResult | None = None,
) -> CegidParseResult:
    employees: list[CegidEmployeeBlock] = []
    for emp in merged.employees:
        days_in_month = [
            d
            for d in emp.days
            if d.get("jour") is not None
        ]
        days_parsed = len(
            [d for d in days_in_month if d.get("heures") is not None]
        )
        expected = len(days_in_month) if days_in_month else 5
        block = CegidEmployeeBlock(
            matricule=emp.matricule or "",
            raw_name=emp.raw_name,
            days=[],
            week_days=[],
            weekly_total_hours=emp.weekly_total_pdf,
            days_expected_count=expected,
            days_parsed_count=days_parsed,
            parse_warnings=list(emp.warnings),
        )
        from app.modules.schedules.application.parsers.cegid_weekly import CegidDayEntry

        for day in days_in_month:
            try:
                jour = int(day.get("jour"))
            except (TypeError, ValueError):
                continue
            heures = day.get("heures")
            try:
                heures_val = 0.0 if heures is None else float(heures)
            except (TypeError, ValueError):
                heures_val = 0.0
            block.days.append(
                CegidDayEntry(
                    jour=jour,
                    month=target_month,
                    year=target_year,
                    heures=heures_val,
                )
            )
        employees.append(block)

    result = CegidParseResult(
        format_detected=True,
        confidence=merged.confidence,
        employees=employees,
        parse_warnings=list(merged.warnings),
    )
    if cegid_fallback:
        if cegid_fallback.period_start:
            result.period_start = cegid_fallback.period_start
        if cegid_fallback.period_end:
            result.period_end = cegid_fallback.period_end
        if cegid_fallback.week_number:
            result.week_number = cegid_fallback.week_number
        if cegid_fallback.week_year:
            result.week_year = cegid_fallback.week_year
    return result


def extract_timesheet_hybrid(
    *,
    file_content: bytes,
    filename: str,
    year: int,
    month: int,
    known_matricules: list[str] | None = None,
    on_progress: ProgressCallback | None = None,
) -> HybridExtractResult:
    """
    Extraction hybride page par page avec consensus vision/OCR.
    Retourne un CegidParseResult compatible avec le pipeline existant.
    """
    if not is_llm_configured():
        raise DocumentExtractionError(
            "L'extraction hybride nécessite OPENROUTER_API_KEY."
        )

    rendered: RenderedDocument = render_document_pages(file_content, filename)
    full_ocr_text = "\n\n".join(p.ocr_text for p in rendered.pages if p.ocr_text)
    mat_hint = _matricule_hint(known_matricules or [])

    if on_progress:
        on_progress(
            {
                "phase": "extracting",
                "pages_total": rendered.pages_total,
                "pages_done": 0,
                "current_page": 0,
            }
        )

    page_results: list[PageExtractionResult] = []
    tokens_total = 0
    concurrency = timesheet_page_concurrency()
    pages_total = len(rendered.pages) or rendered.pages_total

    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = {
            pool.submit(
                _extract_single_page_hybrid,
                page,
                year=year,
                month=month,
                pages_total=pages_total,
                matricule_hint=mat_hint,
            ): page.page_index
            for page in rendered.pages
        }
        done_count = 0
        for future in as_completed(futures):
            page_idx = futures[future]
            try:
                result = future.result()
                page_results.append(result)
                tokens_total += result.tokens_used
            except Exception as exc:
                logger.warning("Extraction page %s échouée: %s", page_idx, exc)
                page_results.append(
                    PageExtractionResult(
                        page_index=page_idx,
                        warnings=[f"Page {page_idx} : extraction échouée ({exc})."],
                    )
                )
            done_count += 1
            if on_progress:
                on_progress(
                    {
                        "phase": "extracting",
                        "pages_total": pages_total,
                        "pages_done": done_count,
                        "current_page": page_idx,
                    }
                )

    page_results.sort(key=lambda p: p.page_index)
    merged = merge_page_results(page_results)
    cegid_fallback = try_parse_cegid_weekly(
        full_ocr_text, target_year=year, target_month=month
    )

    used_fallback = False
    if merged.confidence < _CEGID_FALLBACK_THRESHOLD and cegid_fallback.employees:
        if (
            cegid_fallback.confidence > merged.confidence
            or len(cegid_fallback.employees) > len(merged.employees)
        ):
            parse_result = cegid_fallback
            used_fallback = True
        else:
            parse_result = _merged_to_cegid_result(
                merged,
                target_year=year,
                target_month=month,
                cegid_fallback=cegid_fallback,
            )
    else:
        parse_result = _merged_to_cegid_result(
            merged,
            target_year=year,
            target_month=month,
            cegid_fallback=cegid_fallback,
        )

    warnings = list(rendered.warnings)
    if used_fallback:
        warnings.append(
            "Repli parseur Cegid utilisé (confiance hybride insuffisante)."
        )

    if on_progress:
        on_progress(
            {
                "phase": "merging",
                "pages_total": pages_total,
                "pages_done": pages_total,
                "current_page": pages_total,
            }
        )

    return HybridExtractResult(
        parse_result=parse_result,
        full_ocr_text=full_ocr_text,
        extraction_method="hybrid_vision_ocr",
        pages_total=rendered.pages_total,
        pages_processed=rendered.pages_processed,
        truncated=rendered.truncated,
        warnings=warnings,
        page_results=page_results,
        merged=merged,
        tokens_used=tokens_total,
        consensus_conflicts=merged.conflicts_count,
        used_cegid_fallback=used_fallback,
    )


__all__ = ["HybridExtractResult", "extract_timesheet_hybrid"]
