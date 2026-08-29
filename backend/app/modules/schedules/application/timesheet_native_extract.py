"""Extraction native des relevés : PDF envoyé au modèle par lots, sans OCR local."""

from __future__ import annotations

import asyncio
import io
import logging
from datetime import date
from typing import Any, Callable

import PyPDF2

from app.modules.schedules.application.timesheet_extract_config import (
    timesheet_native_batch_size,
    timesheet_page_concurrency,
    timesheet_vision_model,
)
from app.modules.schedules.application.timesheet_hybrid_extract import (
    _CEGID_FALLBACK_THRESHOLD,
    _matricule_hint,
    _merged_to_cegid_result,
    HybridExtractResult,
)
from app.modules.schedules.application.timesheet_import.registry import (
    best_deterministic_parse,
)
from app.modules.schedules.application.timesheet_page_consensus import (
    PageExtractionResult,
    build_page_consensus,
)
from app.modules.schedules.application.timesheet_page_merge import merge_page_results
from app.modules.schedules.application.timesheet_page_schema import (
    BATCH_EXTRACTION_JSON_SCHEMA,
    PAGE_EXTRACTION_JSON_SCHEMA,
    build_batch_user_prompt_native,
    build_page_system_prompt,
    build_page_user_prompt_vision,
)
from app.modules.schedules.domain.punch_accounting_entities import (
    PunchAccountingSettings,
)
from app.shared.infrastructure.ai import is_llm_configured
from app.shared.infrastructure.ai.client_async import aclose_current_loop_client
from app.shared.infrastructure.ai.structured_document import (
    extract_structured_json_from_pdf,
)
from app.shared.infrastructure.ai.structured_vision import (
    extract_structured_json_from_image,
)
from app.shared.infrastructure.documents.pdf_batches import (
    PdfBatch,
    split_pdf_into_batches,
)
from app.shared.infrastructure.documents.text_extraction import (
    DocumentExtractionError,
    extract_pdf_text_layer,
)

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[dict[str, Any]], None]

# Aligné sur _CEGID_CONFIDENCE_THRESHOLD d'ai_fill : au-delà, le parseur
# déterministe suffit et aucun appel IA n'est nécessaire (spec §3.2-1).
_DETERMINISTIC_SHORTCIRCUIT_CONFIDENCE = 0.75

_IMAGE_MIMES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".heic": "image/heic",
}


def _is_pdf(file_content: bytes, filename: str) -> bool:
    return file_content[:4] == b"%PDF" or (filename or "").lower().endswith(".pdf")


def _image_mime(filename: str) -> str:
    from pathlib import Path

    return _IMAGE_MIMES.get(Path((filename or "")).suffix.lower(), "image/png")


def _real_pdf_page_count(file_content: bytes, *, fallback: int) -> int:
    """Nombre réel de pages du PDF, indépendamment du plafond de split_pdf_into_batches.

    split_pdf_into_batches plafonne silencieusement à max_pages=120 : sans ce
    calcul, un relevé de plus de 120 pages serait tronqué sans avertissement.
    """
    try:
        return len(PyPDF2.PdfReader(io.BytesIO(file_content)).pages)
    except Exception as exc:  # repli défensif sur PDF corrompu
        logger.warning(
            "Comptage réel des pages PDF impossible, repli sur le total des lots (%s): %s",
            fallback,
            exc,
        )
        return fallback


def _consensus_from_page_data(
    page_data: dict[str, Any],
    *,
    fallback_index: int,
    tokens: int,
    year: int,
    month: int,
    punch_settings: PunchAccountingSettings | None,
) -> PageExtractionResult:
    idx = page_data.get("page_index")
    page_index = int(idx) if isinstance(idx, int) and idx > 0 else fallback_index
    return build_page_consensus(
        page_index=page_index,
        vision_data=page_data,
        text_data=None,
        tokens_used=tokens,
        year=year,
        month=month,
        format_hint=None,
        punch_settings=punch_settings,
    )


