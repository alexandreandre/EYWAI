"""Orchestration extraction IA : repérage + extraction structurée."""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Callable, Optional

from app.modules.collective_agreements.rules.chunker import (
    build_minima_focused_text,
    build_payroll_focused_text,
    build_scout_window,
    extract_article_blocks,
    split_salary_grille_chunks,
    strip_html,
)
from app.modules.collective_agreements.rules.completude import finalize_document
from app.modules.collective_agreements.rules.constants import (
    MAX_EXTRACTION_CHARS,
    MAX_PARALLEL_GRILLE_EXTRACTIONS,
)
from app.modules.collective_agreements.rules.diagnostics import log_cc_doc, log_cc_partial, log_cc_stage
from app.modules.collective_agreements.rules.merge import merge_extraction_results
from app.modules.collective_agreements.rules.prompts import (
    EXTRACTION_SYSTEM_PROMPT,
    EXTRACTION_USER_TEMPLATE,
    GRILLE_CHUNK_SYSTEM_PROMPT,
    GRILLE_CHUNK_USER_TEMPLATE,
    MINIMA_FOCUS_SYSTEM_PROMPT,
    MINIMA_FOCUS_USER_TEMPLATE,
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
        should_cancel: Callable[[], bool] | None = None,
    ) -> tuple[CCRulesDocument | None, int, str | None]:
        """
        Retourne (document, tokens_used, error_message).
        """
        if should_cancel and should_cancel():
            return None, 0, "Annulé par l'utilisateur"

        if not full_text or len(full_text.strip()) < 100:
            return None, 0, "Texte CC trop court ou absent"

        cleaned = strip_html(full_text)
        total_tokens = 0
        partials: list[dict[str, Any]] = []

        grille_chunks = split_salary_grille_chunks(cleaned)
        log_cc_stage(
            idcc,
            "debut_extraction",
            text_chars=len(cleaned),
            salary_chunks=len(grille_chunks),
        )
        if len(grille_chunks) >= 1:
            logger.info(
                "IDCC %s : extraction multi-grilles (%d blocs, parallèle x%d)",
                idcc,
                len(grille_chunks),
                MAX_PARALLEL_GRILLE_EXTRACTIONS,
            )
            partials, chunk_tokens = self._extract_grille_chunks_parallel(
                grille_chunks,
                idcc=idcc,
                should_cancel=should_cancel,
            )
            total_tokens += chunk_tokens
            if should_cancel and should_cancel():
                return None, total_tokens, "Annulé par l'utilisateur"
            logger.info(
                "IDCC %s : %d/%d grilles extraites",
                idcc,
                len(partials),
                len(grille_chunks),
            )

        if not partials:
            doc, tokens, err = self._extract_once(
                cleaned, idcc=idcc, should_cancel=should_cancel
            )
            total_tokens += tokens
            if err or doc is None:
                return doc, total_tokens, err
            partials = [document_to_raw(doc)]

        if should_cancel and should_cancel():
            return None, total_tokens, "Annulé par l'utilisateur"

        doc = merge_extraction_results(partials, idcc=idcc)
        log_cc_doc(idcc, "apres_merge_partials", doc)

        if not (doc.prime_anciennete and doc.prime_anciennete.bareme):
            focused = build_payroll_focused_text(cleaned)
            doc2, tokens2, _ = self._extract_once(
                focused, idcc=idcc, should_cancel=should_cancel
            )
            total_tokens += tokens2
            if should_cancel and should_cancel():
                return None, total_tokens, "Annulé par l'utilisateur"
            if doc2 and doc2.prime_anciennete and doc2.prime_anciennete.bareme:
                partials.append(document_to_raw(doc2))
                doc = merge_extraction_results(partials, idcc=idcc)
                log_cc_doc(idcc, "apres_merge_prime_focus", doc)

        if not _has_minima_content(doc):
            log_cc_stage(idcc, "fallback_extraction_minima", reason="minima_absents_apres_merge")
            focused_minima = build_minima_focused_text(cleaned)
            doc_min, tokens_m, _ = self._extract_minima_focus(
                focused_minima,
                idcc=idcc,
                should_cancel=should_cancel,
            )
            total_tokens += tokens_m
            if should_cancel and should_cancel():
                return None, total_tokens, "Annulé par l'utilisateur"
            if doc_min and _has_minima_content(doc_min):
                doc = merge_extraction_results(
                    [document_to_raw(doc), document_to_raw(doc_min)],
                    idcc=idcc,
                )
                log_cc_doc(idcc, "apres_merge_minima_fallback", doc)

        doc = finalize_document(doc)
        log_cc_doc(idcc, "apres_finalize", doc)
        if doc.meta:
            doc.meta.model = self._model
        return doc, total_tokens, None

    def _extract_grille_chunks_parallel(
        self,
        chunks: list[str],
        *,
        idcc: str,
        should_cancel: Callable[[], bool] | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        partials: list[dict[str, Any]] = []
        total_tokens = 0
        workers = min(MAX_PARALLEL_GRILLE_EXTRACTIONS, len(chunks))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {
                pool.submit(self._extract_grille_chunk, chunk, idcc=idcc): idx
                for idx, chunk in enumerate(chunks)
            }
            for future in as_completed(futures):
                if should_cancel and should_cancel():
                    for pending in futures:
                        pending.cancel()
                    break
                chunk_result, chunk_tokens, chunk_err = future.result()
                total_tokens += chunk_tokens
                idx = futures[future]
                if chunk_result:
                    log_cc_partial(idcc, idx, len(chunks), chunk_result)
                    partials.append(chunk_result)
                elif chunk_err:
                    log_cc_stage(
                        idcc,
                        f"chunk_ia_{idx + 1}/{len(chunks)}_echec",
                        error=chunk_err,
                    )
                    logger.warning(
                        "Extraction grille %d/%d échouée IDCC %s : %s",
                        idx + 1,
                        len(chunks),
                        idcc,
                        chunk_err,
                    )
        return partials, total_tokens

    def _extract_grille_chunk(
        self,
        chunk_text: str,
        *,
        idcc: str,
    ) -> tuple[dict[str, Any] | None, int, str | None]:
        """Extraction directe d'un bloc salarial (sans repérage scout)."""
        extract_result = self._extract_fn(
            system_prompt=GRILLE_CHUNK_SYSTEM_PROMPT,
            user_prompt=GRILLE_CHUNK_USER_TEMPLATE.format(
                idcc=idcc, text=chunk_text
            ),
            json_schema=EXTRACTION_JSON_SCHEMA,
            schema_name="cc_rules_v2",
            model=self._model,
        )
        if not extract_result:
            return None, 0, "Extraction grille échouée"
        return extract_result.data, extract_result.tokens_used, None

    def _extract_minima_focus(
        self,
        full_text: str,
        *,
        idcc: str,
        should_cancel: Callable[[], bool] | None = None,
    ) -> tuple[CCRulesDocument | None, int, str | None]:
        """Extraction directe des minima (sans scout, sans prime)."""
        if should_cancel and should_cancel():
            return None, 0, "Annulé par l'utilisateur"
        if not full_text or len(full_text.strip()) < 100:
            return None, 0, "Texte CC trop court ou absent"

        extract_result = self._extract_fn(
            system_prompt=MINIMA_FOCUS_SYSTEM_PROMPT,
            user_prompt=MINIMA_FOCUS_USER_TEMPLATE.format(
                idcc=idcc, text=full_text
            ),
            json_schema=EXTRACTION_JSON_SCHEMA,
            schema_name="cc_rules_v2",
            model=self._model,
        )
        if not extract_result:
            return None, 0, "Extraction minima échouée"
        doc = merge_extraction_results([extract_result.data], idcc=idcc)
        return doc, extract_result.tokens_used, None

    def _extract_once(
        self,
        full_text: str,
        *,
        idcc: str,
        should_cancel: Callable[[], bool] | None = None,
    ) -> tuple[CCRulesDocument | None, int, str | None]:
        """Une passe scout + extraction."""
        if should_cancel and should_cancel():
            return None, 0, "Annulé par l'utilisateur"
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
        if should_cancel and should_cancel():
            return None, total_tokens, "Annulé par l'utilisateur"
        if scout_result:
            total_tokens += scout_result.tokens_used
            article_refs = scout_result.data.get("article_references", [])
        else:
            article_refs = []
            logger.warning("Repérage articles échoué pour IDCC %s — fallback", idcc)

        extraction_text = extract_article_blocks(
            full_text, article_refs, max_chars=MAX_EXTRACTION_CHARS
        )

        if should_cancel and should_cancel():
            return None, total_tokens, "Annulé par l'utilisateur"

        extract_result = self._extract_fn(
            system_prompt=EXTRACTION_SYSTEM_PROMPT,
            user_prompt=EXTRACTION_USER_TEMPLATE.format(
                idcc=idcc, text=extraction_text
            ),
            json_schema=EXTRACTION_JSON_SCHEMA,
            schema_name="cc_rules_v2",
            model=self._model,
        )
        if not extract_result:
            return None, total_tokens, "Extraction IA échouée"

        total_tokens += extract_result.tokens_used
        doc = merge_extraction_results([extract_result.data], idcc=idcc)
        if doc.meta:
            doc.meta.model = self._model
        return doc, total_tokens, None


def _has_minima_content(doc: CCRulesDocument) -> bool:
    return bool(doc.salaires_minima) or any(
        g.minima for g in doc.grilles_salaires
    )


def _has_payroll_content(doc: CCRulesDocument) -> bool:
    return _has_minima_content(doc) or bool(
        doc.prime_anciennete and doc.prime_anciennete.bareme
    )


def document_to_raw(doc: CCRulesDocument) -> dict[str, Any]:
    """Sérialise un document pour merge_extraction_results."""
    return {
        "idcc": doc.idcc,
        "prime_anciennete": (
            {
                "bareme": [
                    {"annees_min": p.annees_min, "taux": p.taux}
                    for p in doc.prime_anciennete.bareme
                ],
                "base_de_calcul": (
                    doc.prime_anciennete.base_de_calcul.model_dump()
                    if doc.prime_anciennete.base_de_calcul
                    else None
                ),
            }
            if doc.prime_anciennete
            else None
        ),
        "salaires_minima": [
            {
                "coefficient": m.coefficient,
                "valeur": m.valeur,
                "libelle": m.libelle,
            }
            for m in doc.salaires_minima
        ],
        "grilles_salaires": [
            {
                "zone_type": g.zone_type,
                "zone_libelle": g.zone_libelle,
                "departements": g.departements,
                "regions": g.regions,
                "date_effet": g.date_effet,
                "source_titre": g.source_titre,
                "minima": [
                    {
                        "coefficient": m.coefficient,
                        "valeur": m.valeur,
                        "libelle": m.libelle,
                    }
                    for m in g.minima
                ],
            }
            for g in doc.grilles_salaires
        ],
        "confidence": doc.meta.confidence if doc.meta else "medium",
        "citations": (
            [c.model_dump() for c in doc.meta.citations] if doc.meta else []
        ),
    }


def dry_run_parse(full_text: str, idcc: str) -> CCRulesDocument | None:
    """Parse sans IA — utilisé pour tests et dry-run CLI."""
    if not full_text:
        return None
    doc = parse_extraction_result(
        {
            "idcc": idcc,
            "prime_anciennete": None,
            "salaires_minima": [],
            "grilles_salaires": [],
            "confidence": "low",
            "citations": [],
        }
    )
    return finalize_document(doc)
