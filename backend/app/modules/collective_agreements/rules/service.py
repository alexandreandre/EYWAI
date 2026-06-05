"""Service d'extraction et persistance des règles CC paie."""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from typing import Any, Callable, Optional

from app.modules.collective_agreements.application.service import (
    CollectiveAgreementsService,
    get_collective_agreements_service,
)
from app.modules.collective_agreements.domain.exceptions import (
    NotFoundError,
    ValidationError,
)
from app.modules.collective_agreements.rules.completude import finalize_document
from app.modules.collective_agreements.rules.constants import PRIORITY_IDCC, SCHEMA_VERSION
from app.modules.collective_agreements.rules.diagnostics import log_cc_doc, log_cc_outcome, log_cc_stage
from app.modules.collective_agreements.rules.deterministic import apply_deterministic_layer
from app.modules.collective_agreements.rules.extractor import CCRulesExtractor
from app.modules.collective_agreements.rules.repository import CCRulesRepository
from app.modules.collective_agreements.rules.schema import document_to_engine_rules
from app.modules.collective_agreements.rules.validator import validate_cc_rules
from app.modules.collective_agreements.infrastructure.providers import (
    AgreementStorageProvider,
    AgreementTextCacheProvider,
)

logger = logging.getLogger(__name__)


@dataclass
class ExtractionOutcome:
    success: bool
    idcc: str
    agreement_id: Optional[str]
    rules: Optional[dict[str, Any]] = None
    error: Optional[str] = None
    tokens_used: int = 0
    confidence: Optional[str] = None
    log_id: Optional[str] = None
    cancelled: bool = False


@dataclass
class RulesStatus:
    idcc: str
    agreement_id: str
    has_rules: bool
    rules: Optional[dict[str, Any]]
    source_text_hash: Optional[str]
    extracted_at: Optional[str]
    extraction_model: Optional[str]
    latest_log_status: Optional[str]
    latest_log_error: Optional[str]
    confidence: Optional[str]