async def _extract_pdf_batches_async(
    *,
    file_content: bytes,
    year: int,
    month: int,
    mat_hint: str,
    week_anchor_context: str,
    punch_settings: PunchAccountingSettings | None,
    on_progress: ProgressCallback | None,
) -> tuple[list[PageExtractionResult], int, int]:
    batches = split_pdf_into_batches(
        file_content, batch_size=timesheet_native_batch_size()
    )
    pages_total = batches[-1].page_end if batches else 0
    semaphore = asyncio.Semaphore(timesheet_page_concurrency())
    page_results: list[PageExtractionResult] = []
    tokens_total = 0
    done_pages = 0

    def _heartbeat(current_page: int) -> None:
        if on_progress:
            on_progress(
                {
                    "phase": "extracting",
                    "pages_total": pages_total,
                    "pages_done": done_pages,
                    "current_page": current_page,
                }
            )

    async def _run_batch(batch: PdfBatch):
        async with semaphore:
            _heartbeat(batch.page_start)
            payload = await extract_structured_json_from_pdf(
                system_prompt=build_page_system_prompt(
                    year=year,
                    month=month,
                    channel="vision",
                    week_anchor_context=week_anchor_context,
                ),
                user_prompt=build_batch_user_prompt_native(
                    page_start=batch.page_start,
                    page_end=batch.page_end,
                    pages_total=pages_total,
                    matricule_hint=mat_hint,
                ),
                pdf_bytes=batch.content,
                filename=f"pages-{batch.page_start}-{batch.page_end}.pdf",
                json_schema=BATCH_EXTRACTION_JSON_SCHEMA,
                schema_name="timesheet_batch_native",
                model=timesheet_vision_model(),
                max_tokens=8192,
            )
            return batch, payload

    try:
        _heartbeat(0)
        for coro in asyncio.as_completed([_run_batch(b) for b in batches]):
            batch, payload = await coro
            batch_pages = list(range(batch.page_start, batch.page_end + 1))
            if payload is None:
                for idx in batch_pages:
                    page_results.append(
                        PageExtractionResult(
                            page_index=idx,
                            warnings=[f"Page {idx} : extraction native échouée."],
                        )
                    )
            else:
                pages = payload.data.get("pages") or []
                per_page_tokens = payload.tokens_used // max(1, len(pages))
                covered_pages: set[int] = set()
                for offset, page_data in enumerate(pages):
                    page_result = _consensus_from_page_data(
                        page_data,
                        fallback_index=batch_pages[min(offset, len(batch_pages) - 1)],
                        tokens=per_page_tokens,
                        year=year,
                        month=month,
                        punch_settings=punch_settings,
                    )
                    page_results.append(page_result)
                    covered_pages.add(page_result.page_index)
                tokens_total += payload.tokens_used
                # Une réponse partielle (modèle qui omet une page du lot) ne doit
                # pas faire disparaître la page sans trace : on la signale.
                for idx in batch_pages:
                    if idx not in covered_pages:
                        page_results.append(
                            PageExtractionResult(
                                page_index=idx,
                                warnings=[f"Page {idx} : absente de la réponse IA."],
                            )
                        )
            done_pages += len(batch_pages)
            _heartbeat(batch.page_end)

        return page_results, tokens_total, pages_total
    finally:
        # Fin de l'orchestration async de ce job : oublie et ferme le client
        # (et son pool httpx) attaché à la boucle courante.
        await aclose_current_loop_client()


