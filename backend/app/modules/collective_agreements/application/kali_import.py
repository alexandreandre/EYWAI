"""Import catalogue CC depuis Légifrance (KALI / PISTE)."""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from typing import Any, Optional

from app.modules.collective_agreements.application.dto import CatalogCreateInput
from app.modules.collective_agreements.application.kali_import_cancel import (
    KaliImportCancelled,
    clear_catalog_sync_cancel,
    is_cancel_requested,
    kali_import_scope,
    raise_if_cancelled,
)
from app.modules.collective_agreements.application.service import (
    CollectiveAgreementsService,
    get_collective_agreements_service,
)
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
from app.modules.collective_agreements.rules.diagnostics import (
    log_cc_outcome,
    log_cc_stage,
    payroll_grid_available_from_rules,
)
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
    text_changed: bool = False
    rules_skipped: bool = False
    rules_extraction: Optional[ExtractionOutcome] = None
    error: Optional[str] = None
    cancelled: bool = False


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
        with kali_import_scope(idcc=idcc):
            try:
                return self._import_by_idcc_impl(
                    idcc,
                    extract_rules=extract_rules,
                    sector=sector,
                )
            except KaliImportCancelled:
                logger.info("Import KALI IDCC %s annulé par l'utilisateur", idcc)
                return KaliImportOutcome(
                    success=False,
                    idcc=idcc,
                    cancelled=True,
                    error="Annulé par l'utilisateur",
                )

    def _import_by_idcc_impl(
        self,
        idcc: str,
        *,
        extract_rules: bool = True,
        sector: Optional[str] = None,
    ) -> KaliImportOutcome:
        raise_if_cancelled(idcc=idcc)
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

        raise_if_cancelled(idcc=idcc)
        meta = fetched.meta
        agreement, created = self._ensure_catalog_entry(
            meta.idcc,
            meta.title,
            meta.legifrance_url,
            sector=sector,
            official_title=meta.full_title or meta.title,
        )
        agreement_id = agreement["id"]
        new_hash = _hash_text(fetched.full_text)
        previous_hash = (
            None if created else self._previous_text_hash(agreement_id, meta.idcc)
        )
        text_changed = previous_hash is None or new_hash != previous_hash

        log_cc_stage(
            meta.idcc,
            "kali_import_texte",
            agreement_id=agreement_id,
            text_changed=text_changed,
            character_count=fetched.character_count,
            created=created,
        )

        self._text_cache.set_full_text(
            agreement_id,
            fetched.full_text,
            fetched.character_count,
            source_hash=f"kali:{meta.kalicont_id}",
        )
        # Le texte de base intégral alimente l'assistant RH ; il est écrit après
        # ``set_full_text``, qui crée la ligne de cache si elle n'existe pas.
        # L'échec n'interrompt pas la synchro — le corpus paie, lui, est déjà
        # écrit — mais il DOIT se voir : une écriture perdue laisse l'assistant
        # sur une convention périmée, et cela ne se remarquerait qu'au moment où
        # il répond à côté. Deux coupures réseau en un seul backfill le 07/08.
        if fetched.base_text and not self._text_cache.set_base_text(
            agreement_id, fetched.base_text
        ):
            logger.error(
                "IDCC %s : texte de base NON enregistré, l'assistant RH garde "
                "la version précédente. Relancer "
                "scripts/backfill_cc_base_text.py --idcc %s --apply",
                meta.idcc,
                meta.idcc,
            )
            log_cc_stage(
                meta.idcc,
                "kali_import_base_text_echec",
                agreement_id=agreement_id,
                caracteres=len(fetched.base_text),
            )

        rules_outcome: Optional[ExtractionOutcome] = None
        rules_skipped = False
        if extract_rules:
            existing_rules = self._rules_repo.get_rules_by_idcc(meta.idcc)
            stored_rules = (
                existing_rules.get("rules")
                if existing_rules and isinstance(existing_rules.get("rules"), dict)
                else None
            )
            has_rules = bool(stored_rules)
            has_payroll_grid = payroll_grid_available_from_rules(stored_rules)
            should_extract = text_changed or not has_rules or not has_payroll_grid
            log_cc_stage(
                meta.idcc,
                "kali_import_decision_extraction",
                extract_rules=extract_rules,
                should_extract=should_extract,
                has_rules=has_rules,
                has_payroll_grid=has_payroll_grid,
                text_changed=text_changed,
            )
            if should_extract:
                raise_if_cancelled(idcc=meta.idcc)
                rules_outcome = self._rules_service.extract_and_persist_from_text(
                    agreement_id,
                    fetched.full_text,
                    should_cancel=lambda: is_cancel_requested(idcc=meta.idcc),
                )
                if rules_outcome.cancelled:
                    raise KaliImportCancelled()
                log_cc_outcome(
                    meta.idcc,
                    success=rules_outcome.success,
                    agreement_id=agreement_id,
                    error=rules_outcome.error,
                    tokens_used=rules_outcome.tokens_used,
                    rules_skipped=False,
                    persisted_rules=rules_outcome.rules
                    if isinstance(rules_outcome.rules, dict)
                    else None,
                )
            else:
                rules_skipped = True
                log_cc_outcome(
                    meta.idcc,
                    success=True,
                    agreement_id=agreement_id,
                    rules_skipped=True,
                    error="extraction_ia_ignoree_texte_et_grille_inchangees",
                )
                logger.info(
                    "IDCC %s : texte et grille paie inchangés, extraction ignorée",
                    meta.idcc,
                )

        return KaliImportOutcome(
            success=True,
            idcc=meta.idcc,
            agreement_id=agreement_id,
            title=meta.title,
            legifrance_url=meta.legifrance_url,
            character_count=fetched.character_count,
            created=created,
            text_changed=text_changed,
            rules_skipped=rules_skipped,
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

    def sync_active_catalog(
        self,
        *,
        extract_rules: bool = True,
    ) -> list[KaliImportOutcome]:
        """Ré-importe depuis Légifrance toutes les CC actives du catalogue."""
        clear_catalog_sync_cancel()
        items = self._rules_repo.list_all_active_catalog()
        outcomes: list[KaliImportOutcome] = []
        for item in items:
            if is_cancel_requested():
                logger.info("Sync catalogue Légifrance annulée après %d convention(s)", len(outcomes))
                break
            idcc = str(item.get("idcc") or "").strip()
            if not idcc:
                continue
            outcomes.append(
                self.import_by_idcc(
                    idcc,
                    extract_rules=extract_rules,
                )
            )
            if outcomes[-1].cancelled:
                break
        return outcomes

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
        official_title: Optional[str] = None,
    ) -> tuple[dict[str, Any], bool]:
        existing = self._rules_repo.list_catalog_by_idcc(idcc)
        full_title = (official_title or title).strip()
        description = f"{full_title}\n\nSource Légifrance : {legifrance_url}"
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

    def _previous_text_hash(self, agreement_id: str, idcc: str) -> Optional[str]:
        rules_row = self._rules_repo.get_rules_by_idcc(idcc)
        if rules_row and rules_row.get("source_text_hash"):
            return str(rules_row["source_text_hash"])
        cached = self._text_cache.get_full_text(agreement_id)
        if cached:
            return _hash_text(cached)
        return None


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def get_kali_import_service() -> KaliImportService:
    return KaliImportService()
