"""Orchestration extraction IA : repérage + extraction structurée."""

from __future__ import annotations

import logging
from typing import Any, Callable, Optional

from app.modules.collective_agreements.rules.chunker import (
    build_payroll_focused_text,
    build_scout_window,
    extract_article_blocks,
    strip_html,
)
from app.modules.collective_agreements.rules.constants import MAX_EXTRACTION_CHARS
from app.modules.collective_agreements.rules.merge import merge_extraction_results
from app.modules.collective_agreements.rules.prompts import (
    EXTRACTION_SYSTEM_PROMPT,
    EXTRACTION_USER_TEMPLATE,
    SCOUT_SYSTEM_PROMPT,
    SCOUT_USER_TEMPLATE,
)
from app.modules.collective_agreements.rules.schema import (
    EXTRACTION_JSON_SCHEMA,
    SCOUT_JSON_SCHEMA,
    CCRulesDocument,
    parse_extraction_result,
)
from app.shared.infrastructure.ai.models import MODEL_CC_RULES_EXTRACTION
from app.shared.infrastructure.ai.structured_extractor import (
    StructuredExtractionResult,
    extract_structured_json,
)

logger = logging.getLogger(__name__)

ExtractFn = Callable[..., Optional[StructuredExtractionResult]]


class CCRulesExtractor:
    """Pipeline 2 passes : repérage articles puis extraction JSON."""

    def __init__(
        self,
        *,
        model: str = MODEL_CC_RULES_EXTRACTION,
        extract_fn: ExtractFn | None = None,
    ):
        self._model = model
        self._extract_fn = extract_fn or extract_structured_json

    def extract_from_text(
        self,
        full_text: str,
        *,
        idcc: str,
    ) -> tuple[CCRulesDocument | None, int, str | None]:
        """
        Retourne (document, tokens_used, error_message).
        """
        if not full_text or len(full_text.strip()) < 100:
            return None, 0, "Texte CC trop court ou absent"

        cleaned = strip_html(full_text)
        doc, tokens, err = self._extract_once(cleaned, idcc=idcc)
        if err or doc is None:
            return doc, tokens, err

        has_prime = bool(doc.prime_anciennete and doc.prime_anciennete.bareme)
        has_minima = bool(doc.salaires_minima)
        if not has_prime and not has_minima:
            focused = build_payroll_focused_text(cleaned)
            doc2, tokens2, err2 = self._extract_once(focused, idcc=idcc)
            tokens += tokens2
            if doc2 and (doc2.salaires_minima or (doc2.prime_anciennete and doc2.prime_anciennete.bareme)):
                return doc2, tokens, err2
        return doc, tokens, None

    def _extract_once(
        self,
        full_text: str,
        *,
        idcc: str,
    ) -> tuple[CCRulesDocument | None, int, str | None]:
        """Une passe scout + extraction."""
        if not full_text or len(full_text.strip()) < 100:
            return None, 0, "Texte CC trop court ou absent"

        total_tokens = 0

        scout_text = build_scout_window(full_text)
        scout_result = self._extract_fn(
            system_prompt=SCOUT_SYSTEM_PROMPT,
            user_prompt=SCOUT_USER_TEMPLATE.format(idcc=idcc, text=scout_text),
            json_schema=SCOUT_JSON_SCHEMA,
            schema_name="cc_scout",
            model=self._model,
        )
        if scout_result:
            total_tokens += scout_result.tokens_used
            article_refs = scout_result.data.get("article_references", [])
        else:
            article_refs = []
            logger.warning("Repérage articles échoué pour IDCC %s — fallback", idcc)

        extraction_text = extract_article_blocks(
            full_text, article_refs, max_chars=MAX_EXTRACTION_CHARS
        )

        extract_result = self._extract_fn(
            system_prompt=EXTRACTION_SYSTEM_PROMPT,
            user_prompt=EXTRACTION_USER_TEMPLATE.format(
                idcc=idcc, text=extraction_text
            ),
            json_schema=EXTRACTION_JSON_SCHEMA,
            schema_name="cc_rules_v1",
            model=self._model,
        )
        if not extract_result:
            return None, total_tokens, "Extraction IA échouée"

        total_tokens += extract_result.tokens_used
        doc = merge_extraction_results([extract_result.data], idcc=idcc)
        if doc.meta:
            doc.meta.model = self._model
        return doc, total_tokens, None


def dry_run_parse(full_text: str, idcc: str) -> CCRulesDocument | None:
    """Parse sans IA — utilisé pour tests et dry-run CLI."""
    if not full_text:
        return None
    # Retourne un document vide valide structurellement
    return parse_extraction_result(
        {
            "idcc": idcc,
            "prime_anciennete": None,
            "salaires_minima": [],
            "confidence": "low",
            "citations": [],
        }
    )