def extract_timesheet_native(
    *,
    file_content: bytes,
    filename: str,
    year: int,
    month: int,
    known_matricules: list[str] | None = None,
    on_progress: ProgressCallback | None = None,
    week_anchor_context: str = "",
    week_anchor_date: date | None = None,
    punch_settings: PunchAccountingSettings | None = None,
) -> HybridExtractResult:
    """Même contrat de sortie que l'hybride, sans OCR local ni rendu 300 DPI."""
    if not is_llm_configured():
        raise DocumentExtractionError(
            "L'extraction native nécessite OPENROUTER_API_KEY."
        )
    mat_hint = _matricule_hint(known_matricules or [])

    if _is_pdf(file_content, filename):
        # Fast path spec §3.2-1 : couche texte Cegid confiante → zéro appel IA.
        text_layer = extract_pdf_text_layer(file_content)
        if text_layer:
            det = best_deterministic_parse(text_layer, year=year, month=month)
            if (
                det.parse_result
                and det.parse_result.format_detected
                and det.parse_result.confidence >= _DETERMINISTIC_SHORTCIRCUIT_CONFIDENCE
                and det.parse_result.employees
            ):
                from app.modules.schedules.application.timesheet_page_merge import (
                    MergedExtractionResult,
                )

                pages = 1
                if on_progress:
                    on_progress(
                        {
                            "phase": "merging",
                            "pages_total": pages,
                            "pages_done": pages,
                            "current_page": pages,
                        }
                    )
                return HybridExtractResult(
                    parse_result=det.parse_result,
                    full_ocr_text=text_layer,
                    extraction_method="native_text_layer",
                    pages_total=pages,
                    pages_processed=pages,
                    truncated=False,
                    merged=MergedExtractionResult(
                        confidence=det.parse_result.confidence
                    ),
                    used_cegid_fallback=True,
                    fallback_parser_key=det.parser_key,
                )

        page_results, tokens_total, pages_total = asyncio.run(
            _extract_pdf_batches_async(
                file_content=file_content,
                year=year,
                month=month,
                mat_hint=mat_hint,
                week_anchor_context=week_anchor_context,
                punch_settings=punch_settings,
                on_progress=on_progress,
            )
        )
        # text_layer déjà calculé avant le fast path déterministe.
        method = "native_pdf"
        # split_pdf_into_batches plafonne à max_pages=120 : pages_total ci-dessus
        # est donc le total *traité* (lots), pas forcément le total réel du
        # document. Le vrai comptage sert à détecter et signaler une troncature.
        real_pages_total = _real_pdf_page_count(file_content, fallback=pages_total)
    else:
        from pathlib import Path

        if Path(filename or "").suffix.lower() not in _IMAGE_MIMES:
            raise DocumentExtractionError(
                "Format non supporté. Formats acceptés : PDF, JPG, PNG."
            )
        vision = extract_structured_json_from_image(
            system_prompt=build_page_system_prompt(
                year=year,
                month=month,
                channel="vision",
                week_anchor_context=week_anchor_context,
            ),
            user_prompt=build_page_user_prompt_vision(
                page_index=1, pages_total=1, matricule_hint=mat_hint
            ),
            image_bytes=file_content,
            mime_type=_image_mime(filename),
            json_schema=PAGE_EXTRACTION_JSON_SCHEMA,
            schema_name="timesheet_page_vision",
            model=timesheet_vision_model(),
            max_tokens=4096,
        )
        if vision is None:
            page_results = [
                PageExtractionResult(
                    page_index=1, warnings=["Page 1 : extraction native échouée."]
                )
            ]
            tokens_total = 0
        else:
            page_results = [
                build_page_consensus(
                    page_index=1,
                    vision_data=vision.data,
                    text_data=None,
                    tokens_used=vision.tokens_used,
                    year=year,
                    month=month,
                    format_hint=None,
                    punch_settings=punch_settings,
                )
            ]
            tokens_total = vision.tokens_used
        pages_total = 1
        real_pages_total = 1
        text_layer = ""
        method = "native_image"

    page_results.sort(key=lambda p: p.page_index)
    merged = merge_page_results(page_results, format_hint=None)

    from app.modules.schedules.application.parsers.cegid_weekly import CegidParseResult

    fallback_attempt = best_deterministic_parse(text_layer, year=year, month=month)
    cegid_fallback = fallback_attempt.parse_result or CegidParseResult(
        format_detected=False, confidence=0.0
    )

    used_fallback = False
    if merged.confidence < _CEGID_FALLBACK_THRESHOLD and cegid_fallback.employees:
        if cegid_fallback.confidence > merged.confidence or len(
            cegid_fallback.employees
        ) > len(merged.employees):
            parse_result = cegid_fallback
            used_fallback = True
        else:
            parse_result = _merged_to_cegid_result(
                merged,
                target_year=year,
                target_month=month,
                cegid_fallback=cegid_fallback,
                week_anchor_date=week_anchor_date,
            )
    else:
        parse_result = _merged_to_cegid_result(
            merged,
            target_year=year,
            target_month=month,
            cegid_fallback=cegid_fallback,
            week_anchor_date=week_anchor_date,
        )

    truncated = real_pages_total > pages_total
    warnings: list[str] = []
    if used_fallback:
        warnings.append("Repli parseur Cegid utilisé (confiance native insuffisante).")
    if truncated:
        warnings.append(
            f"Document tronqué à {pages_total} pages sur {real_pages_total} "
            "pour l'analyse IA."
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
        full_ocr_text=text_layer,
        extraction_method=method,
        pages_total=real_pages_total,
        pages_processed=pages_total,
        truncated=truncated,
        warnings=warnings,
        page_results=page_results,
        merged=merged,
        tokens_used=tokens_total,
        consensus_conflicts=merged.conflicts_count,
        used_cegid_fallback=used_fallback,
        fallback_parser_key=fallback_attempt.parser_key if used_fallback else None,
    )


__all__ = ["extract_timesheet_native"]
