"""Import catalogue CC depuis Légifrance (KALI / PISTE)."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Optional

from app.modules.collective_agreements.application.dto import CatalogCreateInput
from app.modules.collective_agreements.application.service import (
    CollectiveAgreementsService,
    get_collective_agreements_service,
)
from app.modules.collective_agreements.domain.exceptions import ValidationError
from app.modules.collective_agreements.infrastructure.kali_client import (
    KaliClient,
    KaliNotFoundError,
    PisteNotConfiguredError,
    get_kali_client,
)
from app.modules.collective_agreements.infrastructure.providers import (
    AgreementTextCacheProvider,
)
from app.modules.collective_agreements.rules.constants import PRIORITY_IDCC
from app.modules.collective_agreements.rules.repository import CCRulesRepository
from app.modules.collective_agreements.rules.service import (
    CCRulesService,
    ExtractionOutcome,
    get_cc_rules_service,
)

logger = logging.getLogger(__name__)


@dataclass
class KaliImportOutcome:
    success: bool
    idcc: str
    agreement_id: Optional[str] = None
    title: Optional[str] = None
    legifrance_url: Optional[str] = None
    character_count: int = 0
    created: bool = False
    rules_extraction: Optional[ExtractionOutcome] = None
    error: Optional[str] = None


class KaliImportService:
    """Importe une CC depuis KALI → catalogue + cache texte (+ règles paie optionnel)."""

    def __init__(
        self,
        *,
        kali: Optional[KaliClient] = None,
        agreements: Optional[CollectiveAgreementsService] = None,
        text_cache: Optional[AgreementTextCacheProvider] = None,
        rules_repo: Optional[CCRulesRepository] = None,
        rules_service: Optional[CCRulesService] = None,
    ):
        self._kali = kali or get_kali_client()
        self._agreements = agreements or get_collective_agreements_service()
        self._text_cache = text_cache or AgreementTextCacheProvider()
        self._rules_repo = rules_repo or CCRulesRepository()
        self._rules_service = rules_service or get_cc_rules_service()

    def import_by_idcc(
        self,
        idcc: str,
        *,
        extract_rules: bool = True,
        sector: Optional[str] = None,
    ) -> KaliImportOutcome:
        try:
            fetched = self._kali.fetch_convention_text(idcc)
        except PisteNotConfiguredError as exc:
            return KaliImportOutcome(success=False, idcc=idcc, error=str(exc))
        except KaliNotFoundError as exc:
            return KaliImportOutcome(success=False, idcc=idcc, error=str(exc))
        except Exception as exc:
            logger.exception("Import KALI IDCC %s", idcc)
            return KaliImportOutcome(
                success=False, idcc=idcc, error=f"Erreur API Légifrance : {exc}"
            )

        meta = fetched.meta
        agreement, created = self._ensure_catalog_entry(
            meta.idcc, meta.title, meta.legifrance_url, sector=sector
        )
        agreement_id = agreement["id"]

        self._text_cache.set_full_text(
            agreement_id,
            fetched.full_text,
            fetched.character_count,
            source_hash=f"kali:{meta.kalicont_id}",
        )

        rules_outcome: Optional[ExtractionOutcome] = None
        if extract_rules:
            rules_outcome = self._rules_service.extract_and_persist_from_text(
                agreement_id,
                fetched.full_text,
            )

        return KaliImportOutcome(
            success=True,
            idcc=meta.idcc,
            agreement_id=agreement_id,
            title=meta.title,
            legifrance_url=meta.legifrance_url,
            character_count=fetched.character_count,
            created=created,
            rules_extraction=rules_outcome,
        )

    def import_batch(
        self,
        *,
        idcc_list: Optional[list[str]] = None,
        priority_only: bool = False,
        extract_rules: bool = True,
    ) -> list[KaliImportOutcome]:
        targets = list(PRIORITY_IDCC) if priority_only or not idcc_list else idcc_list
        return [
            self.import_by_idcc(idcc, extract_rules=extract_rules) for idcc in targets
        ]

    def get_text_source(self, agreement_id: str) -> str:
        """Retourne kali | pdf | text | missing."""
        cached = self._text_cache.get_full_text(agreement_id)
        if cached:
            try:
                response = (
                    self._rules_repo._supabase.table("collective_agreement_texts")
                    .select("pdf_hash")
                    .eq("agreement_id", agreement_id)
                    .maybe_single()
                    .execute()
                )
                row = response.data if response and response.data else None
                pdf_hash = str(row.get("pdf_hash") or "") if row else ""
                if pdf_hash.startswith("kali:"):
                    return "kali"
                return "text"
            except Exception:
                return "text"
        agreement = self._agreements.get_catalog_item(agreement_id)
        if agreement and agreement.get("rules_pdf_path"):
            return "pdf"
        return "missing"

    def _ensure_catalog_entry(
        self,
        idcc: str,
        title: str,
        legifrance_url: str,
        *,
        sector: Optional[str],
    ) -> tuple[dict[str, Any], bool]:
        existing = self._rules_repo.list_catalog_by_idcc(idcc)
        description = f"Texte officiel Légifrance (KALI). {legifrance_url}"
        if existing:
            updated = self._agreements.update_catalog_item(
                existing["id"],
                {
                    "name": title,
                    "description": description,
                    "is_active": True,
                    **({"sector": sector} if sector else {}),
                },
                is_platform_admin=True,
            )
            return updated or existing, False

        created = self._agreements.create_catalog_item(
            CatalogCreateInput(
                name=title,
                idcc=idcc,
                description=description,
                sector=sector,
                effective_date=None,
                is_active=True,
                rules_pdf_path=None,
                rules_pdf_filename=None,
            ),
            is_platform_admin=True,
        )
        return created, True

def get_kali_import_service() -> KaliImportService:
    return KaliImportService()