class CCRulesService:
    """Orchestration : texte PDF → extraction IA → validation → écriture auto."""

    def __init__(
        self,
        *,
        rules_repo: Optional[CCRulesRepository] = None,
        agreements_service: Optional[CollectiveAgreementsService] = None,
        extractor: Optional[CCRulesExtractor] = None,
        storage: Optional[AgreementStorageProvider] = None,
        text_cache: Optional[AgreementTextCacheProvider] = None,
    ):
        self._rules_repo = rules_repo or CCRulesRepository()
        self._agreements = agreements_service or get_collective_agreements_service()
        self._extractor = extractor or CCRulesExtractor()
        self._storage = storage or AgreementStorageProvider()
        self._text_cache = text_cache or AgreementTextCacheProvider()

    def extract_and_persist_by_agreement_id(
        self,
        agreement_id: str,
        *,
        dry_run: bool = False,
    ) -> ExtractionOutcome:
        agreement = self._agreements.get_catalog_item(agreement_id)
        if not agreement:
            raise NotFoundError("Convention collective non trouvée")
        idcc = agreement.get("idcc") or ""
        if not idcc:
            raise ValidationError("IDCC manquant sur la convention")

        if dry_run:
            previous_row = self._rules_repo.get_rules_by_idcc(idcc)
            return ExtractionOutcome(
                success=True,
                idcc=idcc,
                agreement_id=agreement_id,
                rules=previous_row.get("rules") if previous_row else None,
                error="dry_run: extraction IA non exécutée",
            )

        try:
            full_text = self._ensure_full_text(agreement_id, agreement)
        except ValidationError as exc:
            return self._log_error(idcc, agreement_id, str(exc.message))

        text_hash = _hash_text(full_text)
        previous_row = self._rules_repo.get_rules_by_idcc(idcc)
        previous_rules = previous_row.get("rules") if previous_row else None

        doc, tokens, extract_error = self._extractor.extract_from_text(
            full_text, idcc=idcc
        )
        if extract_error or doc is None:
            return self._log_error(
                idcc,
                agreement_id,
                extract_error or "Extraction échouée",
                model=self._extractor._model,
                tokens_used=tokens,
            )

        doc = finalize_document(doc)
        validation = validate_cc_rules(doc, expected_idcc=idcc)
        if not validation.ok:
            msg = "; ".join(validation.errors)
            self._rules_repo.log_extraction(
                idcc=idcc,
                agreement_id=agreement_id,
                status="rejected_validation",
                rules_proposed=document_to_engine_rules(doc),
                rules_previous=previous_rules,
                error_message=msg,
                model=self._extractor._model,
                tokens_used=tokens,
            )
            return ExtractionOutcome(
                success=False,
                idcc=idcc,
                agreement_id=agreement_id,
                error=msg,
                tokens_used=tokens,
            )

        if doc.meta:
            doc.meta.source_agreement_id = agreement_id

        engine_rules = document_to_engine_rules(doc)
        row = self._rules_repo.upsert_rules(
            idcc=idcc,
            rules=engine_rules,
            agreement_id=agreement_id,
            schema_version=SCHEMA_VERSION,
            extraction_model=self._extractor._model,
            source_text_hash=text_hash,
        )
        log_entry = self._rules_repo.log_extraction(
            idcc=idcc,
            agreement_id=agreement_id,
            status="success",
            rules_proposed=engine_rules,
            rules_previous=previous_rules,
            model=self._extractor._model,
            tokens_used=tokens,
        )
        confidence = doc.meta.confidence if doc.meta else None
        return ExtractionOutcome(
            success=True,
            idcc=idcc,
            agreement_id=agreement_id,
            rules=row.get("rules", engine_rules),
            tokens_used=tokens,
            confidence=confidence,
            log_id=log_entry.get("id"),
        )

    def extract_and_persist_by_idcc(
        self,
        idcc: str,
        *,
        dry_run: bool = False,
    ) -> ExtractionOutcome:
        agreement = self._rules_repo.list_catalog_by_idcc(idcc)
        if not agreement:
            return ExtractionOutcome(
                success=False,
                idcc=idcc,
                agreement_id=None,
                error=f"Aucune convention active pour IDCC {idcc}",
            )
        return self.extract_and_persist_by_agreement_id(
            agreement["id"], dry_run=dry_run
        )

    def extract_batch(
        self,
        *,
        idcc_list: Optional[list[str]] = None,
        all_catalog: bool = False,
        priority_only: bool = False,
        dry_run: bool = False,
    ) -> list[ExtractionOutcome]:
        targets: list[str] = []
        if priority_only:
            targets = list(PRIORITY_IDCC)
        elif idcc_list:
            targets = idcc_list
        elif all_catalog:
            catalog = self._rules_repo.list_all_active_catalog()
            outcomes: list[ExtractionOutcome] = []
            for item in catalog:
                has_pdf = bool(item.get("rules_pdf_path"))
                has_text = bool(self._text_cache.get_full_text(item["id"]))
                if has_pdf or has_text:
                    outcomes.append(
                        self.extract_and_persist_by_agreement_id(
                            item["id"], dry_run=dry_run
                        )
                    )
            return outcomes
        else:
            targets = list(PRIORITY_IDCC)

        return [
            self.extract_and_persist_by_idcc(idcc, dry_run=dry_run) for idcc in targets
        ]

    def get_rules_status(self, agreement_id: str) -> RulesStatus:
        agreement = self._agreements.get_catalog_item(agreement_id)
        if not agreement:
            raise NotFoundError("Convention collective non trouvée")
        idcc = agreement.get("idcc") or ""
        rules_row = self._rules_repo.get_rules_by_agreement_id(agreement_id)
        if not rules_row:
            rules_row = self._rules_repo.get_rules_by_idcc(idcc)
        latest_log = self._rules_repo.get_latest_log(agreement_id)
        rules = rules_row.get("rules") if rules_row else None
        confidence = None
        if isinstance(rules, dict):
            meta = rules.get("meta")
            if isinstance(meta, dict):
                confidence = meta.get("confidence")
        return RulesStatus(
            idcc=idcc,
            agreement_id=agreement_id,
            has_rules=bool(rules),
            rules=rules,
            source_text_hash=rules_row.get("source_text_hash") if rules_row else None,
            extracted_at=rules_row.get("extracted_at") if rules_row else None,
            extraction_model=rules_row.get("extraction_model") if rules_row else None,
            latest_log_status=latest_log.get("status") if latest_log else None,
            latest_log_error=latest_log.get("error_message") if latest_log else None,
            confidence=confidence,
        )

    def rollback(self, log_id: str) -> Optional[dict[str, Any]]:
        return self._rules_repo.rollback_from_log(log_id)

    def extract_and_persist_from_text(
        self,
        agreement_id: str,
        full_text: str,
        *,
        should_cancel: Callable[[], bool] | None = None,
    ) -> ExtractionOutcome:
        """Extraction IA depuis un texte déjà en cache (ex. import KALI)."""
        agreement = self._agreements.get_catalog_item(agreement_id)
        if not agreement:
            raise NotFoundError("Convention collective non trouvée")
        idcc = agreement.get("idcc") or ""
        if not idcc:
            raise ValidationError("IDCC manquant sur la convention")
        if not full_text or len(full_text.strip()) < 100:
            return self._log_error(
                idcc, agreement_id, "Texte CC trop court pour l'extraction IA"
            )

        text_hash = _hash_text(full_text)
        previous_row = self._rules_repo.get_rules_by_idcc(idcc)
        previous_rules = previous_row.get("rules") if previous_row else None
        log_cc_stage(
            idcc,
            "persist_debut",
            agreement_id=agreement_id,
            text_chars=len(full_text),
            had_previous_rules=bool(previous_rules),
        )

        doc, tokens, extract_error = self._extractor.extract_from_text(
            full_text,
            idcc=idcc,
            should_cancel=should_cancel,
        )
        if extract_error == "Annulé par l'utilisateur":
            log_cc_outcome(
                idcc,
                success=False,
                agreement_id=agreement_id,
                error=extract_error,
                tokens_used=tokens,
            )
            return ExtractionOutcome(
                success=False,
                idcc=idcc,
                agreement_id=agreement_id,
                error=extract_error,
                tokens_used=tokens,
                cancelled=True,
            )
        if extract_error or doc is None:
            log_cc_outcome(
                idcc,
                success=False,
                agreement_id=agreement_id,
                error=extract_error or "Extraction échouée",
                tokens_used=tokens,
            )
            return self._log_error(
                idcc,
                agreement_id,
                extract_error or "Extraction échouée",
                model=self._extractor._model,
                tokens_used=tokens,
            )

        doc = finalize_document(doc)
        doc = apply_deterministic_layer(doc, full_text, idcc=idcc)
        log_cc_doc(idcc, "apres_deterministic", doc)
        log_cc_doc(idcc, "avant_validation", doc)
        validation = validate_cc_rules(doc, expected_idcc=idcc)
        if not validation.ok:
            msg = "; ".join(validation.errors)
            log_cc_outcome(
                idcc,
                success=False,
                agreement_id=agreement_id,
                error=f"validation_rejetee: {msg}",
                tokens_used=tokens,
                doc=doc,
            )
            self._rules_repo.log_extraction(
                idcc=idcc,
                agreement_id=agreement_id,
                status="rejected_validation",
                rules_proposed=document_to_engine_rules(doc),
                rules_previous=previous_rules,
                error_message=msg,
                model=self._extractor._model,
                tokens_used=tokens,
            )
            return ExtractionOutcome(
                success=False,
                idcc=idcc,
                agreement_id=agreement_id,
                error=msg,
                tokens_used=tokens,
            )

        if doc.meta:
            doc.meta.source_agreement_id = agreement_id

        engine_rules = document_to_engine_rules(doc)
        row = self._rules_repo.upsert_rules(
            idcc=idcc,
            rules=engine_rules,
            agreement_id=agreement_id,
            schema_version=SCHEMA_VERSION,
            extraction_model=self._extractor._model,
            source_text_hash=text_hash,
        )
        log_entry = self._rules_repo.log_extraction(
            idcc=idcc,
            agreement_id=agreement_id,
            status="success",
            rules_proposed=engine_rules,
            rules_previous=previous_rules,
            model=self._extractor._model,
            tokens_used=tokens,
        )
        confidence = doc.meta.confidence if doc.meta else None
        persisted = row.get("rules", engine_rules)
        log_cc_outcome(
            idcc,
            success=True,
            agreement_id=agreement_id,
            tokens_used=tokens,
            doc=doc,
            persisted_rules=persisted if isinstance(persisted, dict) else None,
        )
        return ExtractionOutcome(
            success=True,
            idcc=idcc,
            agreement_id=agreement_id,
            rules=row.get("rules", engine_rules),
            tokens_used=tokens,
            confidence=confidence,
            log_id=log_entry.get("id"),
        )

    def _ensure_full_text(
        self, agreement_id: str, agreement: dict[str, Any]
    ) -> str:
        cached = self._text_cache.get_full_text(agreement_id)
        if cached:
            return cached
        if not agreement.get("rules_pdf_path"):
            raise ValidationError(
                "Aucun texte disponible — importez depuis Légifrance ou uploadez un PDF"
            )
        pdf_url = self._storage.create_signed_url(agreement["rules_pdf_path"], 3600)
        if not pdf_url:
            raise ValidationError("Impossible de générer l'URL du PDF")
        return self._agreements._get_or_cache_pdf_text(
            agreement_id, pdf_url, agreement.get("name", "")
        )

    def _log_error(
        self,
        idcc: str,
        agreement_id: str,
        message: str,
        *,
        model: Optional[str] = None,
        tokens_used: int = 0,
    ) -> ExtractionOutcome:
        log_entry = self._rules_repo.log_extraction(
            idcc=idcc,
            agreement_id=agreement_id,
            status="error",
            error_message=message,
            model=model,
            tokens_used=tokens_used,
        )
        return ExtractionOutcome(
            success=False,
            idcc=idcc,
            agreement_id=agreement_id,
            error=message,
            tokens_used=tokens_used,
            log_id=log_entry.get("id"),
        )


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def get_cc_rules_service() -> CCRulesService:
    return CCRulesService()
