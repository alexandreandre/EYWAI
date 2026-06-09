"""Extraction IA des formations depuis le texte d'une convention collective."""

from __future__ import annotations

import logging
from typing import Callable, Optional

from app.modules.collective_agreements.rules.chunker import strip_html
from app.modules.collective_agreements.training_reco.prompts import (
    EXTRACTION_SYSTEM_PROMPT,
    EXTRACTION_USER_TEMPLATE,
)
from app.modules.collective_agreements.training_reco.schema import (
    EXTRACTION_JSON_SCHEMA,
    CcTrainingExtractionDocument,
    parse_extraction_result,
)
from app.shared.infrastructure.ai.models import MODEL_CC_TRAINING_EXTRACTION
from app.shared.infrastructure.ai.structured_extractor import (
    StructuredExtractionResult,
    extract_structured_json,
)

logger = logging.getLogger(__name__)

ExtractFn = Callable[..., Optional[StructuredExtractionResult]]
MAX_EXTRACTION_CHARS = 120_000


class CcTrainingExtractor:
    """Extraction single-pass des formations conventionnelles."""

    def __init__(
        self,
        *,
        model: str = MODEL_CC_TRAINING_EXTRACTION,
        extract_fn: ExtractFn | None = None,
    ):
        self._model = model
        self._extract_fn = extract_fn or extract_structured_json

    def extract_from_text(
        self,
        full_text: str,
        *,
        idcc: str,
    ) -> tuple[CcTrainingExtractionDocument | None, int, str | None]:
        if not full_text or len(full_text.strip()) < 100:
            return None, 0, "Texte CC trop court ou absent"

        cleaned = strip_html(full_text)
        excerpt = cleaned[:MAX_EXTRACTION_CHARS]
        user_prompt = EXTRACTION_USER_TEMPLATE.format(idcc=idcc, text=excerpt)

        try:
            result = self._extract_fn(
                system_prompt=EXTRACTION_SYSTEM_PROMPT,
                user_prompt=user_prompt,
                json_schema=EXTRACTION_JSON_SCHEMA,
                schema_name="cc_training_extraction",
                model=self._model,
                temperature=0.0,
                max_tokens=8192,
            )
        except Exception as exc:
            logger.exception("Extraction formations CC échouée pour IDCC %s", idcc)
            return None, 0, str(exc)

        if not result:
            return None, 0, "Extraction IA sans résultat"

        try:
            doc = parse_extraction_result(result.data, expected_idcc=idcc)
        except Exception as exc:
            return None, result.tokens_used, f"Validation JSON échouée: {exc}"

        return doc, result.tokens_used, None
