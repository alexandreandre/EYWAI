"""Configuration extraction relevés de pointages (feature flags)."""

from __future__ import annotations

import os

ExtractMode = str  # deterministic | hybrid | llm_document


def timesheet_extract_mode() -> str:
    raw = os.getenv("TIMESHEET_EXTRACT_MODE", "hybrid").strip().lower()
    if raw in ("deterministic", "hybrid", "llm_document"):
        return raw
    return "hybrid"


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


__all__ = [
    "timesheet_extract_mode",
    "timesheet_page_concurrency",
    "timesheet_page_text_model",
    "timesheet_vision_model",
]
