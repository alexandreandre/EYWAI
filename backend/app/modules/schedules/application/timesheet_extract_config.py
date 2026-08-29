"""Configuration extraction relevés de pointages (feature flags)."""

from __future__ import annotations

import os

ExtractMode = str  # deterministic | hybrid | llm_document | native


def timesheet_extract_mode() -> str:
    raw = os.getenv("TIMESHEET_EXTRACT_MODE", "hybrid").strip().lower()
    if raw in ("deterministic", "hybrid", "llm_document", "native"):
        return raw
    return "hybrid"


def timesheet_native_batch_size() -> int:
    raw = os.getenv("TIMESHEET_NATIVE_BATCH_PAGES", "4").strip()
    try:
        return max(1, min(10, int(raw)))
    except ValueError:
        return 4


def timesheet_page_concurrency() -> int:
    raw = os.getenv("TIMESHEET_PAGE_CONCURRENCY", "4").strip()
    try:
        return max(1, min(8, int(raw)))
    except ValueError:
        return 4


def timesheet_vision_model() -> str:
    from app.shared.infrastructure.ai.models import MODEL_TIMESHEET_VISION

    return os.getenv("TIMESHEET_VISION_MODEL", MODEL_TIMESHEET_VISION).strip()


def timesheet_page_text_model() -> str:
    from app.shared.infrastructure.ai.models import MODEL_TIMESHEET_PAGE_TEXT

    return os.getenv("TIMESHEET_PAGE_TEXT_MODEL", MODEL_TIMESHEET_PAGE_TEXT).strip()


def timesheet_hybrid_adaptive() -> bool:
    raw = os.getenv("TIMESHEET_HYBRID_ADAPTIVE", "true").strip().lower()
    return raw in ("1", "true", "yes", "on")


__all__ = [
    "timesheet_extract_mode",
    "timesheet_hybrid_adaptive",
    "timesheet_native_batch_size",
    "timesheet_page_concurrency",
    "timesheet_page_text_model",
    "timesheet_vision_model",
]
